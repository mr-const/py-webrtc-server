import asyncio, jinja2, aiohttp_jinja2
import json
import logging
import os
import random
import string

from aiohttp import web

log = logging.getLogger(__name__)


async def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(body=text.encode('utf-8'))


g_clients = {}

iceServers = [
  "stun://stun.l.google.com:19302",
  "stun://stun1.l.google.com:19302",
  "stun://stun2.l.google.com:19302",
  "stun://stun3.l.google.com:19302",
  "stun://stun4.l.google.com:19302"
]


def id_generator(size=12, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class Client(object):
    id = ""

    def __init__(self, id):
        self.id = id


def welcomeCallback(websocket, envelope):
    try:
        websocket.send_str(json.dumps(envelope))
    except Exception as ex:
        print("Failed to send welcome packet: " + repr(ex))


def handle_message(websocket, client, data):
    pass


def send_welcome(ws, client):
    welcomeMessage = {
      "id": client.id,
      "ice_servers": iceServers
    }

    envelope = {
        'welcome': welcomeMessage
    }

    welcomeCallback(ws, envelope)


async def wshandler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    clientId = id_generator(12)
    g_clients[clientId] = Client(clientId)

    print("new client inbound: " + clientId)

    send_welcome(ws, g_clients[clientId])

    async for msg in ws:
        if msg.tp == web.MsgType.text:
            handle_message(ws, g_clients[clientId], msg.data)
        elif msg.tp == web.MsgType.binary:
            ws.send_bytes(msg.data)
        elif msg.tp == web.MsgType.close:
            print("Client disconnected: " + clientId)
        elif msg.tp == web.MsgType.error:
            print('ws connection closed with exception %s' %
                  ws.exception())
        else:
            print("Unknown message <" + msg.tp + "> for client: " + clientId)

    return ws

async def index(request):
    return aiohttp_jinja2.render_template('index.html', request,
                                          {'header': 'hello world', 'footer': '(c) Troy Rynok LLC'})

async def streams(request):
    return web.Response(body=json.dumps(list(g_clients.keys())).encode("utf-8"), content_type="application/json")


async def init(loop):
    app = web.Application(loop=loop)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('./templates/'))
    app.router.add_static('/static', './static')
    app.router.add_route('GET', '/socket.io/', wshandler)
    app.router.add_route('GET', '/streams/', streams)
    app.router.add_route('GET', '/{name}', handle)
    app.router.add_route('GET', '/', index)

    srv = await loop.create_server(app.make_handler(),
                                   '127.0.0.1', 8080)
    print("Server started at http://127.0.0.1:8080")
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
