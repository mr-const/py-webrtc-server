import asyncio, jinja2, aiohttp_jinja2
import json
import logging

import aiohttp
from aiohttp import web

import settings
from client import Client

log = logging.getLogger(__name__)

g_clients = {}


def welcome_answer(client):
    welcome_message = {
      "id": client.id,
      "ice_servers": settings.ICE_SERVERS
    }

    envelope = {
        'type': 'welcome',
        'data': welcome_message
    }

    try:
        client.ws.send_str(json.dumps(envelope))
    except Exception as ex:
        print("Failed to send welcome packet: " + repr(ex))


def on_welcome(data, client):
    try:
        token = data["data"]["token"]
        client.id = token
        on_new_client(client)
    except KeyError:
        print("Token not found or invalid")
        on_delete_client(client)


def leave_client(client):
    print('-- ' + client.id + ' left --')


def process_message(data, client):
    dst_id = data['data']['to']
    if dst_id == client.id:
        print("-- Attempt to send message to yourself. Ignoring")
        return

    dst_client = g_clients.get(dst_id)
    if dst_client is None:
        print("Destination client: " + dst_id + " not found. Ignoring")
        return

    # Setting from: field
    data['data']['from'] = client.id
    json_txt = json.dumps(data)
    print("-- Sending message from: " + client.id + " to: " + dst_client.id)
    print(json_txt)
    dst_client.ws.send_str(json_txt)


def handle_incoming_packet(client, data):
    packet = json.loads(data)
    if packet.get('type') is None:
        print("unknown message: " + data)
        return

    if packet['type'] == "ehlo":
        on_welcome(packet, client)
    elif packet['type'] == "leave":
        leave_client(client)
    elif packet['type'] == "message":
        process_message(packet, client)
    else:
        print("unknown message: " + data)


@asyncio.coroutine
def ping_client(ws):
    if not ws.closed:
        ws.ping()
        print('ping sent')
        yield from asyncio.sleep(5)
        asyncio.Task(ping_client(ws))


@asyncio.coroutine
def do_close_ws(ws):
    if ws and not ws.closed:
        ws.close()


def on_new_client(client):
    data = asyncio.wait_for(aiohttp.post(settings.WEBRTC_LISTENER, data={"webrtc_id": client.id}), 5)
    if data.response_code == 201:
        g_clients[client.id] = client
        asyncio.Task(ping_client(client.ws))
        welcome_answer(client)
        print('-- ' + client.id + ' registered--')

    else:
        print("Not Authorized id: " + client.id)
        on_delete_client(client)

    yield from data.release()


def on_delete_client(client):
    print("Connection closed, removing client " + client.id)
    asyncio.Task(do_close_ws(client.ws))
    aiohttp.delete(settings.WEBRTC_LISTENER + client.id + "/")
    del g_clients[client.id]


@asyncio.coroutine
def wshandler(request):
    ws = web.WebSocketResponse()
    yield from ws.prepare(request)

    print('incoming connection initiated')
    client = Client(ws)

    while True:
        msg = yield from ws.receive()
        if msg.tp == web.MsgType.text:
            handle_incoming_packet(client, msg.data)
        elif msg.tp == web.MsgType.binary:
            ws.send_bytes(msg.data)
        elif msg.tp == web.MsgType.error:
            print('ws connection closed with exception %s' %
                  ws.exception())
        elif msg.tp == web.MsgType.closed:
            print('received close message')
            break
        else:
            print("Unknown message <" + str(msg.tp) + "> for client: " + client.id)

    on_delete_client(client)

    return ws


@asyncio.coroutine
def index(request):
    return aiohttp_jinja2.render_template('index.html', request,
                                          {'header': 'hello world',
                                           'footer': '(c) Troy Rynok LLC',
                                           'ws_url': settings.BIND_HOST + ':' + str(settings.BIND_PORT)})


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('./templates/'))
    app.router.add_static('/static', './static')
    app.router.add_route('GET', '/rtc/', wshandler)
    app.router.add_route('GET', '/', index)

    srv = yield from loop.create_server(app.make_handler(),
                                   settings.BIND_HOST, settings.BIND_PORT)
    print("Server started at http://"+settings.BIND_HOST+":"+str(settings.BIND_PORT))
    return srv


if __name__ == '__main__':
    log = logging.getLogger("")
    formatter = logging.Formatter("%(asctime)s %(levelname)s " +
                                  "[%(module)s:%(lineno)d] %(message)s")
    # setup console logging
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    ch.setFormatter(formatter)
    log.addHandler(ch)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(init(loop))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
