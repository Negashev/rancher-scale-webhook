import os
import time

import aiohttp
from japronto import Application

TOKEN = os.getenv('TOKEN', 'SECRET_TOKEN')
RANCHER_NODEPOOL_URL = os.getenv('RANCHER_NODEPOOL_URL', None)
RANCHER_VERIFY_SSL = bool(int(os.getenv('RANCHER_VERIFY_SSL', '0')))
RANCHER_TOKEN = os.getenv('RANCHER_TOKEN', None)
RANCHER_CORDONED_TIME = int(os.getenv('RANCHER_CORDONED_TIME', '3600'))
if RANCHER_NODEPOOL_URL is None:
    print("please set env 'RANCHER_NODEPOOL_URL'")


async def try_uncordon_node_of_nodepool(nodes):
    global RANCHER_TOKEN
    global RANCHER_VERIFY_SSL
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=RANCHER_VERIFY_SSL),
                                     headers={"Authorization": f"Bearer {RANCHER_TOKEN}"}) as session:
        async with session.get(nodes) as resp:
            print(f"try_uncordon_node_of_nodepool rancher api status: {resp.status}")
            list_nodes = await resp.json()
            for node in list_nodes['data']:
                if node['state'] == "cordoned":
                    async with session.post(node['actions']['uncordon']) as resp:
                        print(f"uncordon node rancher api status: {resp.status}")
                        uncordon = await resp.text()
                        return True
    return False


async def try_cordon_last_node_of_nodepool(nodes):
    global RANCHER_TOKEN
    global RANCHER_VERIFY_SSL
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=RANCHER_VERIFY_SSL),
                                     headers={"Authorization": f"Bearer {RANCHER_TOKEN}"}) as session:
        async with session.get(nodes) as resp:
            print(f"try_cordon_last_node_of_nodepool rancher api status: {resp.status}")
            list_nodes = await resp.json()
            node = list_nodes['data'][-1]
            if node['state'] == "active":
                async with session.post(node['actions']['cordon']) as resp:
                    print(f"cordon node rancher api status: {resp.status}")
                    cordon = await resp.text()
                    return True
            elif node['state'] == "cordoned":
                # check how long this machine is NoSchedule (cordoned)
                for taint in node['taints']:
                    if taint['effect'] == "NoSchedule" and taint['key'] == "node.kubernetes.io/unschedulable":
                        if taint['timeAddedTS'] / 1000 + RANCHER_CORDONED_TIME < time.time():
                            # kill cordoned machine
                            return False
                        else:
                            print(f"cordon node expire after time")
            elif node['state'] in ["provisioning", "error"]:
                # nothing do with if last node not ready
                print(f"last node not ready")
                return True
    return True


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
    # check if we have Cordoned node
    uncordon_node = await try_uncordon_node_of_nodepool(pool['links']['nodes'])
    if uncordon_node:
        print(f"scale up --> save time, uncordon node")
        return request.Response(text='ok')
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
    # check if we have Cordoned node
    cordon_node = await try_cordon_last_node_of_nodepool(pool['links']['nodes'])
    if cordon_node:
        print(f"scale down --> save time, cordon node")
        return request.Response(text='ok')
    old = pool['quantity']
    pool['quantity'] = pool['quantity'] - 1
    print(f"scale down {old} --> {pool['quantity']}")
    await set_nodepool(pool)
    return request.Response(text='ok')


app = Application()
r = app.router


def home(request):
    return request.Response(text='ok')


r.add_route('/', home, methods=['GET'])
r.add_route('/up/{token}', scale_up, methods=['POST'])
r.add_route('/down/{token}', scale_down, methods=['POST'])

app.run()
