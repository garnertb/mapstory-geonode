'use strict';

(function() {
  angular.module('mapstory.uploader', [])

  .config(function($interpolateProvider, $httpProvider) {
    $interpolateProvider.startSymbol('{[');
    $interpolateProvider.endSymbol(']}');
    $httpProvider.defaults.xsrfCookieName = 'csrftoken';
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
  })


  .controller('uploadList', function($scope, $http) {
   })

  .directive('upload',
      function($http) {
        return {
          restrict: 'C',
          replace: false,
          scope: true,
          // The linking function will add behavior to the template
          link: function(scope, element, attrs) {
              scope.showImportOptions = false;
              scope.layers = [];
              scope.canGetFields = true;
              scope.showImportWaiting = false;
              scope.getFields = function(uploadid) {
                  if (scope.canGetFields !== true) {
                      return;
                  }

                  scope.showImportWaiting = true;
                  $http.get('/uploads/fields/' + uploadid, {}).success(function(data, status) {
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


              function getDescriptionByIndex(index) {
                  for (var i = 0; i < scope.layers.length; i++) {
                        if (scope.layers[i]['index'] === index) {
                            return scope.layers[i];
                        }
                    }
              }

              function validateImportOptions(options, index){
                  var desc = getDescriptionByIndex(index);


                  if (!options.hasOwnProperty('index') === true) {
                      options['index'] = index;
                  }

                  var checkStartDate = options.hasOwnProperty('start_date');
                  var checkEndDate = options.hasOwnProperty('end_date');
                  var dates = [];

                  if (checkStartDate === true || checkEndDate == true) {
                      for (var i = 0; i < desc.fields.length; i++) {

                          var fieldType = desc.fields[i]['type'];
                            if (fieldType === 'Date' || fieldType === 'DateTime') {
                                dates.push(desc.fields[i]['name']);
                            }
                      }

                      if (checkStartDate === true && dates.indexOf(options['start_date']) == -1) {
                        options.convert_to_date.push(options['start_date']);
                      }

                      if (checkEndDate === true && dates.indexOf(options['end_date']) == -1) {
                        options.convert_to_date.push(options['end_date']);
                      }
                  }

                  return options;
              }

              scope.configureUpload = function(url, index) {
                  scope.configuring = true;
                  $http.post(url, [validateImportOptions(scope.importOptions, index)]).success(function(data, status) {
                      scope.configuring = false;
                      scope.complete = true;
                    if (data.hasOwnProperty('redirect')) {
                        window.location = data.redirect;
                    }
                }).error(function(data, status) {
                   scope.configuring = false;
                   scope.hasError = true;
                  });
              }
          }
        };
      });

})();
