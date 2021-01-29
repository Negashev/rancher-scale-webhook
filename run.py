import os
import time

import aiohttp
from japronto import Application

TOKEN = os.getenv('TOKEN', 'SECRET_TOKEN')
RANCHER_NODEPOOL_URL = os.getenv('RANCHER_NODEPOOL_URL', None)
RANCHER_VERIFY_SSL = bool(int(os.getenv('RANCHER_VERIFY_SSL', '0')))
RANCHER_TOKEN = os.getenv('RANCHER_TOKEN', None)
RANCHER_CORDONED_CPU = int(os.getenv('RANCHER_CORDONED_CPU', '5'))
RANCHER_VM_MAX = int(os.getenv('RANCHER_VM_MAX', '10'))
RANCHER_VM_MIN = int(os.getenv('RANCHER_VM_MIN', '1'))
if RANCHER_NODEPOOL_URL is None:
    print("please set env 'RANCHER_NODEPOOL_URL'")


async def try_uncordon_node_of_nodepool(nodes):
    global RANCHER_TOKEN
    global RANCHER_VERIFY_SSL
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=RANCHER_VERIFY_SSL),
                                     headers={"Authorization": f"Bearer {RANCHER_TOKEN}"}) as session:
        async with session.get(f'{nodes}&order=desc&sort=state') as resp:
            print(f"try_uncordon_node_of_nodepool rancher api status: {resp.status}")
            list_nodes = await resp.json()
            for node in list_nodes['data']:
                if node['state'] == "cordoned":
                    async with session.post(node['actions']['uncordon']) as resp:
                        print(f"uncordon node rancher api status: {resp.status}")
                        uncordon = await resp.text()
                        return True
    return False


async def try_cordon_last_node_of_nodepool(nodes, hostname_prefix):
    global RANCHER_TOKEN
    global RANCHER_VERIFY_SSL
    global RANCHER_VM_MIN
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=RANCHER_VERIFY_SSL),
                                     headers={"Authorization": f"Bearer {RANCHER_TOKEN}"}) as session:
        async with session.get(f'{nodes}&order=desc&sort=hostname') as resp:
            print(f"try_cordon_last_node_of_nodepool rancher api status: {resp.status}")
            not_sorted_list_nodes = await resp.json()
            # check status if only one VM is transitioning, stop scale down (scaling happened?)
            for node in not_sorted_list_nodes['data']:
                if node['transitioning'] == "yes":
                    print('found transitioning node')
                    return True
            # HM.... lambda before for not_sorted_list_nodes['data']
            list_nodes = sorted(not_sorted_list_nodes['data'], key = lambda i: int(i['hostname'][len(hostname_prefix):]), reverse=True)
            node = list_nodes[0]
            # check if this server "my-example-server-1" (first server)
            if node['hostname'] == hostname_prefix + '1':
                return True
            if node['state'] == "active":
                async with session.post(node['actions']['cordon']) as resp:
                    print(f"cordon node rancher api status: {resp.status}")
                    cordon = await resp.text()
                    return True
            elif node['state'] == "cordoned":
                # remove cordoned node if < RANCHER_CORDONED_CPU
                capacity = int(node['capacity']['cpu']) * 1000
                requested = int(node['requested']['cpu'].replace("m", ""))
                percent = requested/capacity * 100
                if percent <= RANCHER_CORDONED_CPU:
                    return False
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
    global RANCHER_VM_MAX
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
    # limit maximum VMs
    if RANCHER_VM_MAX + 1 <= pool['quantity']:
        return request.Response(text='ok')
    print(f"scale up {old} --> {pool['quantity']}")
    await set_nodepool(pool)
    return request.Response(text='ok')


async def scale_down(request):
    global TOKEN
    if request.match_dict['token'] != TOKEN:
        print(f"token '{request.match_dict['token']}' not valid")
        return request.Response(text='ok')
    pool = await get_nodepool()
    if pool['quantity'] <= RANCHER_VM_MIN:
        print(f'quantity <= {RANCHER_VM_MIN}')
        return request.Response(text='ok')
    # check if we have Cordoned node
    cordon_node = await try_cordon_last_node_of_nodepool(pool['links']['nodes'], pool['hostnamePrefix'])
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
