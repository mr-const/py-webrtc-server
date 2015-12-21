var PeerManager = (function () {
  
  var localId,
      config = {
        peerConnectionConfig: {
          iceServers: [
            // will now receive list from server with welcome message
            // {"url": "stun:23.21.150.121"},
            // {"url": "stun:stun.l.google.com:19302"}
          ]
        },
        peerConnectionConstraints: {
          optional: [
            {"DtlsSrtpKeyAgreement": true}
          ]
        }
      },
      peerDatabase = {},
      localStream,
      remoteVideoContainer = document.getElementById('remoteVideosContainer')

    var socket = new WebSocket("ws://" + ws_url + "/rtc/");

    function onMessage(msg) {
        console.log(msg);
        json = JSON.parse(msg.data)
        if (json.hasOwnProperty('type')) {
          if (json.type == 'message')
            handleMessage(json.data)
          else if (json.type == 'welcome') {
            handleWelcome(json.data)
          }
        }
    }

    function onEvent(event) {
      console.log(event);
    }

    socket.onopen = function(openEvent) {
        console.log(openEvent);
        socket.onmessage = onMessage;
        socket.onerror = onEvent;
        socket.onclose = onEvent;
        socket.send(JSON.stringify({
          type: "ehlo",
          data: {
            token: "DEADBABE"
          }
        }));
    };


  function addPeer(remoteId) {
    var peer = new Peer(config.peerConnectionConfig, config.peerConnectionConstraints);
    peer.pc.onicecandidate = function(event) {
      if (event.candidate) {
        send('candidate', remoteId, {
          label: event.candidate.sdpMLineIndex,
          id: event.candidate.sdpMid,
          candidate: event.candidate.candidate
        });
      }
    };
    peer.pc.onaddstream = function(event) {
      attachMediaStream(peer.remoteVideoEl, event.stream);
      remoteVideosContainer.appendChild(peer.remoteVideoEl);
    };
    peer.pc.onremovestream = function(event) {
      peer.remoteVideoEl.src = '';
      remoteVideosContainer.removeChild(peer.remoteVideoEl);
    };
    peer.pc.oniceconnectionstatechange = function(event) {
      switch(
      (  event.srcElement // Chrome
      || event.target   ) // Firefox
      .iceConnectionState) {
        case 'disconnected':
          remoteVideosContainer.removeChild(peer.remoteVideoEl);
          break;
      }
    };
    peerDatabase[remoteId] = peer;
        
    return peer;
  }
  function answer(remoteId) {
    var pc = peerDatabase[remoteId].pc;
    pc.createAnswer(
      function(sessionDescription) {
        pc.setLocalDescription(sessionDescription);
        send('answer', remoteId, sessionDescription);
      }, 
      error
    );
  }
  function offer(remoteId) {
    var pc = peerDatabase[remoteId].pc;
    pc.createOffer(
      function(sessionDescription) {
        pc.setLocalDescription(sessionDescription);
        send('offer', remoteId, sessionDescription);
      }, 
      error
    );
  }

    function handleWelcome(welcome) {
        localId = welcome.id;
        config.peerConnectionConfig.iceServers = welcome.ice_servers.map(function(x) { return {"url": x}; });

        console.log("Connected. ID: " + localId);
        console.log("iceServers: " + JSON.stringify(config.peerConnectionConfig.iceServers));
    }
  function handleMessage(message) {
    var type = message.type,
        from = message.from,
        pc = (peerDatabase[from] || addPeer(from)).pc;

    console.log('received ' + type + ' from ' + from);
  
    switch (type) {
      case 'init':
        toggleLocalStream(pc);
        offer(from);
        break;
      case 'offer':
        pc.setRemoteDescription(new RTCSessionDescription(message.payload), function(){}, error);
        answer(from);
        break;
      case 'answer':
        pc.setRemoteDescription(new RTCSessionDescription(message.payload), function(){}, error);
        break;
      case 'candidate':
        if(pc.remoteDescription) {
          pc.addIceCandidate(new RTCIceCandidate({
            sdpMLineIndex: message.payload.label,
            sdpMid: message.payload.id,
            candidate: message.payload.candidate
          }), function(){}, error);
        }
        break;
    }
  }
  function send(type, to, payload) {
    console.log('sending ' + type + ' to ' + to);

    socket.send(JSON.stringify({
        'type': 'message',
        data: {
          to: to,
          type: type,
          payload: payload
    }}));
  }
  function toggleLocalStream(pc) {
    if(localStream) {
      (!!pc.getLocalStreams().length) ? pc.removeStream(localStream) : pc.addStream(localStream);
    }
  }
  function error(err){
    console.log(err);
  }

  return {
    getId: function() {
      return localId;
    },
    
    setLocalStream: function(stream) {

      // if local cam has been stopped, remove it from all outgoing streams.
      if(!stream) {
        for(id in peerDatabase) {
          pc = peerDatabase[id].pc;
          if(!!pc.getLocalStreams().length) {
            pc.removeStream(localStream);
            offer(id);
          }
        }
      }

      localStream = stream;
    }, 

    toggleLocalStream: function(remoteId) {
      peer = peerDatabase[remoteId] || addPeer(remoteId);
      toggleLocalStream(peer.pc);
    },
    
    peerInit: function(remoteId) {
      peer = peerDatabase[remoteId] || addPeer(remoteId);
      //§send('init', remoteId, null);
      offer(remoteId);
    },

    peerRenegociate: function(remoteId) {
      offer(remoteId);
    },

    addDataChannel: function(remoteId) {
      peer = peerDatabase[remoteId] || addPeer(remoteId);

      var peerConnection = peer.pc;

      var dataChannelOptions = {
        ordered: true,
        maxRetransmitTime: 3000, //ms
      };

      var dataChannel = peerConnection.createDataChannel("dataChannelTest", dataChannelOptions);

      dataChannel.onerror = function (error) {
        console.log("Data Channel Error:", error);
      };

      dataChannel.onmessage = function (event) {
        console.log("Got Data Channel Message:". event.Data);
      };

      dataChannel.onopen = function () {
        console.log("Data Channel OnOpen:");
        dataChannel.send("Hello DataChannel!");
      };

      dataChannel.onclose = function() {
        console.log("The Data Channel is Closed");
      };
    },

    send: function(type, payload) {
        socket.send(JSON.stringify({
            'type': type,
            data: payload
        }))
    }
  };
  
});

var Peer = function (pcConfig, pcConstraints) {
  this.pc = new RTCPeerConnection(pcConfig, pcConstraints);
  this.remoteVideoEl = document.createElement('video');
  this.remoteVideoEl.controls = true;
  this.remoteVideoEl.autoplay = true;
}
