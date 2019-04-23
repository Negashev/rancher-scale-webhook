import os
import aiohttp
from japronto import Application

app = Application()
r = app.router

TOKEN = os.getenv('TOKEN', 'SECRET_TOKEN')
RANCHER_NODEPOOL_URL = os.getenv('RANCHER_NODEPOOL_URL', None)
RANCHER_VERIFY_SSL = bool(int(os.getenv('RANCHER_VERIFY_SSL', '0')))
RANCHER_TOKEN = os.getenv('RANCHER_TOKEN', None)
if RANCHER_NODEPOOL_URL is None:
    print("please set env 'RANCHER_NODEPOOL_URL'")


# Requests with the path set exactly to '/methods' and the method
# set to `POST` or `DELETE` will be directed here.
def home(request):
    return request.Response(text='ok')


r.add_route('/', home, methods=['GET'])


# Requests with the path starting with `/params/` segment and followed
# by two additional segments will be directed here.
# Values of the additional segments will be stored inside `request.match_dict`
# dictionary with keys taken from {} placeholders. A request to `/params/1/2`
# would leave `match_dict` set to `{'p1': 1, 'p2': '2'}`.

async def get_nodepool():
    global RANCHER_NODEPOOL_URL
    global RANCHER_TOKEN
    global RANCHER_VERIFY_SSL
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=RANCHER_VERIFY_SSL),
                                     headers={"Authorization": f"Bearer {RANCHER_TOKEN}"}) as session:
        async with session.get(RANCHER_NODEPOOL_URL) as resp:
            print(f"rancher api status: {resp.status}")
            return await resp.json()


async def set_nodepool(data):
    global RANCHER_NODEPOOL_URL
    global RANCHER_TOKEN
    global RANCHER_VERIFY_SSL
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=RANCHER_VERIFY_SSL),
                                     headers={"Authorization": f"Bearer {RANCHER_TOKEN}", "Accept": "application/json",
                                              "Content-Type": "application/json"}) as session:
        async with session.put(RANCHER_NODEPOOL_URL, json=data) as resp:
            print(f"rancher api status: {resp.status}")
            return await resp.json()


async def scale_up(request):
    global TOKEN
    if request.match_dict['token'] != TOKEN:
        print(f"token '{request.match_dict['token']}' not valid")
        return request.Response(text='ok')
    pool = await get_nodepool()
    old = pool['quantity']
    pool['quantity'] = pool['quantity'] + 1
    print(f"scale up {old} --> {pool['quantity']}")
    await set_nodepool(pool)
    return request.Response(text='ok')


async def scale_down(request):
    global TOKEN
    if request.match_dict['token'] != TOKEN:
        print(f"token '{request.match_dict['token']}' not valid")
        return request.Response(text='ok')
    pool = await get_nodepool()
    if pool['quantity'] <= 1:
        print('quantity <= 1')
        return request.Response(text='ok')
    old = pool['quantity']
    pool['quantity'] = pool['quantity'] - 1
    print(f"scale down {old} --> {pool['quantity']}")
    await set_nodepool(pool)
    return request.Response(text='ok')


r.add_route('/up/{token}', scale_up, methods=['POST'])
r.add_route('/down/{token}', scale_down, methods=['POST'])

app.run()
