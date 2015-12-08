import asyncio, jinja2, aiohttp_jinja2
import json
import logging
import random
import string

from aiohttp import web

import settings
from client import Client
from stream import Stream
from streamlist import StreamList

log = logging.getLogger(__name__)

g_clients = {}

g_streams = StreamList()

iceServers = [
  "stun://stun.l.google.com:19302",
  "stun://stun1.l.google.com:19302",
  "stun://stun2.l.google.com:19302",
  "stun://stun3.l.google.com:19302",
  "stun://stun4.l.google.com:19302"
]


def id_generator(size=12, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def welcome_callback(websocket, envelope):
    try:
        websocket.send_str(json.dumps(envelope))
    except Exception as ex:
        print("Failed to send welcome packet: " + repr(ex))


def send_welcome(ws, client):
    welcomeMessage = {
      "id": client.id,
      "ice_servers": iceServers
    }

    envelope = {
        'type': 'welcome',
        'data': welcomeMessage
    }

    welcome_callback(ws, envelope)


def register_client(data, client):
    name = data["data"]["name"]
    print('-- ' + client.id + ' registered with name: ' + name + ' --')
    g_streams.add_stream(client.id, Stream(client.id, name))


def leave_client(client):
    print('-- ' + client.id + ' left --')
    g_streams.remove_stream(client.id)


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


def handle_incoming_packet(websocket, client, data):
    packet = json.loads(data)
    if packet.get('type') is None:
        print("unknown message: " + data)
        return

    if packet['type'] == "ehlo":
        send_welcome(websocket, client)
    elif packet['type'] == "register_client":
        register_client(packet, client)
    elif packet['type'] == "leave":
        leave_client(client)
    elif packet['type'] == "message":
        process_message(packet, client)
    else:
        print("unknown message: " + data)


@asyncio.coroutine
def list_streams(request):
    return web.Response(body=g_streams.to_json().encode("utf-8"), content_type="application/json")


@asyncio.coroutine
def wshandler(request):
    ws = web.WebSocketResponse()
    yield from ws.prepare(request)

    client_id = id_generator(12)
    g_clients[client_id] = Client(client_id, ws)

    print("new client inbound: " + client_id)

    while True:
        msg = yield from ws.receive()
        if msg.tp == web.MsgType.text:
            handle_incoming_packet(ws, g_clients[client_id], msg.data)
        elif msg.tp == web.MsgType.binary:
            ws.send_bytes(msg.data)
        elif msg.tp == web.MsgType.error:
            print('ws connection closed with exception %s' %
                  ws.exception())
        elif msg.tp == web.MsgType.closed:
            print('received close message')
            break
        else:
            print("Unknown message <" + str(msg.tp) + "> for client: " + client_id)

    print("Connection closed, removing client " + client_id)
    del g_clients[client_id]
    g_streams.remove_stream(client_id)

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
    app.router.add_route('GET', '/streams/', list_streams)
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
