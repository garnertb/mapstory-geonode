'use strict';

(function() {
  angular.module('mapstory.uploader', [
      'ngResource',
      'ui.bootstrap',
      'mapstory.factories'
  ])

  .config(function($interpolateProvider, $httpProvider) {
    $interpolateProvider.startSymbol('{[');
    $interpolateProvider.endSymbol(']}');
    $httpProvider.defaults.xsrfCookieName = 'csrftoken';
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
  })


  .controller('uploadList', function($scope, UploadedData) {
    $scope.uploads = [];
    $scope.loading = true;
    $scope.currentPage = 0;
    $scope.offset = 0;
    $scope.limit = 10;


    function getUploads(query) {
        UploadedData.query(query).$promise.then(function(data) {
            $scope.uploads = data.objects;
            $scope.offset = data.meta.offset;
            $scope.totalItems = data.meta.total_count;
            $scope.loading = false;
        });
    }

    $scope.pageChanged = function() {
      $scope.offset = ($scope.currentPage - 1) * $scope.limit;
      var query = {offset: $scope.offset, limit: $scope.limit};
      getUploads(query);
    };

    getUploads({offset: $scope.offset, limit: $scope.limit});

   })

  .directive('upload',
      function($http, UploadedData) {
        return {
          restrict: 'E',
          replace: true,
          templateUrl: '/static/importer/partials/upload.html',
          scope: {
              upload: '=uploadObject',
              i: '=' //passes the index of the object, used to delete uploads
          },
          link: function(scope, element, attrs) {
              scope.showImportOptions = false;
              scope.layers = [];
              scope.canGetFields = true;
              scope.showImportWaiting = false;
              scope.showDetails = false;

              scope.allLayersImported = function() {
                for (var i = 0; i < scope.layers.length; i++) {
                    if (scope.layers[i].geonode_layer === {}){
                        return false
                    }
                }
                return true;
              };

              scope.deleteLayer = function(index) {
                  var id = scope.upload.id;
                  UploadedData.delete({id: id}, function() {
                     console.log(scope.$parent);

                     scope.$parent.uploads.splice(index, 1);

                  });
              };

              scope.getFields = function() {
                  if (scope.canGetFields !== true) {
                      return;
                  }
                  scope.showImportWaiting = true;
                  $http.get('/uploads/fields/' + scope.upload.id, {}).success(function(data, status) {
                      scope.layers = data;
                      scope.showImportWaiting = false;
                      scope.canGetFields = false;

                }).error(function(data, status) {
                   scope.showImportWaiting = false;
                   scope.configuring = false;
                   scope.hasError = true;
                  });
              };

          }
        };
      })

  .directive('layerInUpload',
      function($http) {
        return {
          restrict: 'C',
          replace: false,
          scope: true,
          // The linking function will add behavior to the template
          link: function(scope, element, attrs) {
              scope.configuring = false;
              scope.hasError = false;
              scope.complete = false;
              scope.importOptions = {configureTime: true, editable: true, convert_to_date: []};

              scope.isImported = function() {
                  return scope.status === 'SUCCESS';
              };

              function validateImportOptions(){
                  var desc = scope.layer;
                  var layer = scope.layer;

                  layer.configuration_options = layer.configuration_options || {};

                  if (!layer.hasOwnProperty('index') === true) {
                      layer['index'] = index;
                  }

                  var checkStartDate = layer.configuration_options.hasOwnProperty('start_date');
                  var checkEndDate = layer.configuration_options.hasOwnProperty('end_date');
                  var dates = [];

                  if (checkStartDate === true || checkEndDate == true) {
                      for (var i = 0; i < desc.fields.length; i++) {

                          var fieldType = desc.fields[i]['type'];
                            if (fieldType === 'Date' || fieldType === 'DateTime') {
                                dates.push(desc.fields[i]['name']);
                            }
                      }

                      if (checkStartDate === true && dates.indexOf(layer.configuration_options['start_date']) == -1) {
                        layer.configuration_options.convert_to_date.push(layer.configuration_options['start_date']);
                      }

                      if (checkEndDate === true && dates.indexOf(layer.configuration_options['end_date']) == -1) {
                        layer.configuration_options.convert_to_date.push(layer.configuration_options['end_date']);
                      }
                  }
              }

              scope.processing = function() {
                  return scope.layer.status === 'PENDING' || scope.layer.status === 'STARTED';
              };

              scope.complete = function() {
                  return scope.layer.status === 'SUCCESS' || scope.layer.geonode_layer != null;
              };

              function update(){
                  $http.get(scope.layer.resource_uri).success(function(data, status) {
                        console.log(scope.layer, data);
                        scope.layer = angular.extend(scope.layer, data);
                        console.log('updated the upload object');


                        if (scope.processing !== false) {
                            setTimeout(function() {
                                update();
                            }, 2000);
                            console.log(scope.layer.status);
                        }
                    });
              }


              scope.configureUpload = function() {
                  scope.configuring = true;
                  validateImportOptions();
                  $http.post(scope.layer.resource_uri + 'configure/', scope.layer.configuration_options).success(function(data, status) {
                    // extend current object with get request to resource_uri
                    console.log('configuration started');
                    update();
                }).error(function(data, status) {
                   scope.configuring = false;
                   scope.hasError = true;
                  });
              }
          }
        };
      });

})();
