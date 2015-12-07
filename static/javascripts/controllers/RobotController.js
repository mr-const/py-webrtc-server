/**
 * Created by sanjo on 01.12.15.
 */
'use strict';

var myAppControllers = angular.module('RobotController', []);

myAppControllers.controller('RobotController', ['Client', '$scope', '$window',
    function(Client, $scope, $window) {
        console.log("RobotController");

        var KEY_CODE_LEFT = 37,
            KEY_CODE_UP = 38,
            KEY_CODE_RIGHT = 39,
            KEY_CODE_DOWN = 40;

        $window.document.onkeydown = function(event) {
            switch (event.keyCode) {
                case KEY_CODE_LEFT:
                    $scope.robotSendLeft();
                    event.preventDefault();
                    break;

                case KEY_CODE_UP:
                    $scope.robotSendUp();
                    event.preventDefault();
                    break;

                case KEY_CODE_RIGHT:
                    $scope.robotSendRight();
                    event.preventDefault();
                    break;

                case KEY_CODE_DOWN:
                    $scope.robotSendDown();
                    event.preventDefault();
                    break;
            }
        };

        $window.document.onkeyup = function(event) {
            if (event.keyCode == KEY_CODE_LEFT
            || event.keyCode == KEY_CODE_UP
            || event.keyCode == KEY_CODE_RIGHT
            || event.keyCode == KEY_CODE_DOWN) {
                $scope.robotSendStop();
            }
        };

        $scope.robotSendStop = function() {
            Client.SendControlMessage(0, JSON.stringify({speed: 0, direction: 0}));
            console.log("robotSendStop");
        };
        $scope.robotSendUp = function() {
            Client.SendControlMessage(0, JSON.stringify({speed: 3, direction: 0}));
            console.log("robotSendUp");
        };
        $scope.robotSendLeft = function() {
            Client.SendControlMessage(0, JSON.stringify({speed: 3, direction: 1}));
            console.log("robotSendLeft");
        };
        $scope.robotSendRight = function() {
            Client.SendControlMessage(0, JSON.stringify({speed: 3, direction: 3}));
            console.log("robotSendRight");
        };
        $scope.robotSendDown = function() {
            Client.SendControlMessage(0, JSON.stringify({speed: 3, direction: 2}));
            console.log("robotSendDown");
        };
    }
]);