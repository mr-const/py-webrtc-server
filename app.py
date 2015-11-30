import asyncio, jinja2, aiohttp_jinja2
from aiohttp import web


async def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(body=text.encode('utf-8'))


async def wshandler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.tp == web.MsgType.text:
            ws.send_str("Hello, {}".format(msg.data))
        elif msg.tp == web.MsgType.binary:
            ws.send_bytes(msg.data)
        elif msg.tp == web.MsgType.close:
            break

    return ws


async def index(request):
    return aiohttp_jinja2.render_template('index.html', request, {'header': 'hello world', 'footer': '(c) Troy Rynok LLC'})


async def init(loop):
    app = web.Application(loop=loop)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('./templates/'))
    app.router.add_static('/static', './static')
    app.router.add_route('GET', '/socket.io/', wshandler)
    app.router.add_route('GET', '/{name}', handle)
    app.router.add_route('GET', '/', index)

    srv = await loop.create_server(app.make_handler(),
                                   '127.0.0.1', 8080)
    print("Server started at http://127.0.0.1:8080")
    return srv


loop = asyncio.get_event_loop()
loop.set_debug(True)
loop.run_until_complete(init(loop))

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
