!function(e){if("object"==typeof exports&&"undefined"!=typeof module)module.exports=e();else if("function"==typeof define&&define.amd)define([],e);else{var o;"undefined"!=typeof window?o=window:"undefined"!=typeof global?o=global:"undefined"!=typeof self&&(o=self),(o.storytools||(o.storytools={})).mapstory=e()}}(function(){var define,module,exports;return (function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
exports.MapConfigTransformer = require('./MapConfigTransformer');

},{"./MapConfigTransformer":2}],2:[function(require,module,exports){
exports.MapConfigTransformer = function(data) {
    var layers = [], i, ii, mode = 'cumulative';
    // look for playback mode in tools
    if (data.tools) {
        for (i=0, ii=data.tools.length; i<ii; ++i) {
            var tool = data.tools[i];
            if (tool.ptype === "gxp_playback" && tool.outputConfig) {
                if (tool.outputConfig.playbackMode === 'cumulative') {
                    mode = 'cumulative';
                }
                // TODO other modes
            }
        }
    }
    for (i=0, ii=data.map.layers.length; i<ii; ++i) {
         var layer = data.map.layers[i];
         // TODO for the editor we also need the invisible layers
         if (layer.visibility === true) {
             var source = data.sources[layer.source];
             var layerConfig = {
                 visibility: layer.visibility,
                 group: layer.group
             };
             if (source.ptype === "gxp_mapquestsource") {
                 layerConfig.type = 'MapQuest';
                 layerConfig.layer = layer.name === 'naip' ? 'sat' : 'osm';
                 layerConfig.title = layer.title;
                 layers.push(layerConfig);
             } else if (source.ptype === "gxp_mapboxsource") {
                 layerConfig.type = 'MapBox';
                 layerConfig.name = layer.name;
                 layerConfig.title = layer.title;
                 layers.push(layerConfig);
             } else if (source.ptype === "gx_olsource" || source.ptype === "gxp_wmscsource") {
                 layerConfig.type = (source.ptype === "gx_olsource") ? layer.type.replace('OpenLayers.Layer.', '') : "WMS";
                 if (layerConfig.type === 'OSM') {
                     if (layerConfig.args && layerConfig.args[0] === 'Humanitarian OpenStreetMap') {
                         layerConfig.type = 'HOT';
                     }
                     layerConfig.title = layer.title;
                 } else if (layerConfig.type === 'WMS') {
                     var params;
                     if (source.ptype === "gx_olsource" && layer.args) {
                         params = layer.args[2] || {};
                         for (var key in params) {
                             if (params[key].constructor === Array) {
                                 params[key.toUpperCase()] = params[key].join(',');
                                 delete params[key];
                             }
                         }
                         layerConfig.url = layer.args[1];
                     } else {
                         params = {
                             LAYERS: layer.name,
                             STYLES: layer.styles,
                             TILED: 'TRUE',
                             FORMAT: layer.format,
                             TRANSPARENT: layer.transparent
                         };
                         if (layer.tiled === false) {
                             layerConfig.singleTile = true;
                         }
                         layerConfig.id = layer.name;
                         layerConfig.name = layer.name;
                         layerConfig.title = layer.title;
                         // TODO not sure if this is the best place to do this?
                         if(source.url){
                            layerConfig.url = source.url.replace('http://mapstory.org/geoserver/', '/geoserver/');
                         }else{
                            layerConfig.url = '/geoserver/';
                         }

                     }
                     layerConfig.params = params;
                     layerConfig.params.VERSION = '1.1.1';
                     if (layer.capability) {
                         layerConfig.latlonBBOX = layer.capability.llbbox;
                         // TODO require dependency explicitly?
                         var times = storytools.core.time.maps.readCapabilitiesTimeDimensions(layer.capability, true);
                         if (times !== undefined) {
                             layerConfig.times = times;
                         }
                         // info for custom tileGrid
                         if (layer.capability.tileSets) {
                             for (var srs in layer.capability.tileSets[0].bbox) {
                                 var bbox = layer.capability.tileSets[0].bbox[srs].bbox;
                                 layerConfig.bbox = bbox;
                             }
                             layerConfig.resolutions = layer.capability.tileSets[0].resolutions;
                         }
                     }else if(layer.times){
                         layerConfig.times = layer.times;
                     }
                 }
                 layers.push(layerConfig);
             } else if (window.console) {
                 window.console.warn('Unknown source type in map config: ' + source.ptype);
             }
         }
     }
     return {
         id: data.id,
         playbackMode: mode,
         map: {
             center: data.map.center,
             projection: data.map.projection,
             zoom: data.map.zoom,
             layers: layers
         },
         about: data.about

     };
};

exports.MapToGXPConfigTransformer = function(config){

    var gxp_config = angular.copy(config);

    gxp_config.sources = {"1": {"ptype": "gx_olsource"},
        "0": {"url": "/geoserver/wms", "lazy": true, "restUrl": "/gs/rest", "name": "local geoserver", "ptype": "gxp_wmscsource"},
        "3": {"hidden": true, "ptype": "gxp_mapboxsource"},
        "2": {"hidden": true, "ptype": "gxp_mapquestsource"}};

    gxp_config.map.layers.forEach(function(layer, i) {
        //What to do if VECTOR?
        if(layer.type === 'WMS'){
            layer.type = 'OpenLayers.Layer.WMS';
            var key = 3 + i;
            var source = {};
            source[key] = {"url": layer.url, "lazy": true, "restUrl": "/gs/rest", "name": layer.name, "ptype": "gxp_wmscsource"};
            $.extend( gxp_config.sources, source);
            layer.source = key.toString();
        }
    });

    return gxp_config;
};


},{}]},{},[1])(1)
});