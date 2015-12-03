/**
 * Created by sanjo on 01.12.15.
 */

// Constants
var SIGNAL_MESSAGE = 'message';
var REGISTER_CLIENT_MESSAGE = 'register_client';

var PeerManager = (function () {
  // Message types
  var MESSAGE_TYPE_OFFER = 'offer';
  var MESSAGE_TYPE_ANSWER = 'answer';
  var MESSAGE_TYPE_CANDIDATE = 'candidate';

  // Variables
  var localId,
      config = {
        peerConnectionConfig: {
          iceServers: []
        },
        controlDataChannelName: "control_data_channel"
      },
      // connected peers
      peerDatabase = {},
      localStream,
      remoteVideosContainer = document.getElementById('remoteVideosContainer');

  function mediaConstraints() {
    return {
      mandatory: {
        OfferToReceiveAudio: true,
        OfferToReceiveVideo: true
      },
      optional: [
        { DtlsSrtpKeyAgreement        : true},
        { 'enable-sctp-data-channels' : true}
      ]
    }
  }

  var socket = new WebSocket("ws://" + ws_url + "/socket.io/");

  function onMessage(msg) {
    console.log(msg);
    json = JSON.parse(msg.data);
    if (json.hasOwnProperty('welcome')) {
      handleWelcome(json.welcome)
    }
    else if (json.hasOwnProperty('type')) {
      if (json.type == 'message')
        handleMessage(json.data);
      }
  };

  function onEvent(event) {
    console.log(event);
  }

  socket.onopen = function(openEvent) {
    console.log(openEvent);
    socket.onmessage = onMessage;
    socket.onerror = onEvent;
    socket.onclose = onEvent;
    socket.send(JSON.stringify({type: "ehlo"}));
  };

  function handleWelcome(welcome) {
    localId = welcome.id;
    config.peerConnectionConfig.iceServers = welcome.ice_servers.map(function(x) {
      return {"url": x};
    });

    console.log("Connected. ID: " + localId);
    console.log("iceServers: " + JSON.stringify(config.peerConnectionConfig.iceServers));
  }

  // handle signaling messages
  function handleMessage(message) {
    var type = message.type,
        from = message.from,
        pc = (peerDatabase[from] || createPeer(from)).pc;

    console.log('received ' + type + ' from ' + from);

    switch (type) {
      case MESSAGE_TYPE_OFFER:
        if(localStream) {
            pc.addStream(localStream);
        }
        pc.setRemoteDescription(new RTCSessionDescription({
            type: 'offer',
            sdp: message.payload.sdp
          }), function () {
          }, error);
        createAnswer(from);
        break;

      case MESSAGE_TYPE_ANSWER:
        pc.setRemoteDescription(new RTCSessionDescription({
                    type: 'answer',
                    sdp: message.payload.sdp
                }), function() { }, error);
                break;
      case MESSAGE_TYPE_CANDIDATE:
        if(pc.remoteDescription) {
          pc.addIceCandidate(new RTCIceCandidate({
            sdpMLineIndex: message.payload.label,
            sdpMid: message.payload.id,
            candidate: message.payload.candidate
          }), function() { }, error);
        }
        break;
    }
  }

  function createPeer(remoteId) {
    var peer = new Peer(config.peerConnectionConfig, mediaConstraints());
    var pc = peer.pc;
    pc.onicecandidate = function (event) {
      if (event.candidate) {
        sendMessage(MESSAGE_TYPE_CANDIDATE, remoteId, {
          label: event.candidate.sdpMLineIndex,
          id: event.candidate.sdpMid,
          candidate: event.candidate.candidate
        });
      }
    };

    pc.onaddstream = function (event) {
        console.log("onaddstream");
        remoteVideosContainer.appendChild(peer.remoteVideoEl);
        attachMediaStream(peer.remoteVideoEl, event.stream);
    };
    pc.onremovestream = function (event) {
        peer.remoteVideoEl.src = '';
        remoteVideosContainer.removeChild(peer.remoteVideoEl);
    };
    pc.oniceconnectionstatechange = function (event) {
        var state = (event.srcElement  // Chrome
                     || event.target) // Firefox
                        .iceConnectionState;
        console.log('ICE connection state changed to ' + state)
        switch (state) {
            case 'disconnected':
                remoteVideosContainer.removeChild(peer.remoteVideoEl);
                if (peer.dc) {
                    peer.dc.close();
                    delete peer.dc;
                }
                break;
        }
    };

    pc.ondatachannel = function (event) {
      if (event.channel.label != config.controlDataChannelName) {
        console.log('Unexpected data channel ' + event.channel.label);
        return
      }
      console.log('Received control data channel');
      peer.dc = event.channel;
      initDataChannel(peer.dc)
    };

    peerDatabase[remoteId] = peer;

    return peer;
  }

  function createAnswer(remoteId) {
    var pc = peerDatabase[remoteId].pc;
    pc.createAnswer(function (sessionDescription) {
      pc.setLocalDescription(sessionDescription);
      sendMessage(MESSAGE_TYPE_ANSWER, remoteId, sessionDescription);
    }, error, mediaConstraints());
  }

  function createOffer(remoteId) {
    var pc = peerDatabase[remoteId].pc;
    createControlChannel(remoteId);
    pc.createOffer(function (sessionDescription) {
      pc.setLocalDescription(sessionDescription);
      sendMessage(MESSAGE_TYPE_OFFER, remoteId, sessionDescription);
    }, error, mediaConstraints());
  }

  function createControlChannel(remoteId) {
    var peer = peerDatabase[remoteId];
    var dataChannelConfig = {
      id: 0,
      maxRetransmits: 0
    };
    peer.dc = peer.pc.createDataChannel(config.controlDataChannelName, dataChannelConfig);
    console.log('Creating control data channel');
    initDataChannel(peer.dc);
  }

  function initDataChannel(channel) {
    channel.onmessage = function (event) {
      console.log('Received message' + event.data)
    };
    channel.onopen = function () {
      console.log('Channel ' + channel.label + ' opened')
    };
    channel.onclose = function () {
      console.log('Channel ' + channel.label + ' closed')
    };
  }

  function sendMessage(type, to, payload) {
    console.log('sending ' + type + ' to ' + to);

    socket.send(JSON.stringify({
      'type': SIGNAL_MESSAGE,
      data: {
        to: to,
        type: type,
        payload: payload
      }
    }));
  }

  function sendMessageToServer(type, payload) {
    socket.send(JSON.stringify({
      'type': type,
      data: payload
    }));
  }

  function sendControlMessage(remoteId, message) {
    var peer = peerDatabase[remoteId];

    if (!peer.dc || peer.dc.readyState != 'open') {
      console.log('Attempt to send control message to peer without being connected to it');
      return
    }
    peer.dc.send(message)
  }

  function error(err){
    console.log(err);
  }

  return {
    GetId: function() {
      return localId;
    },
    
    SetLocalStream: function(stream) {
      // if local cam has been stopped, remove it from all outgoing streams.
      if (!stream) {
        for (id in peerDatabase) {
          var remotePC = peerDatabase[id].pc;
          if (!!remotePC.getLocalStreams().length) {
            remotePC.removeStream(localStream);
            createOffer(id);
          }
        }
      }

      localStream = stream;
    },
    
    CreateOffer: function (remoteId) {
      if (!peerDatabase[remoteId]) {
        createPeer(remoteId);
      }
      createOffer(remoteId);
    },

    SendControlMessage: function (remoteId, message) {
      if (!peerDatabase[remoteId]) {
        createPeer(remoteId);
      }
      sendControlMessage(remoteId, message)
    },

    //PeerRenegotiate: function (remoteId) {
    //    createOffer(remoteId);
    //},

    Send: function (type, payload) {
      sendMessageToServer(type, payload)
    }
  };
});

var Peer = function (pcConfig, pcConstraints) {
  this.pc = new RTCPeerConnection(pcConfig, pcConstraints);
  this.remoteVideoEl = document.createElement('video');
  this.remoteVideoEl.controls = true;
  this.remoteVideoEl.autoplay = true;
};
