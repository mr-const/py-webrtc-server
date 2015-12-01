class StreamList(object):
    streams = {}

    def add_stream(self, stream_id, stream):
        self.streams[stream_id] = stream

    def remove_stream(self, stream_id):
        del self.streams[stream_id]

    def to_json(self):
        js = "["
        for key, value in self.streams.items():
            js += value.to_json() + ","
        js += "]"
        return js

