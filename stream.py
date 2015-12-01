import json


class Stream(object):
    id = ""
    name = ""

    def __init__(self, stream_id, name):
        self.id = stream_id
        self.name = name

    def to_json(self):
        return json.dumps(self.__dict__)
