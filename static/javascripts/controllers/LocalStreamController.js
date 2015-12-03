/**
 * Created by sanjo on 01.12.15.
 */
'use strict';

var myAppControllers = angular.module('LocalStreamController', []);

myAppControllers.controller('LocalStreamController', ['camera', 'Client', '$scope', '$window',
    function(camera, Client, $scope, $window) {
        console.log("LocalStreamController");

        var localStream = this;
        localStream.name = 'Guest';
        localStream.link = '';
        localStream.cameraIsOn = false;

        $scope.$on('cameraIsOn', function (event, data) {
            $scope.$apply(function () {
                localStream.cameraIsOn = data;
            });
        });

        $scope.registerClient = function() {
            console.log("Register client handler");
            camera.start().then(function (result) {
                        localStream.link = $window.location.host + '/' + Client.GetId();
                        Client.Send(REGISTER_CLIENT_MESSAGE, {name: localStream.name});
                    })
                    .catch(function (err) {
                        console.log(err);
                    });
        }
    }
]);