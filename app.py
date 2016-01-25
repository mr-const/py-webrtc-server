import asyncio, jinja2, aiohttp_jinja2
import json
import logging

import aiohttp
from aiohttp import web

import settings
from client import Client

log = logging.getLogger(__name__)

g_sessions = {}


def welcome_answer(client):
    welcome_message = {
      "id": client.session_id,
      "ice_servers": settings.ICE_SERVERS
    }

    send_message('welcome', welcome_message, client)


def send_message(message_type, payload, client):
    envelope = {
        'type': message_type,
        'data': payload
    }

    try:
        client.ws.send_str(json.dumps(envelope))
    except Exception as ex:
        log.warn("Failed to send data packet: " + repr(ex))


@asyncio.coroutine
def on_welcome(data, client):
    try:
        token = data["data"]["token"]
        subtok = token.split(' ')
        # Assuming we got string Bearer <TOKEN_UID> then it's human
        if len(subtok) > 1:
            client.type = 'human'
        else:
            client.type = 'robot'

        client.token = token

        yield from on_new_client(client)
    except KeyError:
        on_delete_client(client, "Token not found or invalid")


def leave_client(client):
    log.info('-- ' + client.session_id + ' left --')


def return_error(client, message):
    log.error("error:" + message)
    err = {"type": "error", "reason": message}
    client.ws.send_str(json.dumps(err))


def process_message(data, client):
    dst_id = data['data']['to']
    if dst_id == client.session_id:
        return_error(client, "Attempt to send message to yourself. Ignored")
        return

    dst_client = g_sessions.get(dst_id)
    if dst_client is None:
        return_error(client, "Destination client: " + dst_id + " not found. Ignoring")
        return

    # Setting from: field
    data['data']['from'] = client.session_id
    data['data']['sender_id'] = client.id
    json_txt = json.dumps(data)
    log.info("-- Sending message from: " + client.session_id + " to: " + dst_client.session_id)
    log.debug(json_txt)
    dst_client.ws.send_str(json_txt)


@asyncio.coroutine
def handle_incoming_packet(client, data):
    packet = json.loads(data)
    if packet.get('type') is None:
        return_error(client, "unknown message: " + data)
        return

    if packet['type'] == "ehlo":
        yield from on_welcome(packet, client)
    elif packet['type'] == "leave":
        leave_client(client)
    elif packet['type'] == "message":
        process_message(packet, client)
    else:
        return_error(client, "unknown message: " + data)


@asyncio.coroutine
def ping_client(ws):
    if not ws.closed:
        ws.ping()
        log.debug('ping sent')
        yield from asyncio.sleep(5)
        asyncio.Task(ping_client(ws))


@asyncio.coroutine
def do_close_ws(ws):
    if ws and not ws.closed:
        yield from ws.close()


@asyncio.coroutine
def on_new_client(client):
    headers = {}
    if client.type == 'human':
        headers["Authorization"] = client.token
    elif client.type == 'robot':
        headers["X-Robot-Key"] = client.token

    try:
        data = yield from asyncio.wait_for(aiohttp.post(settings.WEBRTC_LISTENER,
                                                        headers=headers),
                                           5)
    except (aiohttp.ClientResponseError, TimeoutError) as e:
        on_delete_client(client, "Auth server not available for token: " + client.token + " due to: " + str(e))
        return

    if data.status == 202:
        response = yield from data.json()
        client.id = response['client_id']
        client.session_id = response['webrtc_session_id']
        g_sessions[client.session_id] = client
        asyncio.Task(ping_client(client.ws))
        welcome_answer(client)
        log.info('-- ' + client.session_id + ' registered--')

    else:
        response = yield from data.text()
        log.error('Auth result: ' + str(response))
        yield from data.release()
        on_delete_client(client, "Not Authorized token: " + client.token)


def on_delete_client(client, reason):
    headers = {}
    if client.type == 'human':
        headers["Authorization"] = client.token
    elif client.type == 'robot':
        headers["X-Robot-Key"] = client.token

    log.info("Connection closed, removing client " + client.session_id)
    log.info("Reason: " + reason)
    send_message("error", {"type": "disconnect", "reason": reason}, client)
    asyncio.Task(do_close_ws(client.ws))
    aiohttp.delete(settings.WEBRTC_LISTENER, headers=headers)
    if client.session_id in g_sessions:
        del g_sessions[client.session_id]


@asyncio.coroutine
def wshandler(request):
    ws = web.WebSocketResponse()
    yield from ws.prepare(request)

    log.debug('incoming connection initiated')
    client = Client(ws)

    while True:
        msg = yield from ws.receive()
        if msg.tp == web.MsgType.text:
            yield from handle_incoming_packet(client, msg.data)
        elif msg.tp == web.MsgType.binary:
            ws.send_bytes(msg.data)
        elif msg.tp == web.MsgType.error:
            log.warn('ws connection closed with exception %s' %
                  ws.exception())
        elif msg.tp == web.MsgType.closed:
            log.info('received close message')
            break
        else:
            log.warn("Unknown message <" + str(msg.tp) + "> for client: " + client.session_id)

    on_delete_client(client, "good bye")

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
    log.info("Server started at http://"+settings.BIND_HOST+":"+str(settings.BIND_PORT))
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
