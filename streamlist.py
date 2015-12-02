class StreamList(object):
    streams = {}

    def add_stream(self, stream_id, stream):
        self.streams[stream_id] = stream

    def remove_stream(self, stream_id):
        if stream_id in self.streams:
            del self.streams[stream_id]

    def to_json(self):
        return "["+",".join(y.to_json() for x, y in self.streams.items())+"]"
