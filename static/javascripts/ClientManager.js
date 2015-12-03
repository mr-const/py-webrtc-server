/**
 * Created by sanjo on 01.12.15.
 */
var clientManager = angular.module('ClientManager', []);

clientManager.factory('Client', function () {
    return new PeerManager();
});