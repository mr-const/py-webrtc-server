import asyncio, jinja2, aiohttp_jinja2
import json
import logging
import time

import aiohttp
import sys
from aiohttp import web

import settings
from client import Client

log = logging.getLogger(__name__)

g_sessions = {}

ERR_GENERAL = 400
ERR_NOT_FOUND = 404
ERR_UNKNOWN_MESSAGE = 1001


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
        # We use JWT tokens for human users, so if we extract something that can be split to 3 pieces - probably it's
        # human token
        token = data["data"]["token"]
        subtok = token.split('.')
        # Assuming we got string aaa.bbb.ccc (JWT) then it's human
        if len(subtok) == 3:
            client.type = 'human'
            client.token = 'JWT ' + token
        else:
            client.type = 'robot'
            client.token = token

        yield from on_new_client(client)
    except KeyError:
        yield from request_close(client, "Token not found or invalid")


def leave_client(client):
    log.info('-- ' + client.session_id + ' left --')


def return_error(client, packet_id, message, code):
    log.error("error:" + message)
    err = {"type": "error",
           "id": packet_id,
           "data": {
               "reason": message,
               "code": code
           }}
    if not client.ws.closed:
        client.ws.send_str(json.dumps(err))


@asyncio.coroutine
def process_message(data, client):
    packet = data.get('data')
    if not packet:
        log.error("Invalid packet data: " + packet)
        return_error(client, 0, "Invalid packet data: " + packet, ERR_GENERAL)
        return

    dst_id = packet.get('to')
    packet_id = data.get('id')

    if dst_id is None:
        return_error(client, packet_id, "Unknown packet destination id", ERR_GENERAL)
        return

    if dst_id == client.session_id:
        return_error(client, packet_id, "Attempt to send message to yourself. Ignored", ERR_GENERAL)
        return

    dst_client = g_sessions.get(dst_id)
    if dst_client is None:
        return_error(client, packet_id, "Destination client: " + dst_id + " not found. Ignoring", ERR_NOT_FOUND)
        return

    access = yield from has_access(client, dst_client)
    if not access:
        return_error(client, packet_id, "Permission denied to access ID: {}".format(dst_id), ERR_GENERAL)
        return

    # Setting from: field
    data['data']['from'] = client.session_id
    data['data']['sender_id'] = client.id
    json_txt = json.dumps(data)
    if not dst_client.ws.closed:
        log.info("-- Sending message from: " + client.session_id + " to: " + dst_client.session_id)
        log.debug(json_txt)
        dst_client.ws.send_str(json_txt)
    else:
        log.warn("-- client socket is closed: " + client.session_id)


@asyncio.coroutine
def handle_incoming_packet(client, data):
    packet = json.loads(data)
    if packet.get('type') is None:
        return_error(client, 0, "unknown message: " + data, ERR_UNKNOWN_MESSAGE)
        return

    if packet['type'] == "ehlo":
        yield from on_welcome(packet, client)
    elif packet['type'] == "leave":
        leave_client(client)
    elif packet['type'] == "message":
        yield from process_message(packet, client)
    else:
        return_error(client, 0, "unknown message: " + data, ERR_UNKNOWN_MESSAGE)


@asyncio.coroutine
def ping_client(client):
    if not client.ws.closed:
        if client.ws._writer.writer._conn_lost:
            log.error('connection lost to: ' + client.session_id)
            yield from on_delete_client(client)
            return

        client.ws.ping()
        log.debug('ping sent to: ' + client.session_id)
        loop.call_later(5, asyncio.async, ping_client(client))


@asyncio.coroutine
def do_close_ws(ws):
    if ws and not ws.closed:
        yield from ws.close()


@asyncio.coroutine
def has_access(client, target):
    # check only Human users for access
    if client.type == 'robot':
        return True

    headers = {'Authorization': client.token}
    try:
        data = yield from asyncio.wait_for(aiohttp.get(settings.ACCESS_API.format(target.id),
                                                       headers=headers), 5)
    except (aiohttp.ClientResponseError, aiohttp.errors.ClientOSError, TimeoutError) as e:
        log.error('Access denied due to failed API call: ' + str(repr(e)))
        return False

    if data.status == 200:
        acc_token = yield from data.json()
        log.info('Received access grant with token: ' + str(repr(acc_token)))
        now = int(time.time())
        return int(acc_token['exp']) >= now >= int(acc_token['nbf'])

    else:
        response = yield from data.text()
        log.error('Access denied with result: ' + str(response))
        yield from data.release()
        return False


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
    except (aiohttp.ClientResponseError, aiohttp.errors.ClientOSError, TimeoutError) as e:
        yield from request_close(client, "Auth server not available for token: " + client.token + " due to: " + str(e))
        return

    if data.status == 202:
        response = yield from data.json()
        client.id = response['client_id']
        client.session_id = response['webrtc_session_id']
        g_sessions[client.session_id] = client
        yield from ping_client(client)
        welcome_answer(client)
        log.info('-- ' + client.session_id + ' registered--')

    else:
        response = yield from data.text()
        log.error('Auth result: ' + str(response))
        yield from data.release()
        yield from request_close(client, "Not Authorized token: " + client.token)


@asyncio.coroutine
def request_close(client, reason):
    log.info("Close requested for " + str(client.session_id) + " Reason: " + reason)
    return_error(client, 0, reason, ERR_GENERAL)
    yield from do_close_ws(client.ws)


@asyncio.coroutine
def on_delete_client(client):
    headers = {}
    if hasattr(client, 'type'):
        if client.type == 'human':
            headers["Authorization"] = client.token
        elif client.type == 'robot':
            headers["X-Robot-Key"] = client.token

        log.info("Connection closed for " + client.session_id + ". Notifying Auth server and deleting from active")

        response = yield from asyncio.wait_for(aiohttp.delete(settings.WEBRTC_LISTENER, headers=headers,
                                                              data={'webrtc_session_id': client.session_id}), 5)
        yield from response.release()
    else:
        log.info("Connection closed for " + str(repr(client)) + ". Type unknown, simply removing from sessions")

    if client.session_id in g_sessions:
        del g_sessions[client.session_id]


@asyncio.coroutine
def wshandler(request):
    ws = web.WebSocketResponse(protocols=('base46',))
    yield from ws.prepare(request)

    log.info('incoming connection initiated')
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

    loop.call_later(5, asyncio.async, on_delete_client(client))

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
    log.info("Server started at http://" + settings.BIND_HOST + ":" + str(settings.BIND_PORT))
    return srv


if __name__ == '__main__':
    log = logging.getLogger("")
    formatter = logging.Formatter("%(asctime)s %(levelname)s " +
                                  "[%(module)s:%(lineno)d] %(message)s")
    # setup console logging
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.INFO)

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
