/**
 * Created by sanjo on 01.12.15.
 */
'use strict';

var myAppControllers = angular.module('RobotListController', []);

myAppControllers.controller('RobotListController', ['$scope', '$http', 'Client',
    function($scope, $http, Client) {
        console.log("RobotListController");

        // @todo: replace with api request
        $http.get('/streams/').then(function successCallback(response) {
            $scope.robotList = response.data;
        }, function errorCallback(response) {
            console.log("Error: " + response);
        });

        $scope.view = function(robot) {
            console.log("View button pressed for robot: " + JSON.stringify(robot));
            Client.CreateOffer(robot.id);
        }
    }
]);