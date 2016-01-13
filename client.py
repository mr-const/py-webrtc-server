class Client(object):
    id = "noid"
    session_id = "undefined"
    token = ""
    ws = None
    type = 'human'

    def __init__(self, websocket):
        self.ws = websocket
