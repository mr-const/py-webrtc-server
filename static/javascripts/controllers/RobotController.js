/**
 * Created by sanjo on 01.12.15.
 */
'use strict';

var myAppControllers = angular.module('RobotController', []);

myAppControllers.controller('RobotController', ['$scope', '$window',
    function($scope, $window) {
        console.log("RobotController");

        var KEY_CODE_LEFT = 37,
            KEY_CODE_UP = 38,
            KEY_CODE_RIGHT = 39,
            KEY_CODE_DOWN = 40

        $window.document.onkeydown = function(event) {
            switch (event.keyCode) {
                case KEY_CODE_LEFT:
                    $scope.robotSendLeft();
                    break;

                case KEY_CODE_UP:
                    $scope.robotSendUp();
                    break;

                case KEY_CODE_RIGHT:
                    $scope.robotSendRight();
                    break;

                case KEY_CODE_DOWN:
                    $scope.robotSendDown();
                    break;
            }
        };

        $scope.robotSendUp = function() {
            console.log("robotSendUp");
        };
        $scope.robotSendLeft = function() {
            console.log("robotSendLeft");
        };
        $scope.robotSendRight = function() {
            console.log("robotSendRight");
        };
        $scope.robotSendDown = function() {
            console.log("robotSendDown");
        };
    }
]);