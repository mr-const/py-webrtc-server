# WebRTC server settings

BIND_HOST = "127.0.0.1"
BIND_PORT = 3333

WEBRTC_LISTENER = "http://127.0.0.1:8000/api/webrtc/"

ICE_SERVERS = [
    "stun:104.45.22.14:3478"
]

try:
    from settings_local import *
except ImportError:
    pass
