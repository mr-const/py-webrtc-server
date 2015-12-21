class Client(object):
    id = "undefined"
    ws = None

    def __init__(self, websocket):
        self.ws = websocket
