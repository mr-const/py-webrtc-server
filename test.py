import stream
from streamlist import StreamList

stream0 = stream.Stream('123', 'User')
stream1 = stream.Stream('999', 'Looser')
streamlist = StreamList()
streamlist.add_stream('123', stream0)
streamlist.add_stream('999', stream1)
print(streamlist.to_json())
