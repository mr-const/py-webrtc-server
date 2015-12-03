/**
 * Created by sanjo on 01.12.15.
 */
var cameraManager = angular.module('CameraManager', []);

var mediaConfig = {
    audio: true,
    video: {
        mandatory: {},
        optional: []
    }
};

cameraManager.factory('camera', ['$rootScope', '$window', 'Client', function ($rootScope, $window, Client) {
    var camera = {};
    camera.preview = $window.document.getElementById('localVideo');

    camera.start = function() {
        return new Promise(function (resolve, reject) {
            return requestUserMedia(mediaConfig)
                .then(function (stream) {
                    attachMediaStream(camera.preview, stream);
                    Client.SetLocalStream(stream);
                    camera.stream = stream;
                    $rootScope.$broadcast('cameraIsOn', true);
                    resolve();
                })
                .catch(function (error) {
                    console.log("Error accessing camera: " + error);
                    reject();
                });
        });
    };

    camera.stop = function () {
        return new Promise(function (resolve, reject) {
            try {
                camera.stream.stop();
                camera.preview.src = '';
                resolve();
            } catch (error) {
                reject(error);
            }
        })
            .then(function (result) {
                $rootScope.$broadcast('cameraIsOn', false);
            });
    };

    return camera;
}]);