class Client(object):
    id = ""
    ws = None

    def __init__(self, client_id, websocket):
        self.id = client_id
        self.ws = websocket
