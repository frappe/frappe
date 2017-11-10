(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(_dereq_,module,exports){
function corslite(url, callback, cors) {
    var sent = false;

    if (typeof window.XMLHttpRequest === 'undefined') {
        return callback(Error('Browser not supported'));
    }

    if (typeof cors === 'undefined') {
        var m = url.match(/^\s*https?:\/\/[^\/]*/);
        cors = m && (m[0] !== location.protocol + '//' + location.hostname +
                (location.port ? ':' + location.port : ''));
    }

    var x = new window.XMLHttpRequest();

    function isSuccessful(status) {
        return status >= 200 && status < 300 || status === 304;
    }

    if (cors && !('withCredentials' in x)) {
        // IE8-9
        x = new window.XDomainRequest();

        // Ensure callback is never called synchronously, i.e., before
        // x.send() returns (this has been observed in the wild).
        // See https://github.com/mapbox/mapbox.js/issues/472
        var original = callback;
        callback = function() {
            if (sent) {
                original.apply(this, arguments);
            } else {
                var that = this, args = arguments;
                setTimeout(function() {
                    original.apply(that, args);
                }, 0);
            }
        }
    }

    function loaded() {
        if (
            // XDomainRequest
            x.status === undefined ||
            // modern browsers
            isSuccessful(x.status)) callback.call(x, null, x);
        else callback.call(x, x, null);
    }

    // Both `onreadystatechange` and `onload` can fire. `onreadystatechange`
    // has [been supported for longer](http://stackoverflow.com/a/9181508/229001).
    if ('onload' in x) {
        x.onload = loaded;
    } else {
        x.onreadystatechange = function readystate() {
            if (x.readyState === 4) {
                loaded();
            }
        };
    }

    // Call the callback with the XMLHttpRequest object as an error and prevent
    // it from ever being called again by reassigning it to `noop`
    x.onerror = function error(evt) {
        // XDomainRequest provides no evt parameter
        callback.call(this, evt || true, null);
        callback = function() { };
    };

    // IE9 must have onprogress be set to a unique function.
    x.onprogress = function() { };

    x.ontimeout = function(evt) {
        callback.call(this, evt, null);
        callback = function() { };
    };

    x.onabort = function(evt) {
        callback.call(this, evt, null);
        callback = function() { };
    };

    // GET is the only supported HTTP Verb by XDomainRequest and is the
    // only one supported here.
    x.open('GET', url, true);

    // Send the request. Sending data is not supported.
    x.send(null);
    sent = true;

    return x;
}

if (typeof module !== 'undefined') module.exports = corslite;

},{}],2:[function(_dereq_,module,exports){
'use strict';

/**
 * Based off of [the offical Google document](https://developers.google.com/maps/documentation/utilities/polylinealgorithm)
 *
 * Some parts from [this implementation](http://facstaff.unca.edu/mcmcclur/GoogleMaps/EncodePolyline/PolylineEncoder.js)
 * by [Mark McClure](http://facstaff.unca.edu/mcmcclur/)
 *
 * @module polyline
 */

var polyline = {};

function py2_round(value) {
    // Google's polyline algorithm uses the same rounding strategy as Python 2, which is different from JS for negative values
    return Math.floor(Math.abs(value) + 0.5) * Math.sign(value);
}

function encode(current, previous, factor) {
    current = py2_round(current * factor);
    previous = py2_round(previous * factor);
    var coordinate = current - previous;
    coordinate <<= 1;
    if (current - previous < 0) {
        coordinate = ~coordinate;
    }
    var output = '';
    while (coordinate >= 0x20) {
        output += String.fromCharCode((0x20 | (coordinate & 0x1f)) + 63);
        coordinate >>= 5;
    }
    output += String.fromCharCode(coordinate + 63);
    return output;
}

/**
 * Decodes to a [latitude, longitude] coordinates array.
 *
 * This is adapted from the implementation in Project-OSRM.
 *
 * @param {String} str
 * @param {Number} precision
 * @returns {Array}
 *
 * @see https://github.com/Project-OSRM/osrm-frontend/blob/master/WebContent/routing/OSRM.RoutingGeometry.js
 */
polyline.decode = function(str, precision) {
    var index = 0,
        lat = 0,
        lng = 0,
        coordinates = [],
        shift = 0,
        result = 0,
        byte = null,
        latitude_change,
        longitude_change,
        factor = Math.pow(10, precision || 5);

    // Coordinates have variable length when encoded, so just keep
    // track of whether we've hit the end of the string. In each
    // loop iteration, a single coordinate is decoded.
    while (index < str.length) {

        // Reset shift, result, and byte
        byte = null;
        shift = 0;
        result = 0;

        do {
            byte = str.charCodeAt(index++) - 63;
            result |= (byte & 0x1f) << shift;
            shift += 5;
        } while (byte >= 0x20);

        latitude_change = ((result & 1) ? ~(result >> 1) : (result >> 1));

        shift = result = 0;

        do {
            byte = str.charCodeAt(index++) - 63;
            result |= (byte & 0x1f) << shift;
            shift += 5;
        } while (byte >= 0x20);

        longitude_change = ((result & 1) ? ~(result >> 1) : (result >> 1));

        lat += latitude_change;
        lng += longitude_change;

        coordinates.push([lat / factor, lng / factor]);
    }

    return coordinates;
};

/**
 * Encodes the given [latitude, longitude] coordinates array.
 *
 * @param {Array.<Array.<Number>>} coordinates
 * @param {Number} precision
 * @returns {String}
 */
polyline.encode = function(coordinates, precision) {
    if (!coordinates.length) { return ''; }

    var factor = Math.pow(10, precision || 5),
        output = encode(coordinates[0][0], 0, factor) + encode(coordinates[0][1], 0, factor);

    for (var i = 1; i < coordinates.length; i++) {
        var a = coordinates[i], b = coordinates[i - 1];
        output += encode(a[0], b[0], factor);
        output += encode(a[1], b[1], factor);
    }

    return output;
};

function flipped(coords) {
    var flipped = [];
    for (var i = 0; i < coords.length; i++) {
        flipped.push(coords[i].slice().reverse());
    }
    return flipped;
}

/**
 * Encodes a GeoJSON LineString feature/geometry.
 *
 * @param {Object} geojson
 * @param {Number} precision
 * @returns {String}
 */
polyline.fromGeoJSON = function(geojson, precision) {
    if (geojson && geojson.type === 'Feature') {
        geojson = geojson.geometry;
    }
    if (!geojson || geojson.type !== 'LineString') {
        throw new Error('Input must be a GeoJSON LineString');
    }
    return polyline.encode(flipped(geojson.coordinates), precision);
};

/**
 * Decodes to a GeoJSON LineString geometry.
 *
 * @param {String} str
 * @param {Number} precision
 * @returns {Object}
 */
polyline.toGeoJSON = function(str, precision) {
    var coords = polyline.decode(str, precision);
    return {
        type: 'LineString',
        coordinates: flipped(coords)
    };
};

if (typeof module === 'object' && module.exports) {
    module.exports = polyline;
}

},{}],3:[function(_dereq_,module,exports){
var languages = _dereq_('./languages');
var instructions = languages.instructions;
var grammars = languages.grammars;

module.exports = function(version) {
    Object.keys(instructions).forEach(function(code) {
        if (!instructions[code][version]) { throw 'invalid version ' + version + ': ' + code + ' not supported'; }
    });

    return {
        capitalizeFirstLetter: function(language, string) {
            return string.charAt(0).toLocaleUpperCase(language) + string.slice(1);
        },
        ordinalize: function(language, number) {
            // Transform numbers to their translated ordinalized value
            if (!language) throw new Error('No language code provided');

            return instructions[language][version].constants.ordinalize[number.toString()] || '';
        },
        directionFromDegree: function(language, degree) {
            // Transform degrees to their translated compass direction
            if (!language) throw new Error('No language code provided');
            if (!degree && degree !== 0) {
                // step had no bearing_after degree, ignoring
                return '';
            } else if (degree >= 0 && degree <= 20) {
                return instructions[language][version].constants.direction.north;
            } else if (degree > 20 && degree < 70) {
                return instructions[language][version].constants.direction.northeast;
            } else if (degree >= 70 && degree <= 110) {
                return instructions[language][version].constants.direction.east;
            } else if (degree > 110 && degree < 160) {
                return instructions[language][version].constants.direction.southeast;
            } else if (degree >= 160 && degree <= 200) {
                return instructions[language][version].constants.direction.south;
            } else if (degree > 200 && degree < 250) {
                return instructions[language][version].constants.direction.southwest;
            } else if (degree >= 250 && degree <= 290) {
                return instructions[language][version].constants.direction.west;
            } else if (degree > 290 && degree < 340) {
                return instructions[language][version].constants.direction.northwest;
            } else if (degree >= 340 && degree <= 360) {
                return instructions[language][version].constants.direction.north;
            } else {
                throw new Error('Degree ' + degree + ' invalid');
            }
        },
        laneConfig: function(step) {
            // Reduce any lane combination down to a contracted lane diagram
            if (!step.intersections || !step.intersections[0].lanes) throw new Error('No lanes object');

            var config = [];
            var currentLaneValidity = null;

            step.intersections[0].lanes.forEach(function (lane) {
                if (currentLaneValidity === null || currentLaneValidity !== lane.valid) {
                    if (lane.valid) {
                        config.push('o');
                    } else {
                        config.push('x');
                    }
                    currentLaneValidity = lane.valid;
                }
            });

            return config.join('');
        },
        getWayName: function(language, step, options) {
            var classes = options ? options.classes || [] : [];
            if (typeof step !== 'object') throw new Error('step must be an Object');
            if (!language) throw new Error('No language code provided');
            if (!Array.isArray(classes)) throw new Error('classes must be an Array or undefined');

            var wayName;
            var name = step.name || '';
            var ref = (step.ref || '').split(';')[0];

            // Remove hacks from Mapbox Directions mixing ref into name
            if (name === step.ref) {
                // if both are the same we assume that there used to be an empty name, with the ref being filled in for it
                // we only need to retain the ref then
                name = '';
            }
            name = name.replace(' (' + step.ref + ')', '');

            // In attempt to avoid using the highway name of a way,
            // check and see if the step has a class which should signal
            // the ref should be used instead of the name.
            var wayMotorway = classes.indexOf('motorway') !== -1;

            if (name && ref && name !== ref && !wayMotorway) {
                var phrase = instructions[language][version].phrase['name and ref'] ||
                    instructions.en[version].phrase['name and ref'];
                wayName = this.tokenize(language, phrase, {
                    name: name,
                    ref: ref
                }, options);
            } else if (name && ref && wayMotorway && (/\d/).test(ref)) {
                wayName = ref;
            } else if (!name && ref) {
                wayName = ref;
            } else {
                wayName = name;
            }

            return wayName;
        },
        compile: function(language, step, options) {
            if (!language) throw new Error('No language code provided');
            if (languages.supportedCodes.indexOf(language) === -1) throw new Error('language code ' + language + ' not loaded');
            if (!step.maneuver) throw new Error('No step maneuver provided');

            var type = step.maneuver.type;
            var modifier = step.maneuver.modifier;
            var mode = step.mode;

            if (!type) { throw new Error('Missing step maneuver type'); }
            if (type !== 'depart' && type !== 'arrive' && !modifier) { throw new Error('Missing step maneuver modifier'); }

            if (!instructions[language][version][type]) {
                // Log for debugging
                console.log('Encountered unknown instruction type: ' + type); // eslint-disable-line no-console
                // OSRM specification assumes turn types can be added without
                // major version changes. Unknown types are to be treated as
                // type `turn` by clients
                type = 'turn';
            }

            // Use special instructions if available, otherwise `defaultinstruction`
            var instructionObject;
            if (instructions[language][version].modes[mode]) {
                instructionObject = instructions[language][version].modes[mode];
            } else if (instructions[language][version][type][modifier]) {
                instructionObject = instructions[language][version][type][modifier];
            } else {
                instructionObject = instructions[language][version][type].default;
            }

            // Special case handling
            var laneInstruction;
            switch (type) {
            case 'use lane':
                laneInstruction = instructions[language][version].constants.lanes[this.laneConfig(step)];
                if (!laneInstruction) {
                    // If the lane combination is not found, default to continue straight
                    instructionObject = instructions[language][version]['use lane'].no_lanes;
                }
                break;
            case 'rotary':
            case 'roundabout':
                if (step.rotary_name && step.maneuver.exit && instructionObject.name_exit) {
                    instructionObject = instructionObject.name_exit;
                } else if (step.rotary_name && instructionObject.name) {
                    instructionObject = instructionObject.name;
                } else if (step.maneuver.exit && instructionObject.exit) {
                    instructionObject = instructionObject.exit;
                } else {
                    instructionObject = instructionObject.default;
                }
                break;
            default:
                // NOOP, since no special logic for that type
            }

            // Decide way_name with special handling for name and ref
            var wayName = this.getWayName(language, step, options);

            // Decide which instruction string to use
            // Destination takes precedence over name
            var instruction;
            if (step.destinations && step.exits && instructionObject.exit_destination) {
                instruction = instructionObject.exit_destination;
            } else if (step.destinations && instructionObject.destination) {
                instruction = instructionObject.destination;
            } else if (step.exits && instructionObject.exit) {
                instruction = instructionObject.exit;
            } else if (wayName && instructionObject.name) {
                instruction = instructionObject.name;
            } else {
                instruction = instructionObject.default;
            }

            var nthWaypoint = options && options.legIndex >= 0 && options.legIndex !== options.legCount - 1 ? this.ordinalize(language, options.legIndex + 1) : '';

            // Replace tokens
            // NOOP if they don't exist
            var replaceTokens = {
                'way_name': wayName,
                'destination': (step.destinations || '').split(',')[0],
                'exit': (step.exits || '').split(';')[0],
                'exit_number': this.ordinalize(language, step.maneuver.exit || 1),
                'rotary_name': step.rotary_name,
                'lane_instruction': laneInstruction,
                'modifier': instructions[language][version].constants.modifier[modifier],
                'direction': this.directionFromDegree(language, step.maneuver.bearing_after),
                'nth': nthWaypoint
            };

            return this.tokenize(language, instruction, replaceTokens, options);
        },
        grammarize: function(language, name, grammar) {
            if (!language) throw new Error('No language code provided');
            // Process way/rotary name with applying grammar rules if any
            if (name && grammar && grammars && grammars[language] && grammars[language][version]) {
                var rules = grammars[language][version][grammar];
                if (rules) {
                    // Pass original name to rules' regular expressions enclosed with spaces for simplier parsing
                    var n = ' ' + name + ' ';
                    var flags = grammars[language].meta.regExpFlags || '';
                    rules.forEach(function(rule) {
                        var re = new RegExp(rule[0], flags);
                        n = n.replace(re, rule[1]);
                    });

                    return n.trim();
                }
            }

            return name;
        },
        tokenize: function(language, instruction, tokens, options) {
            if (!language) throw new Error('No language code provided');
            // Keep this function context to use in inline function below (no arrow functions in ES4)
            var that = this;
            var startedWithToken = false;
            var output = instruction.replace(/\{(\w+)(?::(\w+))?\}/g, function(token, tag, grammar, offset) {
                var value = tokens[tag];

                // Return unknown token unchanged
                if (typeof value === 'undefined') {
                    return token;
                }

                value = that.grammarize(language, value, grammar);

                // If this token appears at the beginning of the instruction, capitalize it.
                if (offset === 0 && instructions[language].meta.capitalizeFirstLetter) {
                    startedWithToken = true;
                    value = that.capitalizeFirstLetter(language, value);
                }

                if (options && options.formatToken) {
                    value = options.formatToken(tag, value);
                }

                return value;
            })
            .replace(/ {2}/g, ' '); // remove excess spaces

            if (!startedWithToken && instructions[language].meta.capitalizeFirstLetter) {
                return this.capitalizeFirstLetter(language, output);
            }

            return output;
        },
        getBestMatchingLanguage: function(language) {
            if (languages.instructions[language]) return language;

            var codes = languages.parseLanguageIntoCodes(language);
            var languageCode = codes.language;
            var scriptCode = codes.script;
            var regionCode = codes.region;

            // Same language code and script code (lng-Scpt)
            if (languages.instructions[languageCode + '-' + scriptCode]) {
                return languageCode + '-' + scriptCode;
            }

            // Same language code and region code (lng-CC)
            if (languages.instructions[languageCode + '-' + regionCode]) {
                return languageCode + '-' + regionCode;
            }

            // Same language code (lng)
            if (languages.instructions[languageCode]) {
                return languageCode;
            }

            // Same language code and any script code (lng-Scpx) and the found language contains a script
            var anyScript = languages.parsedSupportedCodes.find(function (language) {
                return language.language === languageCode && language.script;
            });
            if (anyScript) {
                return anyScript.locale;
            }

            // Same language code and any region code (lng-CX)
            var anyCountry = languages.parsedSupportedCodes.find(function (language) {
                return language.language === languageCode && language.region;
            });
            if (anyCountry) {
                return anyCountry.locale;
            }

            return 'en';
        }
    };
};

},{"./languages":4}],4:[function(_dereq_,module,exports){
// Load all language files explicitly to allow integration
// with bundling tools like webpack and browserify
var instructionsDe = _dereq_('./languages/translations/de.json');
var instructionsEn = _dereq_('./languages/translations/en.json');
var instructionsEo = _dereq_('./languages/translations/eo.json');
var instructionsEs = _dereq_('./languages/translations/es.json');
var instructionsEsEs = _dereq_('./languages/translations/es-ES.json');
var instructionsFr = _dereq_('./languages/translations/fr.json');
var instructionsId = _dereq_('./languages/translations/id.json');
var instructionsIt = _dereq_('./languages/translations/it.json');
var instructionsNl = _dereq_('./languages/translations/nl.json');
var instructionsPl = _dereq_('./languages/translations/pl.json');
var instructionsPtBr = _dereq_('./languages/translations/pt-BR.json');
var instructionsRo = _dereq_('./languages/translations/ro.json');
var instructionsRu = _dereq_('./languages/translations/ru.json');
var instructionsSv = _dereq_('./languages/translations/sv.json');
var instructionsTr = _dereq_('./languages/translations/tr.json');
var instructionsUk = _dereq_('./languages/translations/uk.json');
var instructionsVi = _dereq_('./languages/translations/vi.json');
var instructionsZhHans = _dereq_('./languages/translations/zh-Hans.json');

// Load all grammar files
var grammarRu = _dereq_('./languages/grammar/ru.json');

// Create a list of supported codes
var instructions = {
    'de': instructionsDe,
    'en': instructionsEn,
    'eo': instructionsEo,
    'es': instructionsEs,
    'es-ES': instructionsEsEs,
    'fr': instructionsFr,
    'id': instructionsId,
    'it': instructionsIt,
    'nl': instructionsNl,
    'pl': instructionsPl,
    'pt-BR': instructionsPtBr,
    'ro': instructionsRo,
    'ru': instructionsRu,
    'sv': instructionsSv,
    'tr': instructionsTr,
    'uk': instructionsUk,
    'vi': instructionsVi,
    'zh-Hans': instructionsZhHans
};

// Create list of supported grammar
var grammars = {
    'ru': grammarRu
};

function parseLanguageIntoCodes (language) {
    var match = language.match(/(\w\w)(?:-(\w\w\w\w))?(?:-(\w\w))?/i);
    var locale = [];
    if (match[1]) {
        match[1] = match[1].toLowerCase();
        locale.push(match[1]);
    }
    if (match[2]) {
        match[2] = match[2][0].toUpperCase() + match[2].substring(1).toLowerCase();
        locale.push(match[2]);
    }
    if (match[3]) {
        match[3] = match[3].toUpperCase();
        locale.push(match[3]);
    }

    return {
        locale: locale.join('-'),
        language: match[1],
        script: match[2],
        region: match[3]
    };
}

module.exports = {
    supportedCodes: Object.keys(instructions),
    parsedSupportedCodes: Object.keys(instructions).map(function(language) {
        return parseLanguageIntoCodes(language);
    }),
    instructions: instructions,
    grammars: grammars,
    parseLanguageIntoCodes: parseLanguageIntoCodes
};

},{"./languages/grammar/ru.json":5,"./languages/translations/de.json":6,"./languages/translations/en.json":7,"./languages/translations/eo.json":8,"./languages/translations/es-ES.json":9,"./languages/translations/es.json":10,"./languages/translations/fr.json":11,"./languages/translations/id.json":12,"./languages/translations/it.json":13,"./languages/translations/nl.json":14,"./languages/translations/pl.json":15,"./languages/translations/pt-BR.json":16,"./languages/translations/ro.json":17,"./languages/translations/ru.json":18,"./languages/translations/sv.json":19,"./languages/translations/tr.json":20,"./languages/translations/uk.json":21,"./languages/translations/vi.json":22,"./languages/translations/zh-Hans.json":23}],5:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "regExpFlags": ""
    },
    "v5": {
        "accusative": [
            ["^ (\\S+)ая [Аа]ллея ", " $1ую аллею "],
            ["^ (\\S+)ья [Аа]ллея ", " $1ью аллею "],
            ["^ (\\S+)яя [Аа]ллея ", " $1юю аллею "],
            ["^ (\\d+)-я (\\S+)ая [Аа]ллея ", " $1-ю $2ую аллею "],
            ["^ [Аа]ллея ", " аллею "],

            ["^ (\\S+)ая-(\\S+)ая [Уу]лица ", " $1ую-$2ую улицу "],
            ["^ (\\S+)ая [Уу]лица ", " $1ую улицу "],
            ["^ (\\S+)ья [Уу]лица ", " $1ью улицу "],
            ["^ (\\S+)яя [Уу]лица ", " $1юю улицу "],
            ["^ (\\d+)-я (\\S+)ая [Уу]лица ", " $1-ю $2ую улицу "],
            ["^ (\\S+)ая (\\S+)ая [Уу]лица ", " $1ую $2ую улицу "],
            ["^ (\\S+[вн])а [Уу]лица ", " $1у улицу "],
            ["^ (\\S+)ая (\\S+[вн])а [Уу]лица ", " $1ую $2у улицу "],
            ["^ Даньславля [Уу]лица ", " Даньславлю улицу "],
            ["^ Добрыня [Уу]лица ", " Добрыню улицу "],
            ["^ Людогоща [Уу]лица ", " Людогощу улицу "],
            ["^ [Уу]лица ", " улицу "],

            ["^ (\\d+)-я [Лл]иния ", " $1-ю линию "],
            ["^ (\\d+)-(\\d+)-я [Лл]иния ", " $1-$2-ю линию "],
            ["^ (\\S+)ая [Лл]иния ", " $1ую линию "],
            ["^ (\\S+)ья [Лл]иния ", " $1ью линию "],
            ["^ (\\S+)яя [Лл]иния ", " $1юю линию "],
            ["^ (\\d+)-я (\\S+)ая [Лл]иния ", " $1-ю $2ую линию "],
            ["^ [Лл]иния ", " линию "],

            ["^ (\\d+)-(\\d+)-я [Лл]инии ", " $1-$2-ю линии "],

            ["^ (\\S+)ая [Нн]абережная ", " $1ую набережную "],
            ["^ (\\S+)ья [Нн]абережная ", " $1ью набережную "],
            ["^ (\\S+)яя [Нн]абережная ", " $1юю набережную "],
            ["^ (\\d+)-я (\\S+)ая [Нн]абережная ", " $1-ю $2ую набережную "],
            ["^ [Нн]абережная ", " набережную "],

            ["^ (\\S+)ая [Пп]лощадь ", " $1ую площадь "],
            ["^ (\\S+)ья [Пп]лощадь ", " $1ью площадь "],
            ["^ (\\S+)яя [Пп]лощадь ", " $1юю площадь "],
            ["^ (\\S+[вн])а [Пп]лощадь ", " $1у площадь "],
            ["^ (\\d+)-я (\\S+)ая [Пп]лощадь ", " $1-ю $2ую площадь "],
            ["^ [Пп]лощадь ", " площадь "],

            ["^ (\\S+)ая [Ээ]стакада ", " $1ую эстакаду "],
            ["^ (\\S+)ья [Ээ]стакада ", " $1ью эстакаду "],
            ["^ (\\S+)яя [Ээ]стакада ", " $1юю эстакаду "],
            ["^ (\\d+)-я (\\S+)ая [Ээ]стакада ", " $1-ю $2ую эстакаду "],
            ["^ [Ээ]стакада ", " эстакаду "],

            ["^ (\\S+)ая [Мм]агистраль ", " $1ую магистраль "],
            ["^ (\\S+)ья [Мм]агистраль ", " $1ью магистраль "],
            ["^ (\\S+)яя [Мм]агистраль ", " $1юю магистраль "],
            ["^ (\\d+)-я (\\S+)ая [Мм]агистраль ", " $1-ю $2ую магистраль "],
            ["^ [Мм]агистраль ", " магистраль "],

            ["^ (\\S+)ая [Рр]азвязка ", " $1ую развязку "],
            ["^ (\\S+)ья [Рр]азвязка ", " $1ью развязку "],
            ["^ (\\S+)яя [Рр]азвязка ", " $1юю развязку "],
            ["^ (\\d+)-я (\\S+)ая [Рр]азвязка ", " $1-ю $2ую развязку "],
            ["^ [Рр]азвязка ", " развязку "],

            ["^ (\\S+)ая [Тт]расса ", " $1ую трассу "],
            ["^ (\\S+)ья [Тт]расса ", " $1ью трассу "],
            ["^ (\\S+)яя [Тт]расса ", " $1юю трассу "],
            ["^ (\\d+)-я (\\S+)ая [Тт]расса ", " $1-ю $2ую трассу "],
            ["^ [Тт]расса ", " трассу "],

            ["^ (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1ую $2дорогу "],
            ["^ (\\S+)ья ([Аа]вто)?[Дд]орога ", " $1ью $2дорогу "],
            ["^ (\\S+)яя ([Аа]вто)?[Дд]орога ", " $1юю $2дорогу "],
            ["^ (\\d+)-я (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1-ю $2ую $3дорогу "],
            ["^ ([Аа]вто)?[Дд]орога ", " $1дорогу "],

            ["^ (\\S+)ая [Дд]орожка ", " $1ую дорожку "],
            ["^ (\\S+)ья [Дд]орожка ", " $1ью дорожку "],
            ["^ (\\S+)яя [Дд]орожка ", " $1юю дорожку "],
            ["^ (\\d+)-я (\\S+)ая [Дд]орожка ", " $1-ю $2ую дорожку "],
            ["^ [Дд]орожка ", " дорожку "],

            ["^ (\\S+)ая [Кк]оса ", " $1ую косу "]
        ],
        "dative": [
            ["^ (\\S+)ая [Аа]ллея ", " $1ой аллее "],
            ["^ (\\S+)ья [Аа]ллея ", " $1ьей аллее "],
            ["^ (\\S+)яя [Аа]ллея ", " $1ей аллее "],
            ["^ (\\d+)-я (\\S+)ая [Аа]ллея ", " $1-й $2ой аллее "],
            ["^ [Аа]ллея ", " аллее "],

            ["^ (\\S+)ая-(\\S+)ая [Уу]лица ", " $1ой-$2ой улице "],
            ["^ (\\S+)ая [Уу]лица ", " $1ой улице "],
            ["^ (\\S+)ья [Уу]лица ", " $1ьей улице "],
            ["^ (\\S+)яя [Уу]лица ", " $1ей улице "],
            ["^ (\\d+)-я (\\S+)ая [Уу]лица ", " $1-й $2ой улице "],
            ["^ (\\S+)ая (\\S+)ая [Уу]лица ", " $1ой $2ой улице "],
            ["^ (\\S+[вн])а [Уу]лица ", " $1ой улице "],
            ["^ (\\S+)ая (\\S+[вн])а [Уу]лица ", " $1ой $2ой улице "],
            ["^ Даньславля [Уу]лица ", " Даньславлей улице "],
            ["^ Добрыня [Уу]лица ", " Добрыней улице "],
            ["^ Людогоща [Уу]лица ", " Людогощей улице "],
            ["^ [Уу]лица ", " улице "],

            ["^ (\\d+)-я [Лл]иния ", " $1-й линии "],
            ["^ (\\d+)-(\\d+)-я [Лл]иния ", " $1-$2-й линии "],
            ["^ (\\S+)ая [Лл]иния ", " $1ой линии "],
            ["^ (\\S+)ья [Лл]иния ", " $1ьей линии "],
            ["^ (\\S+)яя [Лл]иния ", " $1ей линии "],
            ["^ (\\d+)-я (\\S+)ая [Лл]иния ", " $1-й $2ой линии "],
            ["^ [Лл]иния ", " линии "],

            ["^ (\\d+)-(\\d+)-я [Лл]инии ", " $1-$2-й линиям "],

            ["^ (\\S+)ая [Нн]абережная ", " $1ой набережной "],
            ["^ (\\S+)ья [Нн]абережная ", " $1ьей набережной "],
            ["^ (\\S+)яя [Нн]абережная ", " $1ей набережной "],
            ["^ (\\d+)-я (\\S+)ая [Нн]абережная ", " $1-й $2ой набережной "],
            ["^ [Нн]абережная ", " набережной "],

            ["^ (\\S+)ая [Пп]лощадь ", " $1ой площади "],
            ["^ (\\S+)ья [Пп]лощадь ", " $1ьей площади "],
            ["^ (\\S+)яя [Пп]лощадь ", " $1ей площади "],
            ["^ (\\S+[вн])а [Пп]лощадь ", " $1ой площади "],
            ["^ (\\d+)-я (\\S+)ая [Пп]лощадь ", " $1-й $2ой площади "],
            ["^ [Пп]лощадь ", " площади "],

            ["^ (\\S+)ая [Ээ]стакада ", " $1ой эстакаде "],
            ["^ (\\S+)ья [Ээ]стакада ", " $1ьей эстакаде "],
            ["^ (\\S+)яя [Ээ]стакада ", " $1ей эстакаде "],
            ["^ (\\d+)-я (\\S+)ая [Ээ]стакада ", " $1-й $2ой эстакаде "],
            ["^ [Ээ]стакада ", " эстакаде "],

            ["^ (\\S+)ая [Мм]агистраль ", " $1ой магистрали "],
            ["^ (\\S+)ья [Мм]агистраль ", " $1ьей магистрали "],
            ["^ (\\S+)яя [Мм]агистраль ", " $1ей магистрали "],
            ["^ (\\d+)-я (\\S+)ая [Мм]агистраль ", " $1-й $2ой магистрали "],
            ["^ [Мм]агистраль ", " магистрали "],

            ["^ (\\S+)ая [Рр]азвязка ", " $1ой развязке "],
            ["^ (\\S+)ья [Рр]азвязка ", " $1ьей развязке "],
            ["^ (\\S+)яя [Рр]азвязка ", " $1ей развязке "],
            ["^ (\\d+)-я (\\S+)ая [Рр]азвязка ", " $1-й $2ой развязке "],
            ["^ [Рр]азвязка ", " развязке "],

            ["^ (\\S+)ая [Тт]расса ", " $1ой трассе "],
            ["^ (\\S+)ья [Тт]расса ", " $1ьей трассе "],
            ["^ (\\S+)яя [Тт]расса ", " $1ей трассе "],
            ["^ (\\d+)-я (\\S+)ая [Тт]расса ", " $1-й $2ой трассе "],
            ["^ [Тт]расса ", " трассе "],

            ["^ (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1ой $2дороге "],
            ["^ (\\S+)ья ([Аа]вто)?[Дд]орога ", " $1ьей $2дороге "],
            ["^ (\\S+)яя ([Аа]вто)?[Дд]орога ", " $1ей $2дороге "],
            ["^ (\\d+)-я (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1-й $2ой $3дороге "],
            ["^ ([Аа]вто)?[Дд]орога ", " $1дороге "],

            ["^ (\\S+)ая [Дд]орожка ", " $1ой дорожке "],
            ["^ (\\S+)ья [Дд]орожка ", " $1ьей дорожке "],
            ["^ (\\S+)яя [Дд]орожка ", " $1ей дорожке "],
            ["^ (\\d+)-я (\\S+)ая [Дд]орожка ", " $1-й $2ой дорожке "],
            ["^ [Дд]орожка ", " дорожке "],

            ["^ (\\S+)во [Пп]оле ", " $1ву полю "],
            ["^ (\\S+)ая [Кк]оса ", " $1ой косе "],
            ["^ (\\S+)[иоы]й [Пп]роток ", " $1ому протоку "],

            ["^ (\\S+н)ий [Бб]ульвар ", " $1ему бульвару "],
            ["^ (\\S+)[иоы]й [Бб]ульвар ", " $1ому бульвару "],
            ["^ (\\S+[иы]н) [Бб]ульвар ", " $1у бульвару "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Бб]ульвар ", " $1ому $2ему бульвару "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Бб]ульвар ", " $1ему $2ому бульвару "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Бб]ульвар ", " $1ому $2ому бульвару "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Бб]ульвар ", " $1ому $2у бульвару "],
            ["^ (\\d+)-й (\\S+н)ий [Бб]ульвар ", " $1-му $2ему бульвару "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Бб]ульвар ", " $1-му $2ому бульвару "],
            ["^ (\\d+)-й (\\S+[иы]н) [Бб]ульвар ", " $1-му $2у бульвару "],
            ["^ [Бб]ульвар ", " бульвару "],

            ["^ [Дд]убл[её]р ", " дублёру "],

            ["^ (\\S+н)ий [Зз]аезд ", " $1ему заезду "],
            ["^ (\\S+)[иоы]й [Зз]аезд ", " $1ому заезду "],
            ["^ (\\S+[еёо]в) [Зз]аезд ", " $1у заезду "],
            ["^ (\\S+[иы]н) [Зз]аезд ", " $1у заезду "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Зз]аезд ", " $1ому $2ему заезду "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Зз]аезд ", " $1ему $2ому заезду "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Зз]аезд ", " $1ому $2ому заезду "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Зз]аезд ", " $1ому $2у заезду "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Зз]аезд ", " $1ому $2у заезду "],
            ["^ (\\d+)-й (\\S+н)ий [Зз]аезд ", " $1-му $2ему заезду "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Зз]аезд ", " $1-му $2ому заезду "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Зз]аезд ", " $1-му $2у заезду "],
            ["^ (\\d+)-й (\\S+[иы]н) [Зз]аезд ", " $1-му $2у заезду "],
            ["^ [Зз]аезд ", " заезду "],

            ["^ (\\S+н)ий [Мм]ост ", " $1ему мосту "],
            ["^ (\\S+)[иоы]й [Мм]ост ", " $1ому мосту "],
            ["^ (\\S+[еёо]в) [Мм]ост ", " $1у мосту "],
            ["^ (\\S+[иы]н) [Мм]ост ", " $1у мосту "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Мм]ост ", " $1ому $2ему мосту "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Мм]ост ", " $1ему $2ому мосту "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Мм]ост ", " $1ому $2ому мосту "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Мм]ост ", " $1ому $2у мосту "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Мм]ост ", " $1ому $2у мосту "],
            ["^ (\\d+)-й (\\S+н)ий [Мм]ост ", " $1-му $2ему мосту "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Мм]ост ", " $1-му $2ому мосту "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Мм]ост ", " $1-му $2у мосту "],
            ["^ (\\d+)-й (\\S+[иы]н) [Мм]ост ", " $1-му $2у мосту "],
            ["^ [Мм]ост ", " мосту "],

            ["^ (\\S+н)ий [Оо]бход ", " $1ему обходу "],
            ["^ (\\S+)[иоы]й [Оо]бход ", " $1ому обходу "],
            ["^ [Оо]бход ", " обходу "],

            ["^ (\\S+н)ий [Пп]арк ", " $1ему парку "],
            ["^ (\\S+)[иоы]й [Пп]арк ", " $1ому парку "],
            ["^ (\\S+[иы]н) [Пп]арк ", " $1у парку "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]арк ", " $1ому $2ему парку "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]арк ", " $1ему $2ому парку "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]арк ", " $1ому $2ому парку "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]арк ", " $1ому $2у парку "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]арк ", " $1-му $2ему парку "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]арк ", " $1-му $2ому парку "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]арк ", " $1-му $2у парку "],
            ["^ [Пп]арк ", " парку "],

            ["^ (\\S+)[иоы]й-(\\S+)[иоы]й [Пп]ереулок ", " $1ому-$2ому переулку "],
            ["^ (\\d+)-й (\\S+)[иоы]й-(\\S+)[иоы]й [Пп]ереулок ", " $1-му $2ому-$3ому переулку "],
            ["^ (\\S+н)ий [Пп]ереулок ", " $1ему переулку "],
            ["^ (\\S+)[иоы]й [Пп]ереулок ", " $1ому переулку "],
            ["^ (\\S+[еёо]в) [Пп]ереулок ", " $1у переулку "],
            ["^ (\\S+[иы]н) [Пп]ереулок ", " $1у переулку "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]ереулок ", " $1ому $2ему переулку "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]ереулок ", " $1ему $2ому переулку "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]ереулок ", " $1ому $2ому переулку "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Пп]ереулок ", " $1ому $2у переулку "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]ереулок ", " $1ому $2у переулку "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]ереулок ", " $1-му $2ему переулку "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]ереулок ", " $1-му $2ому переулку "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Пп]ереулок ", " $1-му $2у переулку "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]ереулок ", " $1-му $2у переулку "],
            ["^ [Пп]ереулок ", " переулку "],

            ["^ [Пп]одъезд ", " подъезду "],

            ["^ (\\S+[еёо]в)-(\\S+)[иоы]й [Пп]роезд ", " $1у-$2ому проезду "],
            ["^ (\\S+н)ий [Пп]роезд ", " $1ему проезду "],
            ["^ (\\S+)[иоы]й [Пп]роезд ", " $1ому проезду "],
            ["^ (\\S+[еёо]в) [Пп]роезд ", " $1у проезду "],
            ["^ (\\S+[иы]н) [Пп]роезд ", " $1у проезду "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]роезд ", " $1ому $2ему проезду "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]роезд ", " $1ему $2ому проезду "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]роезд ", " $1ому $2ому проезду "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Пп]роезд ", " $1ому $2у проезду "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]роезд ", " $1ому $2у проезду "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]роезд ", " $1-му $2ему проезду "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]роезд ", " $1-му $2ому проезду "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Пп]роезд ", " $1-му $2у проезду "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]роезд ", " $1-му $2у проезду "],
            ["^ [Пп]роезд ", " проезду "],

            ["^ (\\S+н)ий [Пп]роспект ", " $1ему проспекту "],
            ["^ (\\S+)[иоы]й [Пп]роспект ", " $1ому проспекту "],
            ["^ (\\S+[иы]н) [Пп]роспект ", " $1у проспекту "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]роспект ", " $1ому $2ему проспекту "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]роспект ", " $1ему $2ому проспекту "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]роспект ", " $1ому $2ому проспекту "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]роспект ", " $1ому $2у проспекту "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]роспект ", " $1-му $2ему проспекту "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]роспект ", " $1-му $2ому проспекту "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]роспект ", " $1-му $2у проспекту "],
            ["^ [Пп]роспект ", " проспекту "],

            ["^ (\\S+н)ий [Пп]утепровод ", " $1ему путепроводу "],
            ["^ (\\S+)[иоы]й [Пп]утепровод ", " $1ому путепроводу "],
            ["^ (\\S+[иы]н) [Пп]утепровод ", " $1у путепроводу "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]утепровод ", " $1ому $2ему путепроводу "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]утепровод ", " $1ему $2ому путепроводу "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]утепровод ", " $1ому $2ому путепроводу "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]утепровод ", " $1ому $2у путепроводу "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]утепровод ", " $1-му $2ему путепроводу "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]утепровод ", " $1-му $2ому путепроводу "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]утепровод ", " $1-му $2у путепроводу "],
            ["^ [Пп]утепровод ", " путепроводу "],

            ["^ (\\S+н)ий [Сс]пуск ", " $1ему спуску "],
            ["^ (\\S+)[иоы]й [Сс]пуск ", " $1ому спуску "],
            ["^ (\\S+[еёо]в) [Сс]пуск ", " $1у спуску "],
            ["^ (\\S+[иы]н) [Сс]пуск ", " $1у спуску "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Сс]пуск ", " $1ому $2ему спуску "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Сс]пуск ", " $1ему $2ому спуску "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Сс]пуск ", " $1ому $2ому спуску "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Сс]пуск ", " $1ому $2у спуску "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Сс]пуск ", " $1ому $2у спуску "],
            ["^ (\\d+)-й (\\S+н)ий [Сс]пуск ", " $1-му $2ему спуску "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Сс]пуск ", " $1-му $2ому спуску "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Сс]пуск ", " $1-му $2у спуску "],
            ["^ (\\d+)-й (\\S+[иы]н) [Сс]пуск ", " $1-му $2у спуску "],
            ["^ [Сс]пуск ", " спуску "],

            ["^ (\\S+н)ий [Сс]ъезд ", " $1ему съезду "],
            ["^ (\\S+)[иоы]й [Сс]ъезд ", " $1ому съезду "],
            ["^ (\\S+[иы]н) [Сс]ъезд ", " $1у съезду "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Сс]ъезд ", " $1ому $2ему съезду "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Сс]ъезд ", " $1ему $2ому съезду "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Сс]ъезд ", " $1ому $2ому съезду "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Сс]ъезд ", " $1ому $2у съезду "],
            ["^ (\\d+)-й (\\S+н)ий [Сс]ъезд ", " $1-му $2ему съезду "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Сс]ъезд ", " $1-му $2ому съезду "],
            ["^ (\\d+)-й (\\S+[иы]н) [Сс]ъезд ", " $1-му $2у съезду "],
            ["^ [Сс]ъезд ", " съезду "],

            ["^ (\\S+н)ий [Тт][уо]ннель ", " $1ему тоннелю "],
            ["^ (\\S+)[иоы]й [Тт][уо]ннель ", " $1ому тоннелю "],
            ["^ (\\S+[иы]н) [Тт][уо]ннель ", " $1у тоннелю "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт][уо]ннель ", " $1ому $2ему тоннелю "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт][уо]ннель ", " $1ему $2ому тоннелю "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт][уо]ннель ", " $1ому $2ому тоннелю "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт][уо]ннель ", " $1ому $2у тоннелю "],
            ["^ (\\d+)-й (\\S+н)ий [Тт][уо]ннель ", " $1-му $2ему тоннелю "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт][уо]ннель ", " $1-му $2ому тоннелю "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт][уо]ннель ", " $1-му $2у тоннелю "],
            ["^ [Тт][уо]ннель ", " тоннелю "],

            ["^ (\\S+н)ий [Тт]ракт ", " $1ему тракту "],
            ["^ (\\S+)[иоы]й [Тт]ракт ", " $1ому тракту "],
            ["^ (\\S+[еёо]в) [Тт]ракт ", " $1у тракту "],
            ["^ (\\S+[иы]н) [Тт]ракт ", " $1у тракту "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт]ракт ", " $1ому $2ему тракту "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт]ракт ", " $1ему $2ому тракту "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт]ракт ", " $1ому $2ому тракту "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Тт]ракт ", " $1ому $2у тракту "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт]ракт ", " $1ому $2у тракту "],
            ["^ (\\d+)-й (\\S+н)ий [Тт]ракт ", " $1-му $2ему тракту "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт]ракт ", " $1-му $2ому тракту "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Тт]ракт ", " $1-му $2у тракту "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт]ракт ", " $1-му $2у тракту "],
            ["^ [Тт]ракт ", " тракту "],

            ["^ (\\S+н)ий [Тт]упик ", " $1ему тупику "],
            ["^ (\\S+)[иоы]й [Тт]упик ", " $1ому тупику "],
            ["^ (\\S+[еёо]в) [Тт]упик ", " $1у тупику "],
            ["^ (\\S+[иы]н) [Тт]упик ", " $1у тупику "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт]упик ", " $1ому $2ему тупику "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт]упик ", " $1ему $2ому тупику "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт]упик ", " $1ому $2ому тупику "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Тт]упик ", " $1ому $2у тупику "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт]упик ", " $1ому $2у тупику "],
            ["^ (\\d+)-й (\\S+н)ий [Тт]упик ", " $1-му $2ему тупику "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт]упик ", " $1-му $2ому тупику "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Тт]упик ", " $1-му $2у тупику "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт]упик ", " $1-му $2у тупику "],
            ["^ [Тт]упик ", " тупику "],

            ["^ (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1му $2кольцу "],
            ["^ (\\S+ье) ([Пп]олу)?[Кк]ольцо ", " $1му $2кольцу "],
            ["^ (\\S+[ео])е (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1му $2му $3кольцу "],
            ["^ (\\S+ье) (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1му $2му $3кольцу "],
            ["^ (\\d+)-е (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1му $2му $3кольцу "],
            ["^ (\\d+)-е (\\S+ье) ([Пп]олу)?[Кк]ольцо ", " $1му $2му $3кольцу "],
            ["^ ([Пп]олу)?[Кк]ольцо ", " $1кольцу "],

            ["^ (\\S+[ео])е [Шш]оссе ", " $1му шоссе "],
            ["^ (\\S+ье) [Шш]оссе ", " $1му шоссе "],
            ["^ (\\S+[ео])е (\\S+[ео])е [Шш]оссе ", " $1му $2му шоссе "],
            ["^ (\\S+ье) (\\S+[ео])е [Шш]оссе ", " $1му $2му шоссе "],
            ["^ (\\d+)-е (\\S+[ео])е [Шш]оссе ", " $1му $2му шоссе "],
            ["^ (\\d+)-е (\\S+ье) [Шш]оссе ", " $1му $2му шоссе "],

            [" Третому ", " Третьему "],
            [" третому ", " третьему "],
            ["жому ", "жьему "],
            ["жой ", "жей "],
            ["чому ", "чьему "],
            ["чой ", "чей "]
        ],
        "genitive": [
            ["^ (\\S+)ая [Аа]ллея ", " $1ой аллеи "],
            ["^ (\\S+)ья [Аа]ллея ", " $1ьей аллеи "],
            ["^ (\\S+)яя [Аа]ллея ", " $1ей аллеи "],
            ["^ (\\d+)-я (\\S+)ая [Аа]ллея ", " $1-й $2ой аллеи "],
            ["^ [Аа]ллея ", " аллеи "],

            ["^ (\\S+)ая-(\\S+)ая [Уу]лица ", " $1ой-$2ой улицы "],
            ["^ (\\S+)ая [Уу]лица ", " $1ой улицы "],
            ["^ (\\S+)ья [Уу]лица ", " $1ьей улицы "],
            ["^ (\\S+)яя [Уу]лица ", " $1ей улицы "],
            ["^ (\\d+)-я (\\S+)ая [Уу]лица ", " $1-й $2ой улицы "],
            ["^ (\\S+)ая (\\S+)ая [Уу]лица ", " $1ой $2ой улицы "],
            ["^ (\\S+[вн])а [Уу]лица ", " $1ой улицы "],
            ["^ (\\S+)ая (\\S+[вн])а [Уу]лица ", " $1ой $2ой улицы "],
            ["^ Даньславля [Уу]лица ", " Даньславлей улицы "],
            ["^ Добрыня [Уу]лица ", " Добрыней улицы "],
            ["^ Людогоща [Уу]лица ", " Людогощей улицы "],
            ["^ [Уу]лица ", " улицы "],

            ["^ (\\d+)-я [Лл]иния ", " $1-й линии "],
            ["^ (\\d+)-(\\d+)-я [Лл]иния ", " $1-$2-й линии "],
            ["^ (\\S+)ая [Лл]иния ", " $1ой линии "],
            ["^ (\\S+)ья [Лл]иния ", " $1ьей линии "],
            ["^ (\\S+)яя [Лл]иния ", " $1ей линии "],
            ["^ (\\d+)-я (\\S+)ая [Лл]иния ", " $1-й $2ой линии "],
            ["^ [Лл]иния ", " линии "],

            ["^ (\\d+)-(\\d+)-я [Лл]инии ", " $1-$2-й линий "],

            ["^ (\\S+)ая [Нн]абережная ", " $1ой набережной "],
            ["^ (\\S+)ья [Нн]абережная ", " $1ьей набережной "],
            ["^ (\\S+)яя [Нн]абережная ", " $1ей набережной "],
            ["^ (\\d+)-я (\\S+)ая [Нн]абережная ", " $1-й $2ой набережной "],
            ["^ [Нн]абережная ", " набережной "],

            ["^ (\\S+)ая [Пп]лощадь ", " $1ой площади "],
            ["^ (\\S+)ья [Пп]лощадь ", " $1ьей площади "],
            ["^ (\\S+)яя [Пп]лощадь ", " $1ей площади "],
            ["^ (\\S+[вн])а [Пп]лощадь ", " $1ой площади "],
            ["^ (\\d+)-я (\\S+)ая [Пп]лощадь ", " $1-й $2ой площади "],
            ["^ [Пп]лощадь ", " площади "],

            ["^ (\\S+)ая [Ээ]стакада ", " $1ой эстакады "],
            ["^ (\\S+)ья [Ээ]стакада ", " $1ьей эстакады "],
            ["^ (\\S+)яя [Ээ]стакада ", " $1ей эстакады "],
            ["^ (\\d+)-я (\\S+)ая [Ээ]стакада ", " $1-й $2ой эстакады "],
            ["^ [Ээ]стакада ", " эстакады "],

            ["^ (\\S+)ая [Мм]агистраль ", " $1ой магистрали "],
            ["^ (\\S+)ья [Мм]агистраль ", " $1ьей магистрали "],
            ["^ (\\S+)яя [Мм]агистраль ", " $1ей магистрали "],
            ["^ (\\d+)-я (\\S+)ая [Мм]агистраль ", " $1-й $2ой магистрали "],
            ["^ [Мм]агистраль ", " магистрали "],

            ["^ (\\S+)ая [Рр]азвязка ", " $1ой развязки "],
            ["^ (\\S+)ья [Рр]азвязка ", " $1ьей развязки "],
            ["^ (\\S+)яя [Рр]азвязка ", " $1ей развязки "],
            ["^ (\\d+)-я (\\S+)ая [Рр]азвязка ", " $1-й $2ой развязки "],
            ["^ [Рр]азвязка ", " развязки "],

            ["^ (\\S+)ая [Тт]расса ", " $1ой трассы "],
            ["^ (\\S+)ья [Тт]расса ", " $1ьей трассы "],
            ["^ (\\S+)яя [Тт]расса ", " $1ей трассы "],
            ["^ (\\d+)-я (\\S+)ая [Тт]расса ", " $1-й $2ой трассы "],
            ["^ [Тт]расса ", " трассы "],

            ["^ (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1ой $2дороги "],
            ["^ (\\S+)ья ([Аа]вто)?[Дд]орога ", " $1ьей $2дороги "],
            ["^ (\\S+)яя ([Аа]вто)?[Дд]орога ", " $1ей $2дороги "],
            ["^ (\\d+)-я (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1-й $2ой $3дороги "],
            ["^ ([Аа]вто)?[Дд]орога ", " $1дороги "],

            ["^ (\\S+)ая [Дд]орожка ", " $1ой дорожки "],
            ["^ (\\S+)ья [Дд]орожка ", " $1ьей дорожки "],
            ["^ (\\S+)яя [Дд]орожка ", " $1ей дорожки "],
            ["^ (\\d+)-я (\\S+)ая [Дд]орожка ", " $1-й $2ой дорожки "],
            ["^ [Дд]орожка ", " дорожки "],

            ["^ (\\S+)во [Пп]оле ", " $1ва поля "],
            ["^ (\\S+)ая [Кк]оса ", " $1ой косы "],
            ["^ (\\S+)[иоы]й [Пп]роток ", " $1ого протока "],

            ["^ (\\S+н)ий [Бб]ульвар ", " $1его бульвара "],
            ["^ (\\S+)[иоы]й [Бб]ульвар ", " $1ого бульвара "],
            ["^ (\\S+[иы]н) [Бб]ульвар ", " $1ого бульвара "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Бб]ульвар ", " $1ого $2его бульвара "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Бб]ульвар ", " $1его $2ого бульвара "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Бб]ульвар ", " $1ого $2ого бульвара "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Бб]ульвар ", " $1ого $2ого бульвара "],
            ["^ (\\d+)-й (\\S+н)ий [Бб]ульвар ", " $1-го $2его бульвара "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Бб]ульвар ", " $1-го $2ого бульвара "],
            ["^ (\\d+)-й (\\S+[иы]н) [Бб]ульвар ", " $1-го $2ого бульвара "],
            ["^ [Бб]ульвар ", " бульвара "],

            ["^ [Дд]убл[её]р ", " дублёра "],

            ["^ (\\S+н)ий [Зз]аезд ", " $1его заезда "],
            ["^ (\\S+)[иоы]й [Зз]аезд ", " $1ого заезда "],
            ["^ (\\S+[еёо]в) [Зз]аезд ", " $1а заезда "],
            ["^ (\\S+[иы]н) [Зз]аезд ", " $1а заезда "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Зз]аезд ", " $1ого $2его заезда "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Зз]аезд ", " $1его $2ого заезда "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Зз]аезд ", " $1ого $2ого заезда "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Зз]аезд ", " $1ого $2а заезда "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Зз]аезд ", " $1ого $2а заезда "],
            ["^ (\\d+)-й (\\S+н)ий [Зз]аезд ", " $1-го $2его заезда "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Зз]аезд ", " $1-го $2ого заезда "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Зз]аезд ", " $1-го $2а заезда "],
            ["^ (\\d+)-й (\\S+[иы]н) [Зз]аезд ", " $1-го $2а заезда "],
            ["^ [Зз]аезд ", " заезда "],

            ["^ (\\S+н)ий [Мм]ост ", " $1его моста "],
            ["^ (\\S+)[иоы]й [Мм]ост ", " $1ого моста "],
            ["^ (\\S+[еёо]в) [Мм]ост ", " $1а моста "],
            ["^ (\\S+[иы]н) [Мм]ост ", " $1а моста "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Мм]ост ", " $1ого $2его моста "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Мм]ост ", " $1его $2ого моста "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Мм]ост ", " $1ого $2ого моста "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Мм]ост ", " $1ого $2а моста "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Мм]ост ", " $1ого $2а моста "],
            ["^ (\\d+)-й (\\S+н)ий [Мм]ост ", " $1-го $2его моста "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Мм]ост ", " $1-го $2ого моста "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Мм]ост ", " $1-го $2а моста "],
            ["^ (\\d+)-й (\\S+[иы]н) [Мм]ост ", " $1-го $2а моста "],
            ["^ [Мм]ост ", " моста "],

            ["^ (\\S+н)ий [Оо]бход ", " $1его обхода "],
            ["^ (\\S+)[иоы]й [Оо]бход ", " $1ого обхода "],
            ["^ [Оо]бход ", " обхода "],

            ["^ (\\S+н)ий [Пп]арк ", " $1его парка "],
            ["^ (\\S+)[иоы]й [Пп]арк ", " $1ого парка "],
            ["^ (\\S+[иы]н) [Пп]арк ", " $1ого парка "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]арк ", " $1ого $2его парка "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]арк ", " $1его $2ого парка "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]арк ", " $1ого $2ого парка "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]арк ", " $1ого $2ого парка "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]арк ", " $1-го $2его парка "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]арк ", " $1-го $2ого парка "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]арк ", " $1-го $2ого парка "],
            ["^ [Пп]арк ", " парка "],

            ["^ (\\S+)[иоы]й-(\\S+)[иоы]й [Пп]ереулок ", " $1ого-$2ого переулка "],
            ["^ (\\d+)-й (\\S+)[иоы]й-(\\S+)[иоы]й [Пп]ереулок ", " $1-го $2ого-$3ого переулка "],
            ["^ (\\S+н)ий [Пп]ереулок ", " $1его переулка "],
            ["^ (\\S+)[иоы]й [Пп]ереулок ", " $1ого переулка "],
            ["^ (\\S+[еёо]в) [Пп]ереулок ", " $1а переулка "],
            ["^ (\\S+[иы]н) [Пп]ереулок ", " $1а переулка "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]ереулок ", " $1ого $2его переулка "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]ереулок ", " $1его $2ого переулка "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]ереулок ", " $1ого $2ого переулка "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Пп]ереулок ", " $1ого $2а переулка "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]ереулок ", " $1ого $2а переулка "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]ереулок ", " $1-го $2его переулка "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]ереулок ", " $1-го $2ого переулка "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Пп]ереулок ", " $1-го $2а переулка "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]ереулок ", " $1-го $2а переулка "],
            ["^ [Пп]ереулок ", " переулка "],

            ["^ [Пп]одъезд ", " подъезда "],

            ["^ (\\S+[еёо]в)-(\\S+)[иоы]й [Пп]роезд ", " $1а-$2ого проезда "],
            ["^ (\\S+н)ий [Пп]роезд ", " $1его проезда "],
            ["^ (\\S+)[иоы]й [Пп]роезд ", " $1ого проезда "],
            ["^ (\\S+[еёо]в) [Пп]роезд ", " $1а проезда "],
            ["^ (\\S+[иы]н) [Пп]роезд ", " $1а проезда "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]роезд ", " $1ого $2его проезда "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]роезд ", " $1его $2ого проезда "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]роезд ", " $1ого $2ого проезда "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Пп]роезд ", " $1ого $2а проезда "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]роезд ", " $1ого $2а проезда "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]роезд ", " $1-го $2его проезда "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]роезд ", " $1-го $2ого проезда "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Пп]роезд ", " $1-го $2а проезда "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]роезд ", " $1-го $2а проезда "],
            ["^ [Пп]роезд ", " проезда "],

            ["^ (\\S+н)ий [Пп]роспект ", " $1его проспекта "],
            ["^ (\\S+)[иоы]й [Пп]роспект ", " $1ого проспекта "],
            ["^ (\\S+[иы]н) [Пп]роспект ", " $1ого проспекта "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]роспект ", " $1ого $2его проспекта "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]роспект ", " $1его $2ого проспекта "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]роспект ", " $1ого $2ого проспекта "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]роспект ", " $1ого $2ого проспекта "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]роспект ", " $1-го $2его проспекта "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]роспект ", " $1-го $2ого проспекта "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]роспект ", " $1-го $2ого проспекта "],
            ["^ [Пп]роспект ", " проспекта "],

            ["^ (\\S+н)ий [Пп]утепровод ", " $1его путепровода "],
            ["^ (\\S+)[иоы]й [Пп]утепровод ", " $1ого путепровода "],
            ["^ (\\S+[иы]н) [Пп]утепровод ", " $1ого путепровода "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]утепровод ", " $1ого $2его путепровода "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]утепровод ", " $1его $2ого путепровода "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]утепровод ", " $1ого $2ого путепровода "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]утепровод ", " $1ого $2ого путепровода "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]утепровод ", " $1-го $2его путепровода "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]утепровод ", " $1-го $2ого путепровода "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]утепровод ", " $1-го $2ого путепровода "],
            ["^ [Пп]утепровод ", " путепровода "],

            ["^ (\\S+н)ий [Сс]пуск ", " $1его спуска "],
            ["^ (\\S+)[иоы]й [Сс]пуск ", " $1ого спуска "],
            ["^ (\\S+[еёо]в) [Сс]пуск ", " $1а спуска "],
            ["^ (\\S+[иы]н) [Сс]пуск ", " $1а спуска "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Сс]пуск ", " $1ого $2его спуска "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Сс]пуск ", " $1его $2ого спуска "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Сс]пуск ", " $1ого $2ого спуска "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Сс]пуск ", " $1ого $2а спуска "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Сс]пуск ", " $1ого $2а спуска "],
            ["^ (\\d+)-й (\\S+н)ий [Сс]пуск ", " $1-го $2его спуска "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Сс]пуск ", " $1-го $2ого спуска "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Сс]пуск ", " $1-го $2а спуска "],
            ["^ (\\d+)-й (\\S+[иы]н) [Сс]пуск ", " $1-го $2а спуска "],
            ["^ [Сс]пуск ", " спуска "],

            ["^ (\\S+н)ий [Сс]ъезд ", " $1его съезда "],
            ["^ (\\S+)[иоы]й [Сс]ъезд ", " $1ого съезда "],
            ["^ (\\S+[иы]н) [Сс]ъезд ", " $1ого съезда "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Сс]ъезд ", " $1ого $2его съезда "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Сс]ъезд ", " $1его $2ого съезда "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Сс]ъезд ", " $1ого $2ого съезда "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Сс]ъезд ", " $1ого $2ого съезда "],
            ["^ (\\d+)-й (\\S+н)ий [Сс]ъезд ", " $1-го $2его съезда "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Сс]ъезд ", " $1-го $2ого съезда "],
            ["^ (\\d+)-й (\\S+[иы]н) [Сс]ъезд ", " $1-го $2ого съезда "],
            ["^ [Сс]ъезд ", " съезда "],

            ["^ (\\S+н)ий [Тт][уо]ннель ", " $1его тоннеля "],
            ["^ (\\S+)[иоы]й [Тт][уо]ннель ", " $1ого тоннеля "],
            ["^ (\\S+[иы]н) [Тт][уо]ннель ", " $1ого тоннеля "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт][уо]ннель ", " $1ого $2его тоннеля "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт][уо]ннель ", " $1его $2ого тоннеля "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт][уо]ннель ", " $1ого $2ого тоннеля "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт][уо]ннель ", " $1ого $2ого тоннеля "],
            ["^ (\\d+)-й (\\S+н)ий [Тт][уо]ннель ", " $1-го $2его тоннеля "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт][уо]ннель ", " $1-го $2ого тоннеля "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт][уо]ннель ", " $1-го $2ого тоннеля "],
            ["^ [Тт][уо]ннель ", " тоннеля "],

            ["^ (\\S+н)ий [Тт]ракт ", " $1ем тракта "],
            ["^ (\\S+)[иоы]й [Тт]ракт ", " $1ого тракта "],
            ["^ (\\S+[еёо]в) [Тт]ракт ", " $1а тракта "],
            ["^ (\\S+[иы]н) [Тт]ракт ", " $1а тракта "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт]ракт ", " $1ого $2его тракта "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт]ракт ", " $1его $2ого тракта "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт]ракт ", " $1ого $2ого тракта "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Тт]ракт ", " $1ого $2а тракта "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт]ракт ", " $1ого $2а тракта "],
            ["^ (\\d+)-й (\\S+н)ий [Тт]ракт ", " $1-го $2его тракта "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт]ракт ", " $1-го $2ого тракта "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Тт]ракт ", " $1-го $2а тракта "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт]ракт ", " $1-го $2а тракта "],
            ["^ [Тт]ракт ", " тракта "],

            ["^ (\\S+н)ий [Тт]упик ", " $1его тупика "],
            ["^ (\\S+)[иоы]й [Тт]упик ", " $1ого тупика "],
            ["^ (\\S+[еёо]в) [Тт]упик ", " $1а тупика "],
            ["^ (\\S+[иы]н) [Тт]упик ", " $1а тупика "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт]упик ", " $1ого $2его тупика "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт]упик ", " $1его $2ого тупика "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт]упик ", " $1ого $2ого тупика "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Тт]упик ", " $1ого $2а тупика "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт]упик ", " $1ого $2а тупика "],
            ["^ (\\d+)-й (\\S+н)ий [Тт]упик ", " $1-го $2его тупика "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт]упик ", " $1-го $2ого тупика "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Тт]упик ", " $1-го $2а тупика "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт]упик ", " $1-го $2а тупика "],
            ["^ [Тт]упик ", " тупика "],

            ["^ (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1го $2кольца "],
            ["^ (\\S+ье) ([Пп]олу)?[Кк]ольцо ", " $1го $2кольца "],
            ["^ (\\S+[ео])е (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1го $2го $3кольца "],
            ["^ (\\S+ье) (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1го $2го $3кольца "],
            ["^ (\\d+)-е (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1го $2го $3кольца "],
            ["^ (\\d+)-е (\\S+ье) ([Пп]олу)?[Кк]ольцо ", " $1го $2го $3кольца "],
            ["^ ([Пп]олу)?[Кк]ольцо ", " $1кольца "],

            ["^ (\\S+[ео])е [Шш]оссе ", " $1го шоссе "],
            ["^ (\\S+ье) [Шш]оссе ", " $1го шоссе "],
            ["^ (\\S+[ео])е (\\S+[ео])е [Шш]оссе ", " $1го $2го шоссе "],
            ["^ (\\S+ье) (\\S+[ео])е [Шш]оссе ", " $1го $2го шоссе "],
            ["^ (\\d+)-е (\\S+[ео])е [Шш]оссе ", " $1го $2го шоссе "],
            ["^ (\\d+)-е (\\S+ье) [Шш]оссе ", " $1го $2го шоссе "],

            [" Третого ", " Третьего "],
            [" третого ", " третьего "],
            ["жого ", "жьего "],
            ["чого ", "чьего "]
        ],
        "prepositional": [
            ["^ (\\S+)ая [Аа]ллея ", " $1ой аллее "],
            ["^ (\\S+)ья [Аа]ллея ", " $1ьей аллее "],
            ["^ (\\S+)яя [Аа]ллея ", " $1ей аллее "],
            ["^ (\\d+)-я (\\S+)ая [Аа]ллея ", " $1-й $2ой аллее "],
            ["^ [Аа]ллея ", " аллее "],

            ["^ (\\S+)ая-(\\S+)ая [Уу]лица ", " $1ой-$2ой улице "],
            ["^ (\\S+)ая [Уу]лица ", " $1ой улице "],
            ["^ (\\S+)ья [Уу]лица ", " $1ьей улице "],
            ["^ (\\S+)яя [Уу]лица ", " $1ей улице "],
            ["^ (\\d+)-я (\\S+)ая [Уу]лица ", " $1-й $2ой улице "],
            ["^ (\\S+)ая (\\S+)ая [Уу]лица ", " $1ой $2ой улице "],
            ["^ (\\S+[вн])а [Уу]лица ", " $1ой улице "],
            ["^ (\\S+)ая (\\S+[вн])а [Уу]лица ", " $1ой $2ой улице "],
            ["^ Даньславля [Уу]лица ", " Даньславлей улице "],
            ["^ Добрыня [Уу]лица ", " Добрыней улице "],
            ["^ Людогоща [Уу]лица ", " Людогощей улице "],
            ["^ [Уу]лица ", " улице "],

            ["^ (\\d+)-я [Лл]иния ", " $1-й линии "],
            ["^ (\\d+)-(\\d+)-я [Лл]иния ", " $1-$2-й линии "],
            ["^ (\\S+)ая [Лл]иния ", " $1ой линии "],
            ["^ (\\S+)ья [Лл]иния ", " $1ьей линии "],
            ["^ (\\S+)яя [Лл]иния ", " $1ей линии "],
            ["^ (\\d+)-я (\\S+)ая [Лл]иния ", " $1-й $2ой линии "],
            ["^ [Лл]иния ", " линии "],

            ["^ (\\d+)-(\\d+)-я [Лл]инии ", " $1-$2-й линиях "],

            ["^ (\\S+)ая [Нн]абережная ", " $1ой набережной "],
            ["^ (\\S+)ья [Нн]абережная ", " $1ьей набережной "],
            ["^ (\\S+)яя [Нн]абережная ", " $1ей набережной "],
            ["^ (\\d+)-я (\\S+)ая [Нн]абережная ", " $1-й $2ой набережной "],
            ["^ [Нн]абережная ", " набережной "],

            ["^ (\\S+)ая [Пп]лощадь ", " $1ой площади "],
            ["^ (\\S+)ья [Пп]лощадь ", " $1ьей площади "],
            ["^ (\\S+)яя [Пп]лощадь ", " $1ей площади "],
            ["^ (\\S+[вн])а [Пп]лощадь ", " $1ой площади "],
            ["^ (\\d+)-я (\\S+)ая [Пп]лощадь ", " $1-й $2ой площади "],
            ["^ [Пп]лощадь ", " площади "],

            ["^ (\\S+)ая [Ээ]стакада ", " $1ой эстакаде "],
            ["^ (\\S+)ья [Ээ]стакада ", " $1ьей эстакаде "],
            ["^ (\\S+)яя [Ээ]стакада ", " $1ей эстакаде "],
            ["^ (\\d+)-я (\\S+)ая [Ээ]стакада ", " $1-й $2ой эстакаде "],
            ["^ [Ээ]стакада ", " эстакаде "],

            ["^ (\\S+)ая [Мм]агистраль ", " $1ой магистрали "],
            ["^ (\\S+)ья [Мм]агистраль ", " $1ьей магистрали "],
            ["^ (\\S+)яя [Мм]агистраль ", " $1ей магистрали "],
            ["^ (\\d+)-я (\\S+)ая [Мм]агистраль ", " $1-й $2ой магистрали "],
            ["^ [Мм]агистраль ", " магистрали "],

            ["^ (\\S+)ая [Рр]азвязка ", " $1ой развязке "],
            ["^ (\\S+)ья [Рр]азвязка ", " $1ьей развязке "],
            ["^ (\\S+)яя [Рр]азвязка ", " $1ей развязке "],
            ["^ (\\d+)-я (\\S+)ая [Рр]азвязка ", " $1-й $2ой развязке "],
            ["^ [Рр]азвязка ", " развязке "],

            ["^ (\\S+)ая [Тт]расса ", " $1ой трассе "],
            ["^ (\\S+)ья [Тт]расса ", " $1ьей трассе "],
            ["^ (\\S+)яя [Тт]расса ", " $1ей трассе "],
            ["^ (\\d+)-я (\\S+)ая [Тт]расса ", " $1-й $2ой трассе "],
            ["^ [Тт]расса ", " трассе "],

            ["^ (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1ой $2дороге "],
            ["^ (\\S+)ья ([Аа]вто)?[Дд]орога ", " $1ьей $2дороге "],
            ["^ (\\S+)яя ([Аа]вто)?[Дд]орога ", " $1ей $2дороге "],
            ["^ (\\d+)-я (\\S+)ая ([Аа]вто)?[Дд]орога ", " $1-й $2ой $3дороге "],
            ["^ ([Аа]вто)?[Дд]орога ", " $1дороге "],

            ["^ (\\S+)ая [Дд]орожка ", " $1ой дорожке "],
            ["^ (\\S+)ья [Дд]орожка ", " $1ьей дорожке "],
            ["^ (\\S+)яя [Дд]орожка ", " $1ей дорожке "],
            ["^ (\\d+)-я (\\S+)ая [Дд]орожка ", " $1-й $2ой дорожке "],
            ["^ [Дд]орожка ", " дорожке "],

            ["^ (\\S+)во [Пп]оле ", " $1ве поле "],
            ["^ (\\S+)ая [Кк]оса ", " $1ой косе "],
            ["^ (\\S+)[иоы]й [Пп]роток ", " $1ом протоке "],

            ["^ (\\S+н)ий [Бб]ульвар ", " $1ем бульваре "],
            ["^ (\\S+)[иоы]й [Бб]ульвар ", " $1ом бульваре "],
            ["^ (\\S+[иы]н) [Бб]ульвар ", " $1ом бульваре "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Бб]ульвар ", " $1ом $2ем бульваре "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Бб]ульвар ", " $1ем $2ом бульваре "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Бб]ульвар ", " $1ом $2ом бульваре "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Бб]ульвар ", " $1ом $2ом бульваре "],
            ["^ (\\d+)-й (\\S+н)ий [Бб]ульвар ", " $1-м $2ем бульваре "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Бб]ульвар ", " $1-м $2ом бульваре "],
            ["^ (\\d+)-й (\\S+[иы]н) [Бб]ульвар ", " $1-м $2ом бульваре "],
            ["^ [Бб]ульвар ", " бульваре "],

            ["^ [Дд]убл[её]р ", " дублёре "],

            ["^ (\\S+н)ий [Зз]аезд ", " $1ем заезде "],
            ["^ (\\S+)[иоы]й [Зз]аезд ", " $1ом заезде "],
            ["^ (\\S+[еёо]в) [Зз]аезд ", " $1ом заезде "],
            ["^ (\\S+[иы]н) [Зз]аезд ", " $1ом заезде "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Зз]аезд ", " $1ом $2ем заезде "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Зз]аезд ", " $1ем $2ом заезде "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Зз]аезд ", " $1ом $2ом заезде "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Зз]аезд ", " $1ом $2ом заезде "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Зз]аезд ", " $1ом $2ом заезде "],
            ["^ (\\d+)-й (\\S+н)ий [Зз]аезд ", " $1-м $2ем заезде "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Зз]аезд ", " $1-м $2ом заезде "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Зз]аезд ", " $1-м $2ом заезде "],
            ["^ (\\d+)-й (\\S+[иы]н) [Зз]аезд ", " $1-м $2ом заезде "],
            ["^ [Зз]аезд ", " заезде "],

            ["^ (\\S+н)ий [Мм]ост ", " $1ем мосту "],
            ["^ (\\S+)[иоы]й [Мм]ост ", " $1ом мосту "],
            ["^ (\\S+[еёо]в) [Мм]ост ", " $1ом мосту "],
            ["^ (\\S+[иы]н) [Мм]ост ", " $1ом мосту "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Мм]ост ", " $1ом $2ем мосту "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Мм]ост ", " $1ем $2ом мосту "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Мм]ост ", " $1ом $2ом мосту "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Мм]ост ", " $1ом $2ом мосту "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Мм]ост ", " $1ом $2ом мосту "],
            ["^ (\\d+)-й (\\S+н)ий [Мм]ост ", " $1-м $2ем мосту "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Мм]ост ", " $1-м $2ом мосту "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Мм]ост ", " $1-м $2ом мосту "],
            ["^ (\\d+)-й (\\S+[иы]н) [Мм]ост ", " $1-м $2ом мосту "],
            ["^ [Мм]ост ", " мосту "],

            ["^ (\\S+н)ий [Оо]бход ", " $1ем обходе "],
            ["^ (\\S+)[иоы]й [Оо]бход ", " $1ом обходе "],
            ["^ [Оо]бход ", " обходе "],

            ["^ (\\S+н)ий [Пп]арк ", " $1ем парке "],
            ["^ (\\S+)[иоы]й [Пп]арк ", " $1ом парке "],
            ["^ (\\S+[иы]н) [Пп]арк ", " $1ом парке "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]арк ", " $1ом $2ем парке "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]арк ", " $1ем $2ом парке "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]арк ", " $1ом $2ом парке "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]арк ", " $1ом $2ом парке "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]арк ", " $1-м $2ем парке "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]арк ", " $1-м $2ом парке "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]арк ", " $1-м $2ом парке "],
            ["^ [Пп]арк ", " парке "],

            ["^ (\\S+)[иоы]й-(\\S+)[иоы]й [Пп]ереулок ", " $1ом-$2ом переулке "],
            ["^ (\\d+)-й (\\S+)[иоы]й-(\\S+)[иоы]й [Пп]ереулок ", " $1-м $2ом-$3ом переулке "],
            ["^ (\\S+н)ий [Пп]ереулок ", " $1ем переулке "],
            ["^ (\\S+)[иоы]й [Пп]ереулок ", " $1ом переулке "],
            ["^ (\\S+[еёо]в) [Пп]ереулок ", " $1ом переулке "],
            ["^ (\\S+[иы]н) [Пп]ереулок ", " $1ом переулке "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]ереулок ", " $1ом $2ем переулке "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]ереулок ", " $1ем $2ом переулке "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]ереулок ", " $1ом $2ом переулке "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Пп]ереулок ", " $1ом $2ом переулке "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]ереулок ", " $1ом $2ом переулке "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]ереулок ", " $1-м $2ем переулке "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]ереулок ", " $1-м $2ом переулке "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Пп]ереулок ", " $1-м $2ом переулке "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]ереулок ", " $1-м $2ом переулке "],
            ["^ [Пп]ереулок ", " переулке "],

            ["^ [Пп]одъезд ", " подъезде "],

            ["^ (\\S+[еёо]в)-(\\S+)[иоы]й [Пп]роезд ", " $1ом-$2ом проезде "],
            ["^ (\\S+н)ий [Пп]роезд ", " $1ем проезде "],
            ["^ (\\S+)[иоы]й [Пп]роезд ", " $1ом проезде "],
            ["^ (\\S+[еёо]в) [Пп]роезд ", " $1ом проезде "],
            ["^ (\\S+[иы]н) [Пп]роезд ", " $1ом проезде "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]роезд ", " $1ом $2ем проезде "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]роезд ", " $1ем $2ом проезде "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]роезд ", " $1ом $2ом проезде "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Пп]роезд ", " $1ом $2ом проезде "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]роезд ", " $1ом $2ом проезде "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]роезд ", " $1-м $2ем проезде "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]роезд ", " $1-м $2ом проезде "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Пп]роезд ", " $1-м $2ом проезде "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]роезд ", " $1-м $2ом проезде "],
            ["^ [Пп]роезд ", " проезде "],

            ["^ (\\S+н)ий [Пп]роспект ", " $1ем проспекте "],
            ["^ (\\S+)[иоы]й [Пп]роспект ", " $1ом проспекте "],
            ["^ (\\S+[иы]н) [Пп]роспект ", " $1ом проспекте "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]роспект ", " $1ом $2ем проспекте "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]роспект ", " $1ем $2ом проспекте "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]роспект ", " $1ом $2ом проспекте "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]роспект ", " $1ом $2ом проспекте "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]роспект ", " $1-м $2ем проспекте "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]роспект ", " $1-м $2ом проспекте "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]роспект ", " $1-м $2ом проспекте "],
            ["^ [Пп]роспект ", " проспекте "],

            ["^ (\\S+н)ий [Пп]утепровод ", " $1ем путепроводе "],
            ["^ (\\S+)[иоы]й [Пп]утепровод ", " $1ом путепроводе "],
            ["^ (\\S+[иы]н) [Пп]утепровод ", " $1ом путепроводе "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Пп]утепровод ", " $1ом $2ем путепроводе "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Пп]утепровод ", " $1ем $2ом путепроводе "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Пп]утепровод ", " $1ом $2ом путепроводе "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Пп]утепровод ", " $1ом $2ом путепроводе "],
            ["^ (\\d+)-й (\\S+н)ий [Пп]утепровод ", " $1-м $2ем путепроводе "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Пп]утепровод ", " $1-м $2ом путепроводе "],
            ["^ (\\d+)-й (\\S+[иы]н) [Пп]утепровод ", " $1-м $2ом путепроводе "],
            ["^ [Пп]утепровод ", " путепроводе "],

            ["^ (\\S+н)ий [Сс]пуск ", " $1ем спуске "],
            ["^ (\\S+)[иоы]й [Сс]пуск ", " $1ом спуске "],
            ["^ (\\S+[еёо]в) [Сс]пуск ", " $1ом спуске "],
            ["^ (\\S+[иы]н) [Сс]пуск ", " $1ом спуске "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Сс]пуск ", " $1ом $2ем спуске "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Сс]пуск ", " $1ем $2ом спуске "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Сс]пуск ", " $1ом $2ом спуске "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Сс]пуск ", " $1ом $2ом спуске "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Сс]пуск ", " $1ом $2ом спуске "],
            ["^ (\\d+)-й (\\S+н)ий [Сс]пуск ", " $1-м $2ем спуске "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Сс]пуск ", " $1-м $2ом спуске "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Сс]пуск ", " $1-м $2ом спуске "],
            ["^ (\\d+)-й (\\S+[иы]н) [Сс]пуск ", " $1-м $2ом спуске "],
            ["^ [Сс]пуск ", " спуске "],

            ["^ (\\S+н)ий [Сс]ъезд ", " $1ем съезде "],
            ["^ (\\S+)[иоы]й [Сс]ъезд ", " $1ом съезде "],
            ["^ (\\S+[иы]н) [Сс]ъезд ", " $1ом съезде "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Сс]ъезд ", " $1ом $2ем съезде "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Сс]ъезд ", " $1ем $2ом съезде "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Сс]ъезд ", " $1ом $2ом съезде "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Сс]ъезд ", " $1ом $2ом съезде "],
            ["^ (\\d+)-й (\\S+н)ий [Сс]ъезд ", " $1-м $2ем съезде "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Сс]ъезд ", " $1-м $2ом съезде "],
            ["^ (\\d+)-й (\\S+[иы]н) [Сс]ъезд ", " $1-м $2ом съезде "],
            ["^ [Сс]ъезд ", " съезде "],

            ["^ (\\S+н)ий [Тт][уо]ннель ", " $1ем тоннеле "],
            ["^ (\\S+)[иоы]й [Тт][уо]ннель ", " $1ом тоннеле "],
            ["^ (\\S+[иы]н) [Тт][уо]ннель ", " $1ом тоннеле "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт][уо]ннель ", " $1ом $2ем тоннеле "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт][уо]ннель ", " $1ем $2ом тоннеле "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт][уо]ннель ", " $1ом $2ом тоннеле "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт][уо]ннель ", " $1ом $2ом тоннеле "],
            ["^ (\\d+)-й (\\S+н)ий [Тт][уо]ннель ", " $1-м $2ем тоннеле "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт][уо]ннель ", " $1-м $2ом тоннеле "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт][уо]ннель ", " $1-м $2ом тоннеле "],
            ["^ [Тт][уо]ннель ", " тоннеле "],

            ["^ (\\S+н)ий [Тт]ракт ", " $1ем тракте "],
            ["^ (\\S+)[иоы]й [Тт]ракт ", " $1ом тракте "],
            ["^ (\\S+[еёо]в) [Тт]ракт ", " $1ом тракте "],
            ["^ (\\S+[иы]н) [Тт]ракт ", " $1ом тракте "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт]ракт ", " $1ом $2ем тракте "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт]ракт ", " $1ем $2ом тракте "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт]ракт ", " $1ом $2ом тракте "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Тт]ракт ", " $1ом $2ом тракте "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт]ракт ", " $1ом $2ом тракте "],
            ["^ (\\d+)-й (\\S+н)ий [Тт]ракт ", " $1-м $2ем тракте "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт]ракт ", " $1-м $2ом тракте "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Тт]ракт ", " $1-м $2ом тракте "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт]ракт ", " $1-м $2ом тракте "],
            ["^ [Тт]ракт ", " тракте "],

            ["^ (\\S+н)ий [Тт]упик ", " $1ем тупике "],
            ["^ (\\S+)[иоы]й [Тт]упик ", " $1ом тупике "],
            ["^ (\\S+[еёо]в) [Тт]упик ", " $1ом тупике "],
            ["^ (\\S+[иы]н) [Тт]упик ", " $1ом тупике "],
            ["^ (\\S+)[иоы]й (\\S+н)ий [Тт]упик ", " $1ом $2ем тупике "],
            ["^ (\\S+н)ий (\\S+)[иоы]й [Тт]упик ", " $1ем $2ом тупике "],
            ["^ (\\S+)[иоы]й (\\S+)[иоы]й [Тт]упик ", " $1ом $2ом тупике "],
            ["^ (\\S+)[иоы]й (\\S+[еёо]в) [Тт]упик ", " $1ом $2ом тупике "],
            ["^ (\\S+)[иоы]й (\\S+[иы]н) [Тт]упик ", " $1ом $2ом тупике "],
            ["^ (\\d+)-й (\\S+н)ий [Тт]упик ", " $1-м $2ем тупике "],
            ["^ (\\d+)-й (\\S+)[иоы]й [Тт]упик ", " $1-м $2ом тупике "],
            ["^ (\\d+)-й (\\S+[еёо]в) [Тт]упик ", " $1-м $2ом тупике "],
            ["^ (\\d+)-й (\\S+[иы]н) [Тт]упик ", " $1-м $2ом тупике "],
            ["^ [Тт]упик ", " тупике "],

            ["^ (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1м $2кольце "],
            ["^ (\\S+ье) ([Пп]олу)?[Кк]ольцо ", " $1м $2кольце "],
            ["^ (\\S+[ео])е (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1м $2м $3кольце "],
            ["^ (\\S+ье) (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1м $2м $3кольце "],
            ["^ (\\d+)-е (\\S+[ео])е ([Пп]олу)?[Кк]ольцо ", " $1м $2м $3кольце "],
            ["^ (\\d+)-е (\\S+ье) ([Пп]олу)?[Кк]ольцо ", " $1м $2м $3кольце "],
            ["^ ([Пп]олу)?[Кк]ольцо ", " $1кольце "],

            ["^ (\\S+[ео])е [Шш]оссе ", " $1м шоссе "],
            ["^ (\\S+ье) [Шш]оссе ", " $1м шоссе "],
            ["^ (\\S+[ео])е (\\S+[ео])е [Шш]оссе ", " $1м $2м шоссе "],
            ["^ (\\S+ье) (\\S+[ео])е [Шш]оссе ", " $1м $2м шоссе "],
            ["^ (\\d+)-е (\\S+[ео])е [Шш]оссе ", " $1м $2м шоссе "],
            ["^ (\\d+)-е (\\S+ье) [Шш]оссе ", " $1м $2м шоссе "],

            [" Третом ", " Третьем "],
            [" третом ", " третьем "],
            ["жом ", "жьем "],
            ["чом ", "чьем "]
        ]
    }
}

},{}],6:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "erste",
                "2": "zweite",
                "3": "dritte",
                "4": "vierte",
                "5": "fünfte",
                "6": "sechste",
                "7": "siebente",
                "8": "achte",
                "9": "neunte",
                "10": "zehnte"
            },
            "direction": {
                "north": "Norden",
                "northeast": "Nordosten",
                "east": "Osten",
                "southeast": "Südosten",
                "south": "Süden",
                "southwest": "Südwesten",
                "west": "Westen",
                "northwest": "Nordwesten"
            },
            "modifier": {
                "left": "links",
                "right": "rechts",
                "sharp left": "scharf links",
                "sharp right": "scharf rechts",
                "slight left": "leicht links",
                "slight right": "leicht rechts",
                "straight": "geradeaus",
                "uturn": "180°-Wendung"
            },
            "lanes": {
                "xo": "Rechts halten",
                "ox": "Links halten",
                "xox": "Mittlere Spur nutzen",
                "oxo": "Rechts oder links halten"
            }
        },
        "modes": {
            "ferry": {
                "default": "Fähre nehmen",
                "name": "Fähre nehmen {way_name}",
                "destination": "Fähre nehmen Richtung {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} danach in {distance} {instruction_two}",
            "two linked": "{instruction_one} danach {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Sie haben Ihr {nth} Ziel erreicht"
            },
            "left": {
                "default": "Sie haben Ihr {nth} Ziel erreicht, es befindet sich links"
            },
            "right": {
                "default": "Sie haben Ihr {nth} Ziel erreicht, es befindet sich rechts"
            },
            "sharp left": {
                "default": "Sie haben Ihr {nth} Ziel erreicht, es befindet sich links"
            },
            "sharp right": {
                "default": "Sie haben Ihr {nth} Ziel erreicht, es befindet sich rechts"
            },
            "slight right": {
                "default": "Sie haben Ihr {nth} Ziel erreicht, es befindet sich rechts"
            },
            "slight left": {
                "default": "Sie haben Ihr {nth} Ziel erreicht, es befindet sich links"
            },
            "straight": {
                "default": "Sie haben Ihr {nth} Ziel erreicht, es befindet sich geradeaus"
            }
        },
        "continue": {
            "default": {
                "default": "{modifier} abbiegen",
                "name": "{modifier} weiterfahren auf {way_name}",
                "destination": "{modifier} abbiegen Richtung {destination}",
                "exit": "{modifier} abbiegen auf {way_name}"
            },
            "straight": {
                "default": "Geradeaus weiterfahren",
                "name": "Geradeaus weiterfahren auf {way_name}",
                "destination": "Weiterfahren in Richtung {destination}",
                "distance": "Geradeaus weiterfahren für {distance}",
                "namedistance": "Geradeaus weiterfahren auf {way_name} für {distance}"
            },
            "sharp left": {
                "default": "Scharf links",
                "name": "Scharf links weiterfahren auf {way_name}",
                "destination": "Scharf links Richtung {destination}"
            },
            "sharp right": {
                "default": "Scharf rechts",
                "name": "Scharf rechts weiterfahren auf {way_name}",
                "destination": "Scharf rechts Richtung {destination}"
            },
            "slight left": {
                "default": "Leicht links",
                "name": "Leicht links weiter auf {way_name}",
                "destination": "Leicht links weiter Richtung {destination}"
            },
            "slight right": {
                "default": "Leicht rechts weiter",
                "name": "Leicht rechts weiter auf {way_name}",
                "destination": "Leicht rechts weiter Richtung {destination}"
            },
            "uturn": {
                "default": "180°-Wendung",
                "name": "180°-Wendung auf {way_name}",
                "destination": "180°-Wendung Richtung {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Fahren Sie Richtung {direction}",
                "name": "Fahren Sie Richtung {direction} auf {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "{modifier} abbiegen",
                "name": "{modifier} abbiegen auf {way_name}",
                "destination": "{modifier} abbiegen Richtung {destination}"
            },
            "straight": {
                "default": "Geradeaus weiterfahren",
                "name": "Geradeaus weiterfahren auf {way_name}",
                "destination": "Geradeaus weiterfahren Richtung {destination}"
            },
            "uturn": {
                "default": "180°-Wendung am Ende der Straße",
                "name": "180°-Wendung auf {way_name} am Ende der Straße",
                "destination": "180°-Wendung Richtung {destination} am Ende der Straße"
            }
        },
        "fork": {
            "default": {
                "default": "{modifier} halten an der Gabelung",
                "name": "{modifier} halten an der Gabelung auf {way_name}",
                "destination": "{modifier}  halten an der Gabelung Richtung {destination}"
            },
            "slight left": {
                "default": "Links halten an der Gabelung",
                "name": "Links halten an der Gabelung auf {way_name}",
                "destination": "Links halten an der Gabelung Richtung {destination}"
            },
            "slight right": {
                "default": "Rechts halten an der Gabelung",
                "name": "Rechts halten an der Gabelung auf {way_name}",
                "destination": "Rechts halten an der Gabelung Richtung {destination}"
            },
            "sharp left": {
                "default": "Scharf links abbiegen an der Gabelung",
                "name": "Scharf links abbiegen an der Gabelung auf {way_name}",
                "destination": "Scharf links abbiegen an der Gabelung Richtung {destination}"
            },
            "sharp right": {
                "default": "Scharf rechts abbiegen an der Gabelung",
                "name": "Scharf rechts abbiegen an der Gabelung auf {way_name}",
                "destination": "Scharf rechts abbiegen an der Gabelung Richtung {destination}"
            },
            "uturn": {
                "default": "180°-Wendung",
                "name": "180°-Wendung auf {way_name}",
                "destination": "180°-Wendung Richtung {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "{modifier} auffahren",
                "name": "{modifier} auffahren auf {way_name}",
                "destination": "{modifier} auffahren Richtung {destination}"
            },
            "slight left": {
                "default": "Leicht links auffahren",
                "name": "Leicht links auffahren auf {way_name}",
                "destination": "Leicht links auffahren Richtung {destination}"
            },
            "slight right": {
                "default": "Leicht rechts auffahren",
                "name": "Leicht rechts auffahren auf {way_name}",
                "destination": "Leicht rechts auffahren Richtung {destination}"
            },
            "sharp left": {
                "default": "Scharf links auffahren",
                "name": "Scharf links auffahren auf {way_name}",
                "destination": "Scharf links auffahren Richtung {destination}"
            },
            "sharp right": {
                "default": "Scharf rechts auffahren",
                "name": "Scharf rechts auffahren auf {way_name}",
                "destination": "Scharf rechts auffahren Richtung {destination}"
            },
            "uturn": {
                "default": "180°-Wendung",
                "name": "180°-Wendung auf {way_name}",
                "destination": "180°-Wendung Richtung {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "{modifier} weiterfahren",
                "name": "{modifier} weiterfahren auf {way_name}",
                "destination": "{modifier} weiterfahren Richtung {destination}"
            },
            "straight": {
                "default": "Geradeaus weiterfahren",
                "name": "Weiterfahren auf {way_name}",
                "destination": "Weiterfahren in Richtung {destination}"
            },
            "sharp left": {
                "default": "Scharf links",
                "name": "Scharf links auf {way_name}",
                "destination": "Scharf links Richtung {destination}"
            },
            "sharp right": {
                "default": "Scharf rechts",
                "name": "Scharf rechts auf {way_name}",
                "destination": "Scharf rechts Richtung {destination}"
            },
            "slight left": {
                "default": "Leicht links weiter",
                "name": "Leicht links weiter auf {way_name}",
                "destination": "Leicht links weiter Richtung {destination}"
            },
            "slight right": {
                "default": "Leicht rechts weiter",
                "name": "Leicht rechts weiter auf {way_name}",
                "destination": "Leicht rechts weiter Richtung {destination}"
            },
            "uturn": {
                "default": "180°-Wendung",
                "name": "180°-Wendung auf {way_name}",
                "destination": "180°-Wendung Richtung {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "{modifier} weiterfahren",
                "name": "{modifier} weiterfahren auf {way_name}",
                "destination": "{modifier} weiterfahren Richtung {destination}"
            },
            "uturn": {
                "default": "180°-Wendung",
                "name": "180°-Wendung auf {way_name}",
                "destination": "180°-Wendung Richtung {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Ausfahrt nehmen",
                "name": "Ausfahrt nehmen auf {way_name}",
                "destination": "Ausfahrt nehmen Richtung {destination}",
                "exit": "Ausfahrt {exit} nehmen",
                "exit_destination": "Ausfahrt {exit} nehmen Richtung {destination}"
            },
            "left": {
                "default": "Ausfahrt links nehmen",
                "name": "Ausfahrt links nehmen auf {way_name}",
                "destination": "Ausfahrt links nehmen Richtung {destination}",
                "exit": "Ausfahrt {exit} links nehmen",
                "exit_destination": "Ausfahrt {exit} links nehmen Richtung {destination}"
            },
            "right": {
                "default": "Ausfahrt rechts nehmen",
                "name": "Ausfahrt rechts nehmen Richtung {way_name}",
                "destination": "Ausfahrt rechts nehmen Richtung {destination}",
                "exit": "Ausfahrt {exit} rechts nehmen",
                "exit_destination": "Ausfahrt {exit} nehmen Richtung {destination}"
            },
            "sharp left": {
                "default": "Ausfahrt links nehmen",
                "name": "Ausfahrt links Seite nehmen auf {way_name}",
                "destination": "Ausfahrt links nehmen Richtung {destination}",
                "exit": "Ausfahrt {exit} links nehmen",
                "exit_destination": "Ausfahrt{exit} links nehmen Richtung {destination}"
            },
            "sharp right": {
                "default": "Ausfahrt rechts nehmen",
                "name": "Ausfahrt rechts nehmen auf {way_name}",
                "destination": "Ausfahrt rechts nehmen Richtung {destination}",
                "exit": "Ausfahrt {exit} rechts nehmen",
                "exit_destination": "Ausfahrt {exit} nehmen Richtung {destination}"
            },
            "slight left": {
                "default": "Ausfahrt links nehmen",
                "name": "Ausfahrt links nehmen auf {way_name}",
                "destination": "Ausfahrt links nehmen Richtung {destination}",
                "exit": "Ausfahrt {exit} nehmen",
                "exit_destination": "Ausfahrt {exit} links nehmen Richtung {destination}"
            },
            "slight right": {
                "default": "Ausfahrt rechts nehmen",
                "name": "Ausfahrt rechts nehmen auf {way_name}",
                "destination": "Ausfahrt rechts nehmen Richtung {destination}",
                "exit": "Ausfahrt {exit} rechts nehmen",
                "exit_destination": "Ausfahrt {exit} nehmen Richtung {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Auffahrt nehmen",
                "name": "Auffahrt nehmen auf {way_name}",
                "destination": "Auffahrt nehmen Richtung {destination}"
            },
            "left": {
                "default": "Auffahrt links nehmen",
                "name": "Auffahrt links nehmen auf {way_name}",
                "destination": "Auffahrt links nehmen Richtung {destination}"
            },
            "right": {
                "default": "Auffahrt rechts nehmen",
                "name": "Auffahrt rechts nehmen auf {way_name}",
                "destination": "Auffahrt rechts nehmen Richtung {destination}"
            },
            "sharp left": {
                "default": "Auffahrt links nehmen",
                "name": "Auffahrt links nehmen auf {way_name}",
                "destination": "Auffahrt links nehmen Richtung {destination}"
            },
            "sharp right": {
                "default": "Auffahrt rechts nehmen",
                "name": "Auffahrt rechts nehmen auf {way_name}",
                "destination": "Auffahrt rechts nehmen Richtung {destination}"
            },
            "slight left": {
                "default": "Auffahrt links Seite nehmen",
                "name": "Auffahrt links nehmen auf {way_name}",
                "destination": "Auffahrt links nehmen Richtung {destination}"
            },
            "slight right": {
                "default": "Auffahrt rechts nehmen",
                "name": "Auffahrt rechts nehmen auf {way_name}",
                "destination": "Auffahrt rechts nehmen Richtung {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "In den Kreisverkehr fahren",
                    "name": "Im Kreisverkehr die Ausfahrt auf {way_name} nehmen",
                    "destination": "Im Kreisverkehr die Ausfahrt Richtung {destination} nehmen"
                },
                "name": {
                    "default": "In {rotary_name} fahren",
                    "name": "In {rotary_name} die Ausfahrt auf {way_name} nehmen",
                    "destination": "In {rotary_name} die Ausfahrt Richtung {destination} nehmen"
                },
                "exit": {
                    "default": "Im Kreisverkehr die {exit_number} Ausfahrt nehmen",
                    "name": "Im Kreisverkehr die {exit_number} Ausfahrt nehmen auf {way_name}",
                    "destination": "Im Kreisverkehr die {exit_number} Ausfahrt nehmen Richtung {destination}"
                },
                "name_exit": {
                    "default": "In den Kreisverkehr fahren und {exit_number} Ausfahrt nehmen",
                    "name": "In den Kreisverkehr fahren und {exit_number} Ausfahrt nehmen auf {way_name}",
                    "destination": "In den Kreisverkehr fahren und {exit_number} Ausfahrt nehmen Richtung {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Im Kreisverkehr die {exit_number} Ausfahrt nehmen",
                    "name": "Im Kreisverkehr die {exit_number} Ausfahrt nehmen auf {way_name}",
                    "destination": "Im Kreisverkehr die {exit_number} Ausfahrt nehmen Richtung {destination}"
                },
                "default": {
                    "default": "In den Kreisverkehr fahren",
                    "name": "Im Kreisverkehr die Ausfahrt auf {way_name} nehmen",
                    "destination": "Im Kreisverkehr die Ausfahrt Richtung {destination} nehmen"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Am Kreisverkehr {modifier}",
                "name": "Am Kreisverkehr {modifier} auf {way_name}",
                "destination": "Am Kreisverkehr {modifier} Richtung {destination}"
            },
            "left": {
                "default": "Am Kreisverkehr links abbiegen",
                "name": "Am Kreisverkehr links auf {way_name}",
                "destination": "Am Kreisverkehr links Richtung {destination}"
            },
            "right": {
                "default": "Am Kreisverkehr rechts abbiegen",
                "name": "Am Kreisverkehr rechts auf {way_name}",
                "destination": "Am Kreisverkehr rechts Richtung {destination}"
            },
            "straight": {
                "default": "Am Kreisverkehr geradeaus weiterfahren",
                "name": "Am Kreisverkehr geradeaus weiterfahren auf {way_name}",
                "destination": "Am Kreisverkehr geradeaus weiterfahren Richtung {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "{modifier} abbiegen",
                "name": "{modifier} abbiegen auf {way_name}",
                "destination": "{modifier} abbiegen Richtung {destination}"
            },
            "left": {
                "default": "Links abbiegen",
                "name": "Links abbiegen auf {way_name}",
                "destination": "Links abbiegen Richtung {destination}"
            },
            "right": {
                "default": "Rechts abbiegen",
                "name": "Rechts abbiegen auf {way_name}",
                "destination": "Rechts abbiegen Richtung {destination}"
            },
            "straight": {
                "default": "Geradeaus weiterfahren",
                "name": "Geradeaus weiterfahren auf {way_name}",
                "destination": "Geradeaus weiterfahren Richtung {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "{modifier} abbiegen",
                "name": "{modifier} abbiegen auf {way_name}",
                "destination": "{modifier} abbiegen Richtung {destination}"
            },
            "left": {
                "default": "Links abbiegen",
                "name": "Links abbiegen auf {way_name}",
                "destination": "Links abbiegen Richtung {destination}"
            },
            "right": {
                "default": "Rechts abbiegen",
                "name": "Rechts abbiegen auf {way_name}",
                "destination": "Rechts abbiegen Richtung {destination}"
            },
            "straight": {
                "default": "Geradeaus weiterfahren",
                "name": "Geradeaus weiterfahren auf {way_name}",
                "destination": "Geradeaus weiterfahren Richtung {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "{modifier} abbiegen",
                "name": "{modifier} abbiegen auf {way_name}",
                "destination": "{modifier} abbiegen Richtung {destination}"
            },
            "left": {
                "default": "Links abbiegen",
                "name": "Links abbiegen auf {way_name}",
                "destination": "Links abbiegen Richtung {destination}"
            },
            "right": {
                "default": "Rechts abbiegen",
                "name": "Rechts abbiegen auf {way_name}",
                "destination": "Rechts abbiegen Richtung {destination}"
            },
            "straight": {
                "default": "Geradeaus weiterfahren",
                "name": "Geradeaus weiterfahren auf {way_name}",
                "destination": "Geradeaus weiterfahren Richtung {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Geradeaus weiterfahren"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],7:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1st",
                "2": "2nd",
                "3": "3rd",
                "4": "4th",
                "5": "5th",
                "6": "6th",
                "7": "7th",
                "8": "8th",
                "9": "9th",
                "10": "10th"
            },
            "direction": {
                "north": "north",
                "northeast": "northeast",
                "east": "east",
                "southeast": "southeast",
                "south": "south",
                "southwest": "southwest",
                "west": "west",
                "northwest": "northwest"
            },
            "modifier": {
                "left": "left",
                "right": "right",
                "sharp left": "sharp left",
                "sharp right": "sharp right",
                "slight left": "slight left",
                "slight right": "slight right",
                "straight": "straight",
                "uturn": "U-turn"
            },
            "lanes": {
                "xo": "Keep right",
                "ox": "Keep left",
                "xox": "Keep in the middle",
                "oxo": "Keep left or right"
            }
        },
        "modes": {
            "ferry": {
                "default": "Take the ferry",
                "name": "Take the ferry {way_name}",
                "destination": "Take the ferry towards {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one}, then, in {distance}, {instruction_two}",
            "two linked": "{instruction_one}, then {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "You have arrived at your {nth} destination"
            },
            "left": {
                "default": "You have arrived at your {nth} destination, on the left"
            },
            "right": {
                "default": "You have arrived at your {nth} destination, on the right"
            },
            "sharp left": {
                "default": "You have arrived at your {nth} destination, on the left"
            },
            "sharp right": {
                "default": "You have arrived at your {nth} destination, on the right"
            },
            "slight right": {
                "default": "You have arrived at your {nth} destination, on the right"
            },
            "slight left": {
                "default": "You have arrived at your {nth} destination, on the left"
            },
            "straight": {
                "default": "You have arrived at your {nth} destination, straight ahead"
            }
        },
        "continue": {
            "default": {
                "default": "Turn {modifier}",
                "name": "Turn {modifier} to stay on {way_name}",
                "destination": "Turn {modifier} towards {destination}",
                "exit": "Turn {modifier} onto {way_name}"
            },
            "straight": {
                "default": "Continue straight",
                "name": "Continue straight to stay on {way_name}",
                "destination": "Continue towards {destination}",
                "distance": "Continue straight for {distance}",
                "namedistance": "Continue on {way_name} for {distance}"
            },
            "sharp left": {
                "default": "Make a sharp left",
                "name": "Make a sharp left to stay on {way_name}",
                "destination": "Make a sharp left towards {destination}"
            },
            "sharp right": {
                "default": "Make a sharp right",
                "name": "Make a sharp right to stay on {way_name}",
                "destination": "Make a sharp right towards {destination}"
            },
            "slight left": {
                "default": "Make a slight left",
                "name": "Make a slight left to stay on {way_name}",
                "destination": "Make a slight left towards {destination}"
            },
            "slight right": {
                "default": "Make a slight right",
                "name": "Make a slight right to stay on {way_name}",
                "destination": "Make a slight right towards {destination}"
            },
            "uturn": {
                "default": "Make a U-turn",
                "name": "Make a U-turn and continue on {way_name}",
                "destination": "Make a U-turn towards {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Head {direction}",
                "name": "Head {direction} on {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Turn {modifier}",
                "name": "Turn {modifier} onto {way_name}",
                "destination": "Turn {modifier} towards {destination}"
            },
            "straight": {
                "default": "Continue straight",
                "name": "Continue straight onto {way_name}",
                "destination": "Continue straight towards {destination}"
            },
            "uturn": {
                "default": "Make a U-turn at the end of the road",
                "name": "Make a U-turn onto {way_name} at the end of the road",
                "destination": "Make a U-turn towards {destination} at the end of the road"
            }
        },
        "fork": {
            "default": {
                "default": "Keep {modifier} at the fork",
                "name": "Keep {modifier} at the fork onto {way_name}",
                "destination": "Keep {modifier} at the fork towards {destination}"
            },
            "slight left": {
                "default": "Keep left at the fork",
                "name": "Keep left at the fork onto {way_name}",
                "destination": "Keep left at the fork towards {destination}"
            },
            "slight right": {
                "default": "Keep right at the fork",
                "name": "Keep right at the fork onto {way_name}",
                "destination": "Keep right at the fork towards {destination}"
            },
            "sharp left": {
                "default": "Take a sharp left at the fork",
                "name": "Take a sharp left at the fork onto {way_name}",
                "destination": "Take a sharp left at the fork towards {destination}"
            },
            "sharp right": {
                "default": "Take a sharp right at the fork",
                "name": "Take a sharp right at the fork onto {way_name}",
                "destination": "Take a sharp right at the fork towards {destination}"
            },
            "uturn": {
                "default": "Make a U-turn",
                "name": "Make a U-turn onto {way_name}",
                "destination": "Make a U-turn towards {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Merge {modifier}",
                "name": "Merge {modifier} onto {way_name}",
                "destination": "Merge {modifier} towards {destination}"
            },
            "slight left": {
                "default": "Merge left",
                "name": "Merge left onto {way_name}",
                "destination": "Merge left towards {destination}"
            },
            "slight right": {
                "default": "Merge right",
                "name": "Merge right onto {way_name}",
                "destination": "Merge right towards {destination}"
            },
            "sharp left": {
                "default": "Merge left",
                "name": "Merge left onto {way_name}",
                "destination": "Merge left towards {destination}"
            },
            "sharp right": {
                "default": "Merge right",
                "name": "Merge right onto {way_name}",
                "destination": "Merge right towards {destination}"
            },
            "uturn": {
                "default": "Make a U-turn",
                "name": "Make a U-turn onto {way_name}",
                "destination": "Make a U-turn towards {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Continue {modifier}",
                "name": "Continue {modifier} onto {way_name}",
                "destination": "Continue {modifier} towards {destination}"
            },
            "straight": {
                "default": "Continue straight",
                "name": "Continue onto {way_name}",
                "destination": "Continue towards {destination}"
            },
            "sharp left": {
                "default": "Take a sharp left",
                "name": "Take a sharp left onto {way_name}",
                "destination": "Take a sharp left towards {destination}"
            },
            "sharp right": {
                "default": "Take a sharp right",
                "name": "Take a sharp right onto {way_name}",
                "destination": "Take a sharp right towards {destination}"
            },
            "slight left": {
                "default": "Continue slightly left",
                "name": "Continue slightly left onto {way_name}",
                "destination": "Continue slightly left towards {destination}"
            },
            "slight right": {
                "default": "Continue slightly right",
                "name": "Continue slightly right onto {way_name}",
                "destination": "Continue slightly right towards {destination}"
            },
            "uturn": {
                "default": "Make a U-turn",
                "name": "Make a U-turn onto {way_name}",
                "destination": "Make a U-turn towards {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Continue {modifier}",
                "name": "Continue {modifier} onto {way_name}",
                "destination": "Continue {modifier} towards {destination}"
            },
            "uturn": {
                "default": "Make a U-turn",
                "name": "Make a U-turn onto {way_name}",
                "destination": "Make a U-turn towards {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Take the ramp",
                "name": "Take the ramp onto {way_name}",
                "destination": "Take the ramp towards {destination}",
                "exit": "Take exit {exit}",
                "exit_destination": "Take exit {exit} towards {destination}"
            },
            "left": {
                "default": "Take the ramp on the left",
                "name": "Take the ramp on the left onto {way_name}",
                "destination": "Take the ramp on the left towards {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "right": {
                "default": "Take the ramp on the right",
                "name": "Take the ramp on the right onto {way_name}",
                "destination": "Take the ramp on the right towards {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "sharp left": {
                "default": "Take the ramp on the left",
                "name": "Take the ramp on the left onto {way_name}",
                "destination": "Take the ramp on the left towards {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "sharp right": {
                "default": "Take the ramp on the right",
                "name": "Take the ramp on the right onto {way_name}",
                "destination": "Take the ramp on the right towards {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "slight left": {
                "default": "Take the ramp on the left",
                "name": "Take the ramp on the left onto {way_name}",
                "destination": "Take the ramp on the left towards {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "slight right": {
                "default": "Take the ramp on the right",
                "name": "Take the ramp on the right onto {way_name}",
                "destination": "Take the ramp on the right towards {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Take the ramp",
                "name": "Take the ramp onto {way_name}",
                "destination": "Take the ramp towards {destination}"
            },
            "left": {
                "default": "Take the ramp on the left",
                "name": "Take the ramp on the left onto {way_name}",
                "destination": "Take the ramp on the left towards {destination}"
            },
            "right": {
                "default": "Take the ramp on the right",
                "name": "Take the ramp on the right onto {way_name}",
                "destination": "Take the ramp on the right towards {destination}"
            },
            "sharp left": {
                "default": "Take the ramp on the left",
                "name": "Take the ramp on the left onto {way_name}",
                "destination": "Take the ramp on the left towards {destination}"
            },
            "sharp right": {
                "default": "Take the ramp on the right",
                "name": "Take the ramp on the right onto {way_name}",
                "destination": "Take the ramp on the right towards {destination}"
            },
            "slight left": {
                "default": "Take the ramp on the left",
                "name": "Take the ramp on the left onto {way_name}",
                "destination": "Take the ramp on the left towards {destination}"
            },
            "slight right": {
                "default": "Take the ramp on the right",
                "name": "Take the ramp on the right onto {way_name}",
                "destination": "Take the ramp on the right towards {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Enter the traffic circle",
                    "name": "Enter the traffic circle and exit onto {way_name}",
                    "destination": "Enter the traffic circle and exit towards {destination}"
                },
                "name": {
                    "default": "Enter {rotary_name}",
                    "name": "Enter {rotary_name} and exit onto {way_name}",
                    "destination": "Enter {rotary_name} and exit towards {destination}"
                },
                "exit": {
                    "default": "Enter the traffic circle and take the {exit_number} exit",
                    "name": "Enter the traffic circle and take the {exit_number} exit onto {way_name}",
                    "destination": "Enter the traffic circle and take the {exit_number} exit towards {destination}"
                },
                "name_exit": {
                    "default": "Enter {rotary_name} and take the {exit_number} exit",
                    "name": "Enter {rotary_name} and take the {exit_number} exit onto {way_name}",
                    "destination": "Enter {rotary_name} and take the {exit_number} exit towards {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Enter the traffic circle and take the {exit_number} exit",
                    "name": "Enter the traffic circle and take the {exit_number} exit onto {way_name}",
                    "destination": "Enter the traffic circle and take the {exit_number} exit towards {destination}"
                },
                "default": {
                    "default": "Enter the traffic circle",
                    "name": "Enter the traffic circle and exit onto {way_name}",
                    "destination": "Enter the traffic circle and exit towards {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "At the roundabout make a {modifier}",
                "name": "At the roundabout make a {modifier} onto {way_name}",
                "destination": "At the roundabout make a {modifier} towards {destination}"
            },
            "left": {
                "default": "At the roundabout turn left",
                "name": "At the roundabout turn left onto {way_name}",
                "destination": "At the roundabout turn left towards {destination}"
            },
            "right": {
                "default": "At the roundabout turn right",
                "name": "At the roundabout turn right onto {way_name}",
                "destination": "At the roundabout turn right towards {destination}"
            },
            "straight": {
                "default": "At the roundabout continue straight",
                "name": "At the roundabout continue straight onto {way_name}",
                "destination": "At the roundabout continue straight towards {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Make a {modifier}",
                "name": "Make a {modifier} onto {way_name}",
                "destination": "Make a {modifier} towards {destination}"
            },
            "left": {
                "default": "Turn left",
                "name": "Turn left onto {way_name}",
                "destination": "Turn left towards {destination}"
            },
            "right": {
                "default": "Turn right",
                "name": "Turn right onto {way_name}",
                "destination": "Turn right towards {destination}"
            },
            "straight": {
                "default": "Go straight",
                "name": "Go straight onto {way_name}",
                "destination": "Go straight towards {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Make a {modifier}",
                "name": "Make a {modifier} onto {way_name}",
                "destination": "Make a {modifier} towards {destination}"
            },
            "left": {
                "default": "Turn left",
                "name": "Turn left onto {way_name}",
                "destination": "Turn left towards {destination}"
            },
            "right": {
                "default": "Turn right",
                "name": "Turn right onto {way_name}",
                "destination": "Turn right towards {destination}"
            },
            "straight": {
                "default": "Go straight",
                "name": "Go straight onto {way_name}",
                "destination": "Go straight towards {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Make a {modifier}",
                "name": "Make a {modifier} onto {way_name}",
                "destination": "Make a {modifier} towards {destination}"
            },
            "left": {
                "default": "Turn left",
                "name": "Turn left onto {way_name}",
                "destination": "Turn left towards {destination}"
            },
            "right": {
                "default": "Turn right",
                "name": "Turn right onto {way_name}",
                "destination": "Turn right towards {destination}"
            },
            "straight": {
                "default": "Go straight",
                "name": "Go straight onto {way_name}",
                "destination": "Go straight towards {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Continue straight"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],8:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1-a",
                "2": "2-a",
                "3": "3-a",
                "4": "4-a",
                "5": "5-a",
                "6": "6-a",
                "7": "7-a",
                "8": "8-a",
                "9": "9-a",
                "10": "10-a"
            },
            "direction": {
                "north": "norden",
                "northeast": "nord-orienten",
                "east": "orienten",
                "southeast": "sud-orienten",
                "south": "suden",
                "southwest": "sud-okcidenten",
                "west": "okcidenten",
                "northwest": "nord-okcidenten"
            },
            "modifier": {
                "left": "maldekstren",
                "right": "dekstren",
                "sharp left": "maldekstregen",
                "sharp right": "dekstregen",
                "slight left": "maldekstreten",
                "slight right": "dekstreten",
                "straight": "rekten",
                "uturn": "turniĝu malantaŭen"
            },
            "lanes": {
                "xo": "Veturu dekstre",
                "ox": "Veturu maldekstre",
                "xox": "Veturu meze",
                "oxo": "Veturu dekstre aŭ maldekstre"
            }
        },
        "modes": {
            "ferry": {
                "default": "Enpramiĝu",
                "name": "Enpramiĝu {way_name}",
                "destination": "Enpramiĝu direkte al {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} kaj post {distance} {instruction_two}",
            "two linked": "{instruction_one} kaj sekve {instruction_two}",
            "one in distance": "Post {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Vi atingis vian {nth} celon"
            },
            "left": {
                "default": "Vi atingis vian {nth} celon ĉe maldekstre"
            },
            "right": {
                "default": "Vi atingis vian {nth} celon ĉe dekstre"
            },
            "sharp left": {
                "default": "Vi atingis vian {nth} celon ĉe maldekstre"
            },
            "sharp right": {
                "default": "Vi atingis vian {nth} celon ĉe dekstre"
            },
            "slight right": {
                "default": "Vi atingis vian {nth} celon ĉe dekstre"
            },
            "slight left": {
                "default": "Vi atingis vian {nth} celon ĉe maldekstre"
            },
            "straight": {
                "default": "Vi atingis vian {nth} celon"
            }
        },
        "continue": {
            "default": {
                "default": "Veturu {modifier}",
                "name": "Veturu {modifier} al {way_name}",
                "destination": "Veturu {modifier} direkte al {destination}",
                "exit": "Veturu {modifier} direkte al {way_name}"
            },
            "straight": {
                "default": "Veturu rekten",
                "name": "Veturu rekten al {way_name}",
                "destination": "Veturu rekten direkte al {destination}",
                "distance": "Veturu rekten dum {distance}",
                "namedistance": "Veturu rekten al {way_name} dum {distance}"
            },
            "sharp left": {
                "default": "Turniĝu ege maldekstren",
                "name": "Turniĝu ege maldekstren al {way_name}",
                "destination": "Turniĝu ege maldekstren direkte al {destination}"
            },
            "sharp right": {
                "default": "Turniĝu ege dekstren",
                "name": "Turniĝu ege dekstren al {way_name}",
                "destination": "Turniĝu ege dekstren direkte al {destination}"
            },
            "slight left": {
                "default": "Turniĝu ete maldekstren",
                "name": "Turniĝu ete maldekstren al {way_name}",
                "destination": "Turniĝu ete maldekstren direkte al {destination}"
            },
            "slight right": {
                "default": "Turniĝu ete dekstren",
                "name": "Turniĝu ete dekstren al {way_name}",
                "destination": "Turniĝu ete dekstren direkte al {destination}"
            },
            "uturn": {
                "default": "Turniĝu malantaŭen",
                "name": "Turniĝu malantaŭen al {way_name}",
                "destination": "Turniĝu malantaŭen direkte al {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Direktiĝu {direction}",
                "name": "Direktiĝu {direction} al {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Veturu {modifier}",
                "name": "Veturu {modifier} direkte al {way_name}",
                "destination": "Veturu {modifier} direkte al {destination}"
            },
            "straight": {
                "default": "Veturu rekten",
                "name": "Veturu rekten al {way_name}",
                "destination": "Veturu rekten direkte al {destination}"
            },
            "uturn": {
                "default": "Turniĝu malantaŭen ĉe fino de la vojo",
                "name": "Turniĝu malantaŭen al {way_name} ĉe fino de la vojo",
                "destination": "Turniĝu malantaŭen direkte al {destination} ĉe fino de la vojo"
            }
        },
        "fork": {
            "default": {
                "default": "Daŭru {modifier} ĉe la vojforko",
                "name": "Pluu {modifier} ĉe la vojforko al {way_name}",
                "destination": "Pluu {modifier} ĉe la vojforko direkte al {destination}"
            },
            "slight left": {
                "default": "Maldekstren ĉe la vojforko",
                "name": "Maldekstren ĉe la vojforko al {way_name}",
                "destination": "Maldekstren ĉe la vojforko direkte al {destination}"
            },
            "slight right": {
                "default": "Dekstren ĉe la vojforko",
                "name": "Dekstren ĉe la vojforko al {way_name}",
                "destination": "Dekstren ĉe la vojforko direkte al {destination}"
            },
            "sharp left": {
                "default": "Ege maldekstren ĉe la vojforko",
                "name": "Ege maldekstren ĉe la vojforko al {way_name}",
                "destination": "Ege maldekstren ĉe la vojforko direkte al {destination}"
            },
            "sharp right": {
                "default": "Ege dekstren ĉe la vojforko",
                "name": "Ege dekstren ĉe la vojforko al {way_name}",
                "destination": "Ege dekstren ĉe la vojforko direkte al {destination}"
            },
            "uturn": {
                "default": "Turniĝu malantaŭen",
                "name": "Turniĝu malantaŭen al {way_name}",
                "destination": "Turniĝu malantaŭen direkte al {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Enveturu {modifier}",
                "name": "Enveturu {modifier} al {way_name}",
                "destination": "Enveturu {modifier} direkte al {destination}"
            },
            "slight left": {
                "default": "Enveturu de maldekstre",
                "name": "Enveturu de maldekstre al {way_name}",
                "destination": "Enveturu de maldekstre direkte al {destination}"
            },
            "slight right": {
                "default": "Enveturu de dekstre",
                "name": "Enveturu de dekstre al {way_name}",
                "destination": "Enveturu de dekstre direkte al {destination}"
            },
            "sharp left": {
                "default": "Enveturu de maldekstre",
                "name": "Enveture de maldekstre al {way_name}",
                "destination": "Enveturu de maldekstre direkte al {destination}"
            },
            "sharp right": {
                "default": "Enveturu de dekstre",
                "name": "Enveturu de dekstre al {way_name}",
                "destination": "Enveturu de dekstre direkte al {destination}"
            },
            "uturn": {
                "default": "Turniĝu malantaŭen",
                "name": "Turniĝu malantaŭen al {way_name}",
                "destination": "Turniĝu malantaŭen direkte al {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Pluu {modifier}",
                "name": "Pluu {modifier} al {way_name}",
                "destination": "Pluu {modifier} direkte al {destination}"
            },
            "straight": {
                "default": "Veturu rekten",
                "name": "Veturu rekten al {way_name}",
                "destination": "Veturu rekten direkte al {destination}"
            },
            "sharp left": {
                "default": "Turniĝu ege maldekstren",
                "name": "Turniĝu ege maldekstren al {way_name}",
                "destination": "Turniĝu ege maldekstren direkte al {destination}"
            },
            "sharp right": {
                "default": "Turniĝu ege dekstren",
                "name": "Turniĝu ege dekstren al {way_name}",
                "destination": "Turniĝu ege dekstren direkte al {destination}"
            },
            "slight left": {
                "default": "Pluu ete maldekstren",
                "name": "Pluu ete maldekstren al {way_name}",
                "destination": "Pluu ete maldekstren direkte al {destination}"
            },
            "slight right": {
                "default": "Pluu ete dekstren",
                "name": "Pluu ete dekstren al {way_name}",
                "destination": "Pluu ete dekstren direkte al {destination}"
            },
            "uturn": {
                "default": "Turniĝu malantaŭen",
                "name": "Turniĝu malantaŭen al {way_name}",
                "destination": "Turniĝu malantaŭen direkte al {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Pluu {modifier}",
                "name": "Pluu {modifier} al {way_name}",
                "destination": "Pluu {modifier} direkte al {destination}"
            },
            "uturn": {
                "default": "Turniĝu malantaŭen",
                "name": "Turniĝu malantaŭen al {way_name}",
                "destination": "Turniĝu malantaŭen direkte al {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Direktiĝu al enveturejo",
                "name": "Direktiĝu al enveturejo al {way_name}",
                "destination": "Direktiĝu al enveturejo direkte al {destination}",
                "exit": "Direktiĝu al elveturejo {exit}",
                "exit_destination": "Direktiĝu al elveturejo {exit} direkte al {destination}"
            },
            "left": {
                "default": "Direktiĝu al enveturejo ĉe maldekstre",
                "name": "Direktiĝu al enveturejo ĉe maldekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe maldekstre al {destination}",
                "exit": "Direktiĝu al elveturejo {exit} ĉe maldekstre",
                "exit_destination": "Direktiĝu al elveturejo {exit} ĉe maldekstre direkte al {destination}"
            },
            "right": {
                "default": "Direktiĝu al enveturejo ĉe dekstre",
                "name": "Direktiĝu al enveturejo ĉe dekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe dekstre al {destination}",
                "exit": "Direktiĝu al {exit} elveturejo ĉe ldekstre",
                "exit_destination": "Direktiĝu al elveturejo {exit} ĉe dekstre direkte al {destination}"
            },
            "sharp left": {
                "default": "Direktiĝu al enveturejo ĉe maldekstre",
                "name": "Direktiĝu al enveturejo ĉe maldekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe maldekstre al {destination}",
                "exit": "Direktiĝu al {exit} elveturejo ĉe maldekstre",
                "exit_destination": "Direktiĝu al elveturejo {exit} ĉe maldekstre direkte al {destination}"
            },
            "sharp right": {
                "default": "Direktiĝu al enveturejo ĉe dekstre",
                "name": "Direktiĝu al enveturejo ĉe dekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe dekstre al {destination}",
                "exit": "Direktiĝu al elveturejo {exit} ĉe dekstre",
                "exit_destination": "Direktiĝu al elveturejo {exit} ĉe dekstre direkte al {destination}"
            },
            "slight left": {
                "default": "Direktiĝu al enveturejo ĉe maldekstre",
                "name": "Direktiĝu al enveturejo ĉe maldekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe maldekstre al {destination}",
                "exit": "Direktiĝu al {exit} elveturejo ĉe maldekstre",
                "exit_destination": "Direktiĝu al elveturejo {exit} ĉe maldekstre direkte al {destination}"
            },
            "slight right": {
                "default": "Direktiĝu al enveturejo ĉe dekstre",
                "name": "Direktiĝu al enveturejo ĉe dekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe dekstre al {destination}",
                "exit": "Direktiĝu al {exit} elveturejo ĉe ldekstre",
                "exit_destination": "Direktiĝu al elveturejo {exit} ĉe dekstre direkte al {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Direktiĝu al enveturejo",
                "name": "Direktiĝu al enveturejo al {way_name}",
                "destination": "Direktiĝu al enveturejo direkte al {destination}"
            },
            "left": {
                "default": "Direktiĝu al enveturejo ĉe maldekstre",
                "name": "Direktiĝu al enveturejo ĉe maldekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe maldekstre al {destination}"
            },
            "right": {
                "default": "Direktiĝu al enveturejo ĉe dekstre",
                "name": "Direktiĝu al enveturejo ĉe dekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe dekstre al {destination}"
            },
            "sharp left": {
                "default": "Direktiĝu al enveturejo ĉe maldekstre",
                "name": "Direktiĝu al enveturejo ĉe maldekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe maldekstre al {destination}"
            },
            "sharp right": {
                "default": "Direktiĝu al enveturejo ĉe dekstre",
                "name": "Direktiĝu al enveturejo ĉe dekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe dekstre al {destination}"
            },
            "slight left": {
                "default": "Direktiĝu al enveturejo ĉe maldekstre",
                "name": "Direktiĝu al enveturejo ĉe maldekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe maldekstre al {destination}"
            },
            "slight right": {
                "default": "Direktiĝu al enveturejo ĉe dekstre",
                "name": "Direktiĝu al enveturejo ĉe dekstre al {way_name}",
                "destination": "Direktiĝu al enveturejo ĉe dekstre al {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Enveturu trafikcirklegon",
                    "name": "Enveturu trafikcirklegon kaj elveturu al {way_name}",
                    "destination": "Enveturu trafikcirklegon kaj elveturu direkte al {destination}"
                },
                "name": {
                    "default": "Enveturu {rotary_name}",
                    "name": "Enveturu {rotary_name} kaj elveturu al {way_name}",
                    "destination": "Enveturu {rotary_name} kaj elveturu direkte al {destination}"
                },
                "exit": {
                    "default": "Enveturu trafikcirklegon kaj sekve al {exit_number} elveturejo",
                    "name": "Enveturu trafikcirklegon kaj sekve al {exit_number} elveturejo al {way_name}",
                    "destination": "Enveturu trafikcirklegon kaj sekve al {exit_number} elveturejo direkte al {destination}"
                },
                "name_exit": {
                    "default": "Enveturu {rotary_name} kaj sekve al {exit_number} elveturejo",
                    "name": "Enveturu {rotary_name} kaj sekve al {exit_number} elveturejo al {way_name}",
                    "destination": "Enveturu {rotary_name} kaj sekve al {exit_number} elveturejo direkte al {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Enveturu trafikcirklon kaj sekve al {exit_number} elveturejo",
                    "name": "Enveturu trafikcirklon kaj sekve al {exit_number} elveturejo al {way_name}",
                    "destination": "Enveturu trafikcirklon kaj sekve al {exit_number} elveturejo direkte al {destination}"
                },
                "default": {
                    "default": "Enveturu trafikcirklon",
                    "name": "Enveturu trafikcirklon kaj elveturu al {way_name}",
                    "destination": "Enveturu trafikcirklon kaj elveturu direkte al {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Ĉe la trafikcirklo veturu {modifier}",
                "name": "Ĉe la trafikcirklo veturu {modifier} al {way_name}",
                "destination": "Ĉe la trafikcirklo veturu {modifier} direkte al {destination}"
            },
            "left": {
                "default": "Ĉe la trafikcirklo turniĝu maldekstren",
                "name": "Ĉe la trafikcirklo turniĝu maldekstren al {way_name}",
                "destination": "Ĉe la trafikcirklo turniĝu maldekstren direkte al {destination}"
            },
            "right": {
                "default": "Ĉe la trafikcirklo turniĝu dekstren",
                "name": "Ĉe la trafikcirklo turniĝu dekstren al {way_name}",
                "destination": "Ĉe la trafikcirklo turniĝu dekstren direkte al {destination}"
            },
            "straight": {
                "default": "Ĉe la trafikcirklo veturu rekten",
                "name": "Ĉe la trafikcirklo veturu rekten al {way_name}",
                "destination": "Ĉe la trafikcirklo veturu rekten direkte al {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Veturu {modifier}",
                "name": "Veturu {modifier} al {way_name}",
                "destination": "Veturu {modifier} direkte al {destination}"
            },
            "left": {
                "default": "Turniĝu maldekstren",
                "name": "Turniĝu maldekstren al {way_name}",
                "destination": "Turniĝu maldekstren direkte al {destination}"
            },
            "right": {
                "default": "Turniĝu dekstren",
                "name": "Turniĝu dekstren al {way_name}",
                "destination": "Turniĝu dekstren direkte al {destination}"
            },
            "straight": {
                "default": "Veturu rekten",
                "name": "Veturu rekten al {way_name}",
                "destination": "Veturu rekten direkte al {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "{modifier}",
                "name": "{modifier} al {way_name}",
                "destination": "Veturu {modifier} direkte al {destination}"
            },
            "left": {
                "default": "Turniĝu maldekstren",
                "name": "Turniĝu maldekstren al {way_name}",
                "destination": "Turniĝu maldekstren direkte al {destination}"
            },
            "right": {
                "default": "Turniĝu dekstren",
                "name": "Turniĝu dekstren al {way_name}",
                "destination": "Turniĝu dekstren direkte al {destination}"
            },
            "straight": {
                "default": "Veturu rekten",
                "name": "Veturu rekten al {way_name}",
                "destination": "Veturu rekten direkte al {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Veturu {modifier}",
                "name": "Veturu {modifier} al {way_name}",
                "destination": "Veturu {modifier} direkte al {destination}"
            },
            "left": {
                "default": "Turniĝu maldekstren",
                "name": "Turniĝu maldekstren al {way_name}",
                "destination": "Turniĝu maldekstren direkte al {destination}"
            },
            "right": {
                "default": "Turniĝu dekstren",
                "name": "Turniĝu dekstren al {way_name}",
                "destination": "Turniĝu dekstren direkte al {destination}"
            },
            "straight": {
                "default": "Veturu rekten",
                "name": "Veturu rekten al {way_name}",
                "destination": "Veturu rekten direkte al {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Pluu rekten"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],9:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1ª",
                "2": "2ª",
                "3": "3ª",
                "4": "4ª",
                "5": "5ª",
                "6": "6ª",
                "7": "7ª",
                "8": "8ª",
                "9": "9ª",
                "10": "10ª"
            },
            "direction": {
                "north": "norte",
                "northeast": "noreste",
                "east": "este",
                "southeast": "sureste",
                "south": "sur",
                "southwest": "suroeste",
                "west": "oeste",
                "northwest": "noroeste"
            },
            "modifier": {
                "left": "a la izquierda",
                "right": "a la derecha",
                "sharp left": "cerrada a la izquierda",
                "sharp right": "cerrada a la derecha",
                "slight left": "ligeramente a la izquierda",
                "slight right": "ligeramente a la derecha",
                "straight": "recto",
                "uturn": "cambio de sentido"
            },
            "lanes": {
                "xo": "Mantente a la derecha",
                "ox": "Mantente a la izquierda",
                "xox": "Mantente en el medio",
                "oxo": "Mantente a la izquierda o a la derecha"
            }
        },
        "modes": {
            "ferry": {
                "default": "Coge el ferry",
                "name": "Coge el ferry {way_name}",
                "destination": "Coge el ferry hacia {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} y luego en {distance}, {instruction_two}",
            "two linked": "{instruction_one} y luego {instruction_two}",
            "one in distance": "A {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Has llegado a tu {nth} destino"
            },
            "left": {
                "default": "Has llegado a tu {nth} destino, a la izquierda"
            },
            "right": {
                "default": "Has llegado a tu {nth} destino, a la derecha"
            },
            "sharp left": {
                "default": "Has llegado a tu {nth} destino, a la izquierda"
            },
            "sharp right": {
                "default": "Has llegado a tu {nth} destino, a la derecha"
            },
            "slight right": {
                "default": "Has llegado a tu {nth} destino, a la derecha"
            },
            "slight left": {
                "default": "Has llegado a tu {nth} destino, a la izquierda"
            },
            "straight": {
                "default": "Has llegado a tu {nth} destino, en frente"
            }
        },
        "continue": {
            "default": {
                "default": "Gire {modifier}",
                "name": "Cruce {modifier} en {way_name}",
                "destination": "Gire {modifier} hacia {destination}",
                "exit": "Gire {modifier} en {way_name}"
            },
            "straight": {
                "default": "Continúe recto",
                "name": "Continúe en {way_name}",
                "destination": "Continúe hacia {destination}",
                "distance": "Continúe recto por {distance}",
                "namedistance": "Continúe recto en {way_name} por {distance}"
            },
            "sharp left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "slight left": {
                "default": "Gire a la izquierda",
                "name": "Doble levemente a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Gire a la izquierda",
                "name": "Doble levemente a la derecha en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido y continúe en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Dirígete al {direction}",
                "name": "Dirígete al {direction} por {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Al final de la calle gira {modifier}",
                "name": "Al final de la calle gira {modifier} por {way_name}",
                "destination": "Al final de la calle gira {modifier} hacia {destination}"
            },
            "straight": {
                "default": "Al final de la calle continúa recto",
                "name": "Al final de la calle continúa recto por {way_name}",
                "destination": "Al final de la calle continúa recto hacia {destination}"
            },
            "uturn": {
                "default": "Al final de la calle haz un cambio de sentido",
                "name": "Al final de la calle haz un cambio de sentido en {way_name}",
                "destination": "Al final de la calle haz un cambio de sentido hacia {destination}"
            }
        },
        "fork": {
            "default": {
                "default": "Mantente {modifier} en el cruce",
                "name": "Mantente {modifier} en el cruce por {way_name}",
                "destination": "Mantente {modifier} en el cruce hacia {destination}"
            },
            "slight left": {
                "default": "Mantente a la izquierda en el cruce",
                "name": "Mantente a la izquierda en el cruce por {way_name}",
                "destination": "Mantente a la izquierda en el cruce hacia {destination}"
            },
            "slight right": {
                "default": "Mantente a la derecha en el cruce",
                "name": "Mantente a la derecha en el cruce por {way_name}",
                "destination": "Mantente a la derecha en el cruce hacia {destination}"
            },
            "sharp left": {
                "default": "Gira la izquierda en el cruce",
                "name": "Gira a la izquierda en el cruce por {way_name}",
                "destination": "Gira a la izquierda en el cruce hacia {destination}"
            },
            "sharp right": {
                "default": "Gira a la derecha en el cruce",
                "name": "Gira a la derecha en el cruce por {way_name}",
                "destination": "Gira a la derecha en el cruce hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Incorpórate {modifier}",
                "name": "Incorpórate {modifier} por {way_name}",
                "destination": "Incorpórate {modifier} hacia {destination}"
            },
            "slight left": {
                "default": "Incorpórate a la izquierda",
                "name": "Incorpórate a la izquierda por {way_name}",
                "destination": "Incorpórate a la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Incorpórate a la derecha",
                "name": "Incorpórate a la derecha por {way_name}",
                "destination": "Incorpórate a la derecha hacia {destination}"
            },
            "sharp left": {
                "default": "Incorpórate a la izquierda",
                "name": "Incorpórate a la izquierda por {way_name}",
                "destination": "Incorpórate a la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Incorpórate a la derecha",
                "name": "Incorpórate a la derecha por {way_name}",
                "destination": "Incorpórate a la derecha hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Continúa {modifier}",
                "name": "Continúa {modifier} por {way_name}",
                "destination": "Continúa {modifier} hacia {destination}"
            },
            "straight": {
                "default": "Continúa recto",
                "name": "Continúa por {way_name}",
                "destination": "Continúa hacia {destination}"
            },
            "sharp left": {
                "default": "Gira a la izquierda",
                "name": "Gira a la izquierda por {way_name}",
                "destination": "Gira a la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Gira a la derecha",
                "name": "Gira a la derecha por {way_name}",
                "destination": "Gira a la derecha hacia {destination}"
            },
            "slight left": {
                "default": "Continúa ligeramente por la izquierda",
                "name": "Continúa ligeramente por la izquierda por {way_name}",
                "destination": "Continúa ligeramente por la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Continúa ligeramente por la derecha",
                "name": "Continúa ligeramente por la derecha por {way_name}",
                "destination": "Continúa ligeramente por la derecha hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Continúa {modifier}",
                "name": "Continúa {modifier} por {way_name}",
                "destination": "Continúa {modifier} hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Coge la cuesta abajo",
                "name": "Coge la cuesta abajo por {way_name}",
                "destination": "Coge la cuesta abajo hacia {destination}",
                "exit": "Coge la cuesta abajo {exit}",
                "exit_destination": "Coge la cuesta abajo {exit} hacia {destination}"
            },
            "left": {
                "default": "Coge la cuesta abajo de la izquierda",
                "name": "Coge la cuesta abajo de la izquierda por {way_name}",
                "destination": "Coge la cuesta abajo de la izquierda hacia {destination}",
                "exit": "Coge la cuesta abajo {exit} a tu izquierda",
                "exit_destination": "Coge la cuesta abajo {exit} a tu izquierda hacia {destination}"
            },
            "right": {
                "default": "Coge la cuesta abajo de la derecha",
                "name": "Coge la cuesta abajo de la derecha por {way_name}",
                "destination": "Coge la cuesta abajo de la derecha hacia {destination}",
                "exit": "Coge la cuesta abajo {exit}",
                "exit_destination": "Coge la cuesta abajo {exit} hacia {destination}"
            },
            "sharp left": {
                "default": "Coge la cuesta abajo de la izquierda",
                "name": "Coge la cuesta abajo de la izquierda por {way_name}",
                "destination": "Coge la cuesta abajo de la izquierda hacia {destination}",
                "exit": "Coge la cuesta abajo {exit} a tu izquierda",
                "exit_destination": "Coge la cuesta abajo {exit} a tu izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Coge la cuesta abajo de la derecha",
                "name": "Coge la cuesta abajo de la derecha por {way_name}",
                "destination": "Coge la cuesta abajo de la derecha hacia {destination}",
                "exit": "Coge la cuesta abajo {exit}",
                "exit_destination": "Coge la cuesta abajo {exit} hacia {destination}"
            },
            "slight left": {
                "default": "Coge la cuesta abajo de la izquierda",
                "name": "Coge la cuesta abajo de la izquierda por {way_name}",
                "destination": "Coge la cuesta abajo de la izquierda hacia {destination}",
                "exit": "Coge la cuesta abajo {exit} a tu izquierda",
                "exit_destination": "Coge la cuesta abajo {exit} a tu izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Coge la cuesta abajo de la derecha",
                "name": "Coge la cuesta abajo de la derecha por {way_name}",
                "destination": "Coge la cuesta abajo de la derecha hacia {destination}",
                "exit": "Coge la cuesta abajo {exit}",
                "exit_destination": "Coge la cuesta abajo {exit} hacia {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Coge la cuesta",
                "name": "Coge la cuesta por {way_name}",
                "destination": "Coge la cuesta hacia {destination}"
            },
            "left": {
                "default": "Coge la cuesta de la izquierda",
                "name": "Coge la cuesta de la izquierda por {way_name}",
                "destination": "Coge la cuesta de la izquierda hacia {destination}"
            },
            "right": {
                "default": "Coge la cuesta de la derecha",
                "name": "Coge la cuesta de la derecha por {way_name}",
                "destination": "Coge la cuesta de la derecha hacia {destination}"
            },
            "sharp left": {
                "default": "Coge la cuesta de la izquierda",
                "name": "Coge la cuesta de la izquierda por {way_name}",
                "destination": "Coge la cuesta de la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Coge la cuesta de la derecha",
                "name": "Coge la cuesta de la derecha por {way_name}",
                "destination": "Coge la cuesta de la derecha hacia {destination}"
            },
            "slight left": {
                "default": "Coge la cuesta de la izquierda",
                "name": "Coge la cuesta de la izquierda por {way_name}",
                "destination": "Coge la cuesta de la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Coge la cuesta de la derecha",
                "name": "Coge la cuesta de la derecha por {way_name}",
                "destination": "Coge la cuesta de la derecha hacia {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Incorpórate en la rotonda",
                    "name": "En la rotonda sal por {way_name}",
                    "destination": "En la rotonda sal hacia {destination}"
                },
                "name": {
                    "default": "En {rotary_name}",
                    "name": "En {rotary_name} sal por {way_name}",
                    "destination": "En {rotary_name} sal hacia {destination}"
                },
                "exit": {
                    "default": "En la rotonda toma la {exit_number} salida",
                    "name": "En la rotonda toma la {exit_number} salida por {way_name}",
                    "destination": "En la rotonda toma la {exit_number} salida hacia {destination}"
                },
                "name_exit": {
                    "default": "En {rotary_name} toma la {exit_number} salida",
                    "name": "En {rotary_name} toma la {exit_number} salida por {way_name}",
                    "destination": "En {rotary_name} toma la {exit_number} salida hacia {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Entra en la rotonda y toma la {exit_number} salida",
                    "name": "Entra en la rotonda y toma la {exit_number} salida por {way_name}",
                    "destination": "Entra en la rotonda y toma la {exit_number} salida hacia {destination}"
                },
                "default": {
                    "default": "Entra en la rotonda",
                    "name": "Entra en la rotonda y sal por {way_name}",
                    "destination": "Entra en la rotonda y sal hacia {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "En la rotonda siga {modifier}",
                "name": "En la rotonda siga {modifier} por {way_name}",
                "destination": "En la rotonda siga {modifier} hacia {destination}"
            },
            "left": {
                "default": "En la rotonda gira a la izquierda",
                "name": "En la rotonda gira a la izquierda por {way_name}",
                "destination": "En la rotonda gira a la izquierda hacia {destination}"
            },
            "right": {
                "default": "En la rotonda gira a la derecha",
                "name": "En la rotonda gira a la derecha por {way_name}",
                "destination": "En la rotonda gira a la derecha hacia {destination}"
            },
            "straight": {
                "default": "En la rotonda continúa recto",
                "name": "En la rotonda continúa recto por {way_name}",
                "destination": "En la rotonda continúa recto hacia {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} en {way_name}",
                "destination": "Siga {modifier} hacia {destination}"
            },
            "left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "straight": {
                "default": "Ve recto",
                "name": "Ve recto en {way_name}",
                "destination": "Ve recto hacia {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} en {way_name}",
                "destination": "Siga {modifier} hacia {destination}"
            },
            "left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "straight": {
                "default": "Ve recto",
                "name": "Ve recto en {way_name}",
                "destination": "Ve recto hacia {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Gira {modifier}",
                "name": "Gira {modifier} por {way_name}",
                "destination": "Gira {modifier} hacia {destination}"
            },
            "left": {
                "default": "Gira a la izquierda",
                "name": "Gira a la izquierda por {way_name}",
                "destination": "Gira a la izquierda hacia {destination}"
            },
            "right": {
                "default": "Gira a la derecha",
                "name": "Gira a la derecha por {way_name}",
                "destination": "Gira a la derecha hacia {destination}"
            },
            "straight": {
                "default": "Continúa recto",
                "name": "Continúa recto por {way_name}",
                "destination": "Continúa recto hacia {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Continúa recto"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],10:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1ª",
                "2": "2ª",
                "3": "3ª",
                "4": "4ª",
                "5": "5ª",
                "6": "6ª",
                "7": "7ª",
                "8": "8ª",
                "9": "9ª",
                "10": "10ª"
            },
            "direction": {
                "north": "norte",
                "northeast": "noreste",
                "east": "este",
                "southeast": "sureste",
                "south": "sur",
                "southwest": "suroeste",
                "west": "oeste",
                "northwest": "noroeste"
            },
            "modifier": {
                "left": "izquierda",
                "right": "derecha",
                "sharp left": "cerrada a la izquierda",
                "sharp right": "cerrada a la derecha",
                "slight left": "ligeramente a la izquierda",
                "slight right": "ligeramente a la derecha",
                "straight": "recto",
                "uturn": "cambio de sentido"
            },
            "lanes": {
                "xo": "Mantengase a la derecha",
                "ox": "Mantengase a la izquierda",
                "xox": "Mantengase en el medio",
                "oxo": "Mantengase a la izquierda o derecha"
            }
        },
        "modes": {
            "ferry": {
                "default": "Coge el ferry",
                "name": "Coge el ferry {way_name}",
                "destination": "Coge el ferry a {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} y luego en {distance}, {instruction_two}",
            "two linked": "{instruction_one} y luego {instruction_two}",
            "one in distance": "A {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Has llegado a tu {nth} destino"
            },
            "left": {
                "default": "Has llegado a tu {nth} destino, a la izquierda"
            },
            "right": {
                "default": "Has llegado a tu {nth} destino, a la derecha"
            },
            "sharp left": {
                "default": "Has llegado a tu {nth} destino, a la izquierda"
            },
            "sharp right": {
                "default": "Has llegado a tu {nth} destino, a la derecha"
            },
            "slight right": {
                "default": "Has llegado a tu {nth} destino, a la derecha"
            },
            "slight left": {
                "default": "Has llegado a tu {nth} destino, a la izquierda"
            },
            "straight": {
                "default": "Has llegado a tu {nth} destino, en frente"
            }
        },
        "continue": {
            "default": {
                "default": "Gire a {modifier}",
                "name": "Cruce a la{modifier}  en {way_name}",
                "destination": "Gire a {modifier} hacia {destination}",
                "exit": "Gire a {modifier} en {way_name}"
            },
            "straight": {
                "default": "Continúe recto",
                "name": "Continúe en {way_name}",
                "destination": "Continúe hacia {destination}",
                "distance": "Continúe recto por {distance}",
                "namedistance": "Continúe recto en {way_name} por {distance}"
            },
            "sharp left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "slight left": {
                "default": "Gire a la izquierda",
                "name": "Doble levemente a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Gire a la izquierda",
                "name": "Doble levemente a la derecha en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido y continúe en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Ve a {direction}",
                "name": "Ve a {direction} en {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Gire  a {modifier}",
                "name": "Gire a {modifier} en {way_name}",
                "destination": "Gire a {modifier} hacia {destination}"
            },
            "straight": {
                "default": "Continúe recto",
                "name": "Continúe recto en {way_name}",
                "destination": "Continúe recto hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido al final de la via",
                "name": "Haz un cambio de sentido en {way_name} al final de la via",
                "destination": "Haz un cambio de sentido hacia {destination} al final de la via"
            }
        },
        "fork": {
            "default": {
                "default": "Mantengase  {modifier} en el cruce",
                "name": "Mantengase  {modifier} en el cruce en {way_name}",
                "destination": "Mantengase  {modifier} en el cruce hacia {destination}"
            },
            "slight left": {
                "default": "Mantengase a la izquierda en el cruce",
                "name": "Mantengase a la izquierda en el cruce en {way_name}",
                "destination": "Mantengase a la izquierda en el cruce hacia {destination}"
            },
            "slight right": {
                "default": "Mantengase a la derecha en el cruce",
                "name": "Mantengase a la derecha en el cruce en {way_name}",
                "destination": "Mantengase a la derecha en el cruce hacia {destination}"
            },
            "sharp left": {
                "default": "Gire a la izquierda en el cruce",
                "name": "Gire a la izquierda en el cruce en {way_name}",
                "destination": "Gire a la izquierda en el cruce hacia {destination}"
            },
            "sharp right": {
                "default": "Gire a la derecha en el cruce",
                "name": "Gire a la derecha en el cruce en {way_name}",
                "destination": "Gire a la derecha en el cruce hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Gire  a {modifier}",
                "name": "Gire a {modifier} en {way_name}",
                "destination": "Gire a {modifier} hacia {destination}"
            },
            "slight left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "sharp left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Continúe {modifier}",
                "name": "Continúe {modifier} en {way_name}",
                "destination": "Continúe {modifier} hacia {destination}"
            },
            "straight": {
                "default": "Continúe recto",
                "name": "Continúe en {way_name}",
                "destination": "Continúe hacia {destination}"
            },
            "sharp left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "slight left": {
                "default": "Continúe ligeramente a la izquierda",
                "name": "Continúe ligeramente a la izquierda en {way_name}",
                "destination": "Continúe ligeramente a la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Continúe ligeramente a la derecha",
                "name": "Continúe ligeramente a la derecha en {way_name}",
                "destination": "Continúe ligeramente a la derecha hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Continúe {modifier}",
                "name": "Continúe {modifier} en {way_name}",
                "destination": "Continúe {modifier} hacia {destination}"
            },
            "uturn": {
                "default": "Haz un cambio de sentido",
                "name": "Haz un cambio de sentido en {way_name}",
                "destination": "Haz un cambio de sentido hacia {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Tome la salida",
                "name": "Tome la salida en {way_name}",
                "destination": "Tome la salida hacia {destination}",
                "exit": "Tome la salida {exit}",
                "exit_destination": "Tome la salida {exit} hacia {destination}"
            },
            "left": {
                "default": "Tome la salida en la izquierda",
                "name": "Tome la salida en la izquierda en {way_name}",
                "destination": "Tome la salida en la izquierda en {destination}",
                "exit": "Tome la salida {exit} en la izquierda",
                "exit_destination": "Tome la salida {exit} en la izquierda hacia {destination}"
            },
            "right": {
                "default": "Tome la salida en la derecha",
                "name": "Tome la salida en la derecha en {way_name}",
                "destination": "Tome la salida en la derecha hacia {destination}",
                "exit": "Tome la salida {exit} en la derecha",
                "exit_destination": "Tome la salida {exit} en la derecha hacia {destination}"
            },
            "sharp left": {
                "default": "Ve cuesta abajo en la izquierda",
                "name": "Ve cuesta abajo en la izquierda en {way_name}",
                "destination": "Ve cuesta abajo en la izquierda hacia {destination}",
                "exit": "Tome la salida {exit} en la izquierda",
                "exit_destination": "Tome la salida {exit} en la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Ve cuesta abajo en la derecha",
                "name": "Ve cuesta abajo en la derecha en {way_name}",
                "destination": "Ve cuesta abajo en la derecha hacia {destination}",
                "exit": "Tome la salida {exit} en la derecha",
                "exit_destination": "Tome la salida {exit} en la derecha hacia {destination}"
            },
            "slight left": {
                "default": "Ve cuesta abajo en la izquierda",
                "name": "Ve cuesta abajo en la izquierda en {way_name}",
                "destination": "Ve cuesta abajo en la izquierda hacia {destination}",
                "exit": "Tome la salida {exit} en la izquierda",
                "exit_destination": "Tome la salida {exit} en la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Tome la salida en la derecha",
                "name": "Tome la salida en la derecha en {way_name}",
                "destination": "Tome la salida en la derecha hacia {destination}",
                "exit": "Tome la salida {exit} en la derecha",
                "exit_destination": "Tome la salida {exit} en la derecha hacia {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Tome la rampa",
                "name": "Tome la rampa en {way_name}",
                "destination": "Tome la rampa hacia {destination}"
            },
            "left": {
                "default": "Tome la rampa en la izquierda",
                "name": "Tome la rampa en la izquierda en {way_name}",
                "destination": "Tome la rampa en la izquierda hacia {destination}"
            },
            "right": {
                "default": "Tome la rampa en la derecha",
                "name": "Tome la rampa en la derecha en {way_name}",
                "destination": "Tome la rampa en la derecha hacia {destination}"
            },
            "sharp left": {
                "default": "Tome la rampa en la izquierda",
                "name": "Tome la rampa en la izquierda en {way_name}",
                "destination": "Tome la rampa en la izquierda hacia {destination}"
            },
            "sharp right": {
                "default": "Tome la rampa en la derecha",
                "name": "Tome la rampa en la derecha en {way_name}",
                "destination": "Tome la rampa en la derecha hacia {destination}"
            },
            "slight left": {
                "default": "Tome la rampa en la izquierda",
                "name": "Tome la rampa en la izquierda en {way_name}",
                "destination": "Tome la rampa en la izquierda hacia {destination}"
            },
            "slight right": {
                "default": "Tome la rampa en la derecha",
                "name": "Tome la rampa en la derecha en {way_name}",
                "destination": "Tome la rampa en la derecha hacia {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Entra en la rotonda",
                    "name": "Entra en la rotonda y sal en {way_name}",
                    "destination": "Entra en la rotonda y sal hacia {destination}"
                },
                "name": {
                    "default": "Entra en {rotary_name}",
                    "name": "Entra en {rotary_name} y sal en {way_name}",
                    "destination": "Entra en {rotary_name} y sal hacia {destination}"
                },
                "exit": {
                    "default": "Entra en la rotonda y toma la {exit_number} salida",
                    "name": "Entra en la rotonda y toma la {exit_number} salida a {way_name}",
                    "destination": "Entra en la rotonda y toma la {exit_number} salida hacia {destination}"
                },
                "name_exit": {
                    "default": "Entra en {rotary_name} y coge la {exit_number} salida",
                    "name": "Entra en {rotary_name} y coge la {exit_number} salida en {way_name}",
                    "destination": "Entra en {rotary_name} y coge la {exit_number} salida hacia {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Entra en la rotonda y toma la {exit_number} salida",
                    "name": "Entra en la rotonda y toma la {exit_number} salida a {way_name}",
                    "destination": "Entra en la rotonda y toma la {exit_number} salida hacia {destination}"
                },
                "default": {
                    "default": "Entra en la rotonda",
                    "name": "Entra en la rotonda y sal en {way_name}",
                    "destination": "Entra en la rotonda y sal hacia {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "En la rotonda siga {modifier}",
                "name": "En la rotonda siga {modifier} en {way_name}",
                "destination": "En la rotonda siga {modifier} hacia {destination}"
            },
            "left": {
                "default": "En la rotonda gira a la izquierda",
                "name": "En la rotonda gira a la izquierda en {way_name}",
                "destination": "En la rotonda gira a la izquierda hacia {destination}"
            },
            "right": {
                "default": "En la rotonda gira a la derecha",
                "name": "En la rotonda gira a la derecha en {way_name}",
                "destination": "En la rotonda gira a la derecha hacia {destination}"
            },
            "straight": {
                "default": "En la rotonda continúe recto",
                "name": "En la rotonda continúe recto en {way_name}",
                "destination": "En la rotonda continúe recto hacia {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} en {way_name}",
                "destination": "Siga {modifier} hacia {destination}"
            },
            "left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "straight": {
                "default": "Ve recto",
                "name": "Ve recto en {way_name}",
                "destination": "Ve recto hacia {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} en {way_name}",
                "destination": "Siga {modifier} hacia {destination}"
            },
            "left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "straight": {
                "default": "Ve recto",
                "name": "Ve recto en {way_name}",
                "destination": "Ve recto hacia {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} en {way_name}",
                "destination": "Siga {modifier} hacia {destination}"
            },
            "left": {
                "default": "Gire a la izquierda",
                "name": "Gire a la izquierda en {way_name}",
                "destination": "Gire a la izquierda hacia {destination}"
            },
            "right": {
                "default": "Gire a la derecha",
                "name": "Gire a la derecha en {way_name}",
                "destination": "Gire a la derecha hacia {destination}"
            },
            "straight": {
                "default": "Ve recto",
                "name": "Ve recto en {way_name}",
                "destination": "Ve recto hacia {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Continúe recto"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],11:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "première",
                "2": "seconde",
                "3": "troisième",
                "4": "quatrième",
                "5": "cinquième",
                "6": "sixième",
                "7": "septième",
                "8": "huitième",
                "9": "neuvième",
                "10": "dixième"
            },
            "direction": {
                "north": "le nord",
                "northeast": "le nord-est",
                "east": "l'est",
                "southeast": "le sud-est",
                "south": "le sud",
                "southwest": "le sud-ouest",
                "west": "l'ouest",
                "northwest": "le nord-ouest"
            },
            "modifier": {
                "left": "à gauche",
                "right": "à droite",
                "sharp left": "franchement à gauche",
                "sharp right": "franchement à droite",
                "slight left": "légèrement à gauche",
                "slight right": "légèrement à droite",
                "straight": "tout droit",
                "uturn": "demi-tour"
            },
            "lanes": {
                "xo": "Serrer à droite",
                "ox": "Serrer à gauche",
                "xox": "Rester au milieu",
                "oxo": "Rester à gauche ou à droite"
            }
        },
        "modes": {
            "ferry": {
                "default": "Prendre le ferry",
                "name": "Prendre le ferry {way_name}",
                "destination": "Prendre le ferry en direction de {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} then in {distance} {instruction_two}",
            "two linked": "{instruction_one} then {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Vous êtes arrivés à votre {nth} destination"
            },
            "left": {
                "default": "Vous êtes arrivés à votre {nth} destination, sur la gauche"
            },
            "right": {
                "default": "Vous êtes arrivés à votre {nth} destination, sur la droite"
            },
            "sharp left": {
                "default": "Vous êtes arrivés à votre {nth} destination, sur la gauche"
            },
            "sharp right": {
                "default": "Vous êtes arrivés à votre {nth} destination, sur la droite"
            },
            "slight right": {
                "default": "Vous êtes arrivés à votre {nth} destination, sur la droite"
            },
            "slight left": {
                "default": "Vous êtes arrivés à votre {nth} destination, sur la gauche"
            },
            "straight": {
                "default": "Vous êtes arrivés à votre {nth} destination, droit devant"
            }
        },
        "continue": {
            "default": {
                "default": "Tourner {modifier}",
                "name": "Continuer {modifier} sur {way_name}",
                "destination": "Tourner {modifier} en direction de {destination}",
                "exit": "Tourner {modifier} sur {way_name}"
            },
            "straight": {
                "default": "Continuer tout droit",
                "name": "Continuer tout droit sur {way_name}",
                "destination": "Continuer tout droit en direction de {destination}",
                "distance": "Continue straight for {distance}",
                "namedistance": "Continue on {way_name} for {distance}"
            },
            "sharp left": {
                "default": "Prendre franchement à gauche",
                "name": "Make a sharp left to stay on {way_name}",
                "destination": "Prendre franchement à gauche en direction de {destination}"
            },
            "sharp right": {
                "default": "Prendre franchement à droite",
                "name": "Make a sharp right to stay on {way_name}",
                "destination": "Prendre franchement à droite en direction de {destination}"
            },
            "slight left": {
                "default": "Continuer légèrement à gauche",
                "name": "Continuer légèrement à gauche sur {way_name}",
                "destination": "Continuer légèrement à gauche en direction de {destination}"
            },
            "slight right": {
                "default": "Continuer légèrement à droite",
                "name": "Continuer légèrement à droite sur {way_name}",
                "destination": "Continuer légèrement à droite en direction de {destination}"
            },
            "uturn": {
                "default": "Faire demi-tour",
                "name": "Faire demi-tour sur {way_name}",
                "destination": "Faire demi-tour en direction de {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Rouler vers {direction}",
                "name": "Rouler vers {direction} sur {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Tourner {modifier}",
                "name": "Tourner {modifier} sur {way_name}",
                "destination": "Tourner {modifier} en direction de {destination}"
            },
            "straight": {
                "default": "Continuer tout droit",
                "name": "Continuer tout droit sur {way_name}",
                "destination": "Continuer tout droit en direction de {destination}"
            },
            "uturn": {
                "default": "Faire demi-tour à la fin de la route",
                "name": "Faire demi-tour à la fin de la route {way_name}",
                "destination": "Faire demi-tour à la fin de la route en direction de {destination}"
            }
        },
        "fork": {
            "default": {
                "default": "Rester {modifier} à l'embranchement",
                "name": "Rester {modifier} à l'embranchement sur {way_name}",
                "destination": "Rester {modifier} à l'embranchement en direction de {destination}"
            },
            "slight left": {
                "default": "Rester à gauche à l'embranchement",
                "name": "Rester à gauche à l'embranchement sur {way_name}",
                "destination": "Rester à gauche à l'embranchement en direction de {destination}"
            },
            "slight right": {
                "default": "Rester à droite à l'embranchement",
                "name": "Rester à droite à l'embranchement sur {way_name}",
                "destination": "Rester à droite à l'embranchement en direction de {destination}"
            },
            "sharp left": {
                "default": "Prendre franchement à gauche à l'embranchement",
                "name": "Prendre franchement à gauche à l'embranchement sur {way_name}",
                "destination": "Prendre franchement à gauche à l'embranchement en direction de {destination}"
            },
            "sharp right": {
                "default": "Prendre franchement à droite à l'embranchement",
                "name": "Prendre franchement à droite à l'embranchement sur {way_name}",
                "destination": "Prendre franchement à droite à l'embranchement en direction de {destination}"
            },
            "uturn": {
                "default": "Faire demi-tour",
                "name": "Faire demi-tour sur {way_name}",
                "destination": "Faire demi-tour en direction de {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Rejoindre {modifier}",
                "name": "Rejoindre {modifier} sur {way_name}",
                "destination": "Rejoindre {modifier} en direction de {destination}"
            },
            "slight left": {
                "default": "Rejoindre par la gauche",
                "name": "Rejoindre {way_name} par la gauche",
                "destination": "Rejoindre par la gauche la route en direction de {destination}"
            },
            "slight right": {
                "default": "Rejoindre par la droite",
                "name": "Rejoindre {way_name} par la droite",
                "destination": "Rejoindre par la droite la route en direction de {destination}"
            },
            "sharp left": {
                "default": "Rejoindre par la gauche",
                "name": "Rejoindre {way_name} par la gauche",
                "destination": "Rejoindre par la gauche la route en direction de {destination}"
            },
            "sharp right": {
                "default": "Rejoindre par la droite",
                "name": "Rejoindre {way_name} par la droite",
                "destination": "Rejoindre par la droite la route en direction de {destination}"
            },
            "uturn": {
                "default": "Faire demi-tour",
                "name": "Faire demi-tour sur {way_name}",
                "destination": "Faire demi-tour en direction de {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Continuer {modifier}",
                "name": "Continuer {modifier} sur {way_name}",
                "destination": "Continuer {modifier} en direction de {destination}"
            },
            "straight": {
                "default": "Continuer tout droit",
                "name": "Continuer tout droit sur {way_name}",
                "destination": "Continuer tout droit en direction de {destination}"
            },
            "sharp left": {
                "default": "Prendre franchement à gauche",
                "name": "Prendre franchement à gauche sur {way_name}",
                "destination": "Prendre franchement à gauche en direction de {destination}"
            },
            "sharp right": {
                "default": "Prendre franchement à droite",
                "name": "Prendre franchement à droite sur {way_name}",
                "destination": "Prendre franchement à droite en direction de {destination}"
            },
            "slight left": {
                "default": "Continuer légèrement à gauche",
                "name": "Continuer légèrement à gauche sur {way_name}",
                "destination": "Continuer légèrement à gauche en direction de {destination}"
            },
            "slight right": {
                "default": "Continuer légèrement à droite",
                "name": "Continuer légèrement à droite sur {way_name}",
                "destination": "Continuer légèrement à droite en direction de {destination}"
            },
            "uturn": {
                "default": "Faire demi-tour",
                "name": "Faire demi-tour sur {way_name}",
                "destination": "Faire demi-tour en direction de {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Continuer {modifier}",
                "name": "Continuer {modifier} sur {way_name}",
                "destination": "Continuer {modifier} en direction de {destination}"
            },
            "uturn": {
                "default": "Faire demi-tour",
                "name": "Faire demi-tour sur {way_name}",
                "destination": "Faire demi-tour en direction de {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Prendre la sortie",
                "name": "Prendre la sortie sur {way_name}",
                "destination": "Prendre la sortie en direction de {destination}",
                "exit": "Take exit {exit}",
                "exit_destination": "Take exit {exit} towards {destination}"
            },
            "left": {
                "default": "Prendre la sortie à gauche",
                "name": "Prendre la sortie à gauche sur {way_name}",
                "destination": "Prendre la sortie à gauche en direction de {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "right": {
                "default": "Prendre la sortie à droite",
                "name": "Prendre la sortie à droite sur {way_name}",
                "destination": "Prendre la sortie à droite en direction de {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "sharp left": {
                "default": "Prendre la sortie à gauche",
                "name": "Prendre la sortie à gauche sur {way_name}",
                "destination": "Prendre la sortie à gauche en direction de {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "sharp right": {
                "default": "Prendre la sortie à droite",
                "name": "Prendre la sortie à droite sur {way_name}",
                "destination": "Prendre la sortie à droite en direction de {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "slight left": {
                "default": "Prendre la sortie à gauche",
                "name": "Prendre la sortie à gauche sur {way_name}",
                "destination": "Prendre la sortie à gauche en direction de {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "slight right": {
                "default": "Prendre la sortie à droite",
                "name": "Prendre la sortie à droite sur {way_name}",
                "destination": "Prendre la sortie à droite en direction de {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Prendre la sortie",
                "name": "Prendre la sortie sur {way_name}",
                "destination": "Prendre la sortie en direction de {destination}"
            },
            "left": {
                "default": "Prendre la sortie à gauche",
                "name": "Prendre la sortie à gauche sur {way_name}",
                "destination": "Prendre la sortie à gauche en direction de {destination}"
            },
            "right": {
                "default": "Prendre la sortie à droite",
                "name": "Prendre la sortie à droite sur {way_name}",
                "destination": "Prendre la sortie à droite en direction de {destination}"
            },
            "sharp left": {
                "default": "Prendre la sortie à gauche",
                "name": "Prendre la sortie à gauche sur {way_name}",
                "destination": "Prendre la sortie à gauche en direction de {destination}"
            },
            "sharp right": {
                "default": "Prendre la sortie à droite",
                "name": "Prendre la sortie à droite sur {way_name}",
                "destination": "Prendre la sortie à droite en direction de {destination}"
            },
            "slight left": {
                "default": "Prendre la sortie à gauche",
                "name": "Prendre la sortie à gauche sur {way_name}",
                "destination": "Prendre la sortie à gauche en direction de {destination}"
            },
            "slight right": {
                "default": "Prendre la sortie à droite",
                "name": "Prendre la sortie à droite sur {way_name}",
                "destination": "Prendre la sortie à droite en direction de {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Prendre le rond-point",
                    "name": "Prendre le rond-point et sortir par {way_name}",
                    "destination": "Prendre le rond-point et sortir en direction de {destination}"
                },
                "name": {
                    "default": "Prendre le rond-point {rotary_name}",
                    "name": "Prendre le rond-point {rotary_name} et sortir par {way_name}",
                    "destination": "Prendre le rond-point {rotary_name} et sortir en direction de {destination}"
                },
                "exit": {
                    "default": "Prendre le rond-point et prendre la {exit_number} sortie",
                    "name": "Prendre le rond-point et prendre la {exit_number} sortie sur {way_name}",
                    "destination": "Prendre le rond-point et prendre la {exit_number} sortie en direction de {destination}"
                },
                "name_exit": {
                    "default": "Prendre le rond-point {rotary_name} et prendre la {exit_number} sortie",
                    "name": "Prendre le rond-point {rotary_name} et prendre la {exit_number} sortie sur {way_name}",
                    "destination": "Prendre le rond-point {rotary_name} et prendre la {exit_number} sortie en direction de {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Prendre le rond-point et prendre la {exit_number} sortie",
                    "name": "Prendre le rond-point et prendre la {exit_number} sortie sur {way_name}",
                    "destination": "Prendre le rond-point et prendre la {exit_number} sortie en direction de {destination}"
                },
                "default": {
                    "default": "Prendre le rond-point",
                    "name": "Prendre le rond-point et sortir par {way_name}",
                    "destination": "Prendre le rond-point et sortir en direction de {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Au rond-point, tourner {modifier}",
                "name": "Au rond-point, tourner {modifier} sur {way_name}",
                "destination": "Au rond-point, tourner {modifier} en direction de {destination}"
            },
            "left": {
                "default": "Au rond-point, tourner à gauche",
                "name": "Au rond-point, tourner à gauche sur {way_name}",
                "destination": "Au rond-point, tourner à gauche en direction de {destination}"
            },
            "right": {
                "default": "Au rond-point, tourner à droite",
                "name": "Au rond-point, tourner à droite sur {way_name}",
                "destination": "Au rond-point, tourner à droite en direction de {destination}"
            },
            "straight": {
                "default": "Au rond-point, continuer tout droit",
                "name": "Au rond-point, continuer tout droit sur {way_name}",
                "destination": "Au rond-point, continuer tout droit en direction de {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Tourner {modifier}",
                "name": "Tourner {modifier} sur {way_name}",
                "destination": "Tourner {modifier} en direction de {destination}"
            },
            "left": {
                "default": "Tourner à gauche",
                "name": "Tourner à gauche sur {way_name}",
                "destination": "Tourner à gauche en direction de {destination}"
            },
            "right": {
                "default": "Tourner à droite",
                "name": "Tourner à droite sur {way_name}",
                "destination": "Tourner à droite en direction de {destination}"
            },
            "straight": {
                "default": "Aller tout droit",
                "name": "Aller tout droit sur {way_name}",
                "destination": "Aller tout droit en direction de {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Tourner {modifier}",
                "name": "Tourner {modifier} sur {way_name}",
                "destination": "Tourner {modifier} en direction de {destination}"
            },
            "left": {
                "default": "Tourner à gauche",
                "name": "Tourner à gauche sur {way_name}",
                "destination": "Tourner à gauche en direction de {destination}"
            },
            "right": {
                "default": "Tourner à droite",
                "name": "Tourner à droite sur {way_name}",
                "destination": "Tourner à droite en direction de {destination}"
            },
            "straight": {
                "default": "Aller tout droit",
                "name": "Aller tout droit sur {way_name}",
                "destination": "Aller tout droit en direction de {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Tourner {modifier}",
                "name": "Tourner {modifier} sur {way_name}",
                "destination": "Tourner {modifier} en direction de {destination}"
            },
            "left": {
                "default": "Tourner à gauche",
                "name": "Tourner à gauche sur {way_name}",
                "destination": "Tourner à gauche en direction de {destination}"
            },
            "right": {
                "default": "Tourner à droite",
                "name": "Tourner à droite sur {way_name}",
                "destination": "Tourner à droite en direction de {destination}"
            },
            "straight": {
                "default": "Aller tout droit",
                "name": "Aller tout droit sur {way_name}",
                "destination": "Aller tout droit en direction de {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Continuer tout droit"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],12:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1",
                "2": "2",
                "3": "3",
                "4": "4",
                "5": "5",
                "6": "6",
                "7": "7",
                "8": "8",
                "9": "9",
                "10": "10"
            },
            "direction": {
                "north": "utara",
                "northeast": "timur laut",
                "east": "timur",
                "southeast": "tenggara",
                "south": "selatan",
                "southwest": "barat daya",
                "west": "barat",
                "northwest": "barat laut"
            },
            "modifier": {
                "left": "kiri",
                "right": "kanan",
                "sharp left": "tajam kiri",
                "sharp right": "tajam kanan",
                "slight left": "agak ke kiri",
                "slight right": "agak ke kanan",
                "straight": "lurus",
                "uturn": "putar balik"
            },
            "lanes": {
                "xo": "Tetap di kanan",
                "ox": "Tetap di kiri",
                "xox": "Tetap di tengah",
                "oxo": "Tetap di kiri atau kanan"
            }
        },
        "modes": {
            "ferry": {
                "default": "Naik ferry",
                "name": "Naik ferry di {way_name}",
                "destination": "Naik ferry menuju {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} then in {distance} {instruction_two}",
            "two linked": "{instruction_one} then {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Anda telah tiba di tujuan ke-{nth}"
            },
            "left": {
                "default": "Anda telah tiba di tujuan ke-{nth}, di sebelah kiri"
            },
            "right": {
                "default": "Anda telah tiba di tujuan ke-{nth}, di sebelah kanan"
            },
            "sharp left": {
                "default": "Anda telah tiba di tujuan ke-{nth}, di sebelah kiri"
            },
            "sharp right": {
                "default": "Anda telah tiba di tujuan ke-{nth}, di sebelah kanan"
            },
            "slight right": {
                "default": "Anda telah tiba di tujuan ke-{nth}, di sebelah kanan"
            },
            "slight left": {
                "default": "Anda telah tiba di tujuan ke-{nth}, di sebelah kiri"
            },
            "straight": {
                "default": "Anda telah tiba di tujuan ke-{nth}, lurus saja"
            }
        },
        "continue": {
            "default": {
                "default": "Belok {modifier}",
                "name": "Terus {modifier} ke {way_name}",
                "destination": "Belok {modifier} menuju {destination}",
                "exit": "Belok {modifier} ke {way_name}"
            },
            "straight": {
                "default": "Lurus terus",
                "name": "Terus ke {way_name}",
                "destination": "Terus menuju {destination}",
                "distance": "Continue straight for {distance}",
                "namedistance": "Continue on {way_name} for {distance}"
            },
            "sharp left": {
                "default": "Belok kiri tajam",
                "name": "Make a sharp left to stay on {way_name}",
                "destination": "Belok kiri tajam menuju {destination}"
            },
            "sharp right": {
                "default": "Belok kanan tajam",
                "name": "Make a sharp right to stay on {way_name}",
                "destination": "Belok kanan tajam menuju {destination}"
            },
            "slight left": {
                "default": "Tetap agak di kiri",
                "name": "Tetap agak di kiri ke {way_name}",
                "destination": "Tetap agak di kiri menuju {destination}"
            },
            "slight right": {
                "default": "Tetap agak di kanan",
                "name": "Tetap agak di kanan ke {way_name}",
                "destination": "Tetap agak di kanan menuju {destination}"
            },
            "uturn": {
                "default": "Putar balik",
                "name": "Putar balik ke arah {way_name}",
                "destination": "Putar balik menuju {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Arah {direction}",
                "name": "Arah {direction} di {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Belok {modifier}",
                "name": "Belok {modifier} ke {way_name}",
                "destination": "Belok {modifier} menuju {destination}"
            },
            "straight": {
                "default": "Lurus terus",
                "name": "Tetap lurus ke {way_name} ",
                "destination": "Tetap lurus menuju {destination}"
            },
            "uturn": {
                "default": "Putar balik di akhir jalan",
                "name": "Putar balik di {way_name} di akhir jalan",
                "destination": "Putar balik menuju {destination} di akhir jalan"
            }
        },
        "fork": {
            "default": {
                "default": "Tetap {modifier} di pertigaan",
                "name": "Tetap {modifier} di pertigaan ke {way_name}",
                "destination": "Tetap {modifier} di pertigaan menuju {destination}"
            },
            "slight left": {
                "default": "Tetap di kiri pada pertigaan",
                "name": "Tetap di kiri pada pertigaan ke arah {way_name}",
                "destination": "Tetap di kiri pada pertigaan menuju {destination}"
            },
            "slight right": {
                "default": "Tetap di kanan pada pertigaan",
                "name": "Tetap di kanan pada pertigaan ke arah {way_name}",
                "destination": "Tetap di kanan pada pertigaan menuju {destination}"
            },
            "sharp left": {
                "default": "Belok kiri pada pertigaan",
                "name": "Belok kiri pada pertigaan ke arah {way_name}",
                "destination": "Belok kiri pada pertigaan menuju {destination}"
            },
            "sharp right": {
                "default": "Belok kanan pada pertigaan",
                "name": "Belok kanan pada pertigaan ke arah {way_name}",
                "destination": "Belok kanan pada pertigaan menuju {destination}"
            },
            "uturn": {
                "default": "Putar balik",
                "name": "Putar balik ke arah {way_name}",
                "destination": "Putar balik menuju {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Bergabung {modifier}",
                "name": "Bergabung {modifier} ke arah {way_name}",
                "destination": "Bergabung {modifier} menuju {destination}"
            },
            "slight left": {
                "default": "Bergabung di kiri",
                "name": "Bergabung di kiri ke arah {way_name}",
                "destination": "Bergabung di kiri menuju {destination}"
            },
            "slight right": {
                "default": "Bergabung di kanan",
                "name": "Bergabung di kanan ke arah {way_name}",
                "destination": "Bergabung di kanan menuju {destination}"
            },
            "sharp left": {
                "default": "Bergabung di kiri",
                "name": "Bergabung di kiri ke arah {way_name}",
                "destination": "Bergabung di kiri menuju {destination}"
            },
            "sharp right": {
                "default": "Bergabung di kanan",
                "name": "Bergabung di kanan ke arah {way_name}",
                "destination": "Bergabung di kanan menuju {destination}"
            },
            "uturn": {
                "default": "Putar balik",
                "name": "Putar balik ke arah {way_name}",
                "destination": "Putar balik menuju {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Lanjutkan {modifier}",
                "name": "Lanjutkan {modifier} menuju {way_name}",
                "destination": "Lanjutkan {modifier} menuju {destination}"
            },
            "straight": {
                "default": "Lurus terus",
                "name": "Terus ke {way_name}",
                "destination": "Terus menuju {destination}"
            },
            "sharp left": {
                "default": "Belok kiri tajam",
                "name": "Belok kiri tajam ke arah {way_name}",
                "destination": "Belok kiri tajam menuju {destination}"
            },
            "sharp right": {
                "default": "Belok kanan tajam",
                "name": "Belok kanan tajam ke arah {way_name}",
                "destination": "Belok kanan tajam menuju {destination}"
            },
            "slight left": {
                "default": "Lanjut dengan agak ke kiri",
                "name": "Lanjut dengan agak di kiri ke {way_name}",
                "destination": "Tetap agak di kiri menuju {destination}"
            },
            "slight right": {
                "default": "Tetap agak di kanan",
                "name": "Tetap agak di kanan ke {way_name}",
                "destination": "Tetap agak di kanan menuju {destination}"
            },
            "uturn": {
                "default": "Putar balik",
                "name": "Putar balik ke arah {way_name}",
                "destination": "Putar balik menuju {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Lanjutkan {modifier}",
                "name": "Lanjutkan {modifier} menuju {way_name}",
                "destination": "Lanjutkan {modifier} menuju {destination}"
            },
            "uturn": {
                "default": "Putar balik",
                "name": "Putar balik ke arah {way_name}",
                "destination": "Putar balik menuju {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Ambil jalan melandai",
                "name": "Ambil jalan melandai ke {way_name}",
                "destination": "Ambil jalan melandai menuju {destination}",
                "exit": "Take exit {exit}",
                "exit_destination": "Take exit {exit} towards {destination}"
            },
            "left": {
                "default": "Ambil jalan yang melandai di sebelah kiri",
                "name": "Ambil jalan melandai di sebelah kiri ke arah {way_name}",
                "destination": "Ambil jalan melandai di sebelah kiri menuju {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "right": {
                "default": "Ambil jalan melandai di sebelah kanan",
                "name": "Ambil jalan melandai di sebelah kanan ke {way_name}",
                "destination": "Ambil jalan melandai di sebelah kanan menuju {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "sharp left": {
                "default": "Ambil jalan yang melandai di sebelah kiri",
                "name": "Ambil jalan melandai di sebelah kiri ke arah {way_name}",
                "destination": "Ambil jalan melandai di sebelah kiri menuju {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "sharp right": {
                "default": "Ambil jalan melandai di sebelah kanan",
                "name": "Ambil jalan melandai di sebelah kanan ke {way_name}",
                "destination": "Ambil jalan melandai di sebelah kanan menuju {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "slight left": {
                "default": "Ambil jalan yang melandai di sebelah kiri",
                "name": "Ambil jalan melandai di sebelah kiri ke arah {way_name}",
                "destination": "Ambil jalan melandai di sebelah kiri menuju {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "slight right": {
                "default": "Ambil jalan melandai di sebelah kanan",
                "name": "Ambil jalan melandai di sebelah kanan ke {way_name}",
                "destination": "Ambil jalan melandai di sebelah kanan  menuju {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Ambil jalan melandai",
                "name": "Ambil jalan melandai ke {way_name}",
                "destination": "Ambil jalan melandai menuju {destination}"
            },
            "left": {
                "default": "Ambil jalan yang melandai di sebelah kiri",
                "name": "Ambil jalan melandai di sebelah kiri ke arah {way_name}",
                "destination": "Ambil jalan melandai di sebelah kiri menuju {destination}"
            },
            "right": {
                "default": "Ambil jalan melandai di sebelah kanan",
                "name": "Ambil jalan melandai di sebelah kanan ke {way_name}",
                "destination": "Ambil jalan melandai di sebelah kanan  menuju {destination}"
            },
            "sharp left": {
                "default": "Ambil jalan yang melandai di sebelah kiri",
                "name": "Ambil jalan melandai di sebelah kiri ke arah {way_name}",
                "destination": "Ambil jalan melandai di sebelah kiri menuju {destination}"
            },
            "sharp right": {
                "default": "Ambil jalan melandai di sebelah kanan",
                "name": "Ambil jalan melandai di sebelah kanan ke {way_name}",
                "destination": "Ambil jalan melandai di sebelah kanan  menuju {destination}"
            },
            "slight left": {
                "default": "Ambil jalan yang melandai di sebelah kiri",
                "name": "Ambil jalan melandai di sebelah kiri ke arah {way_name}",
                "destination": "Ambil jalan melandai di sebelah kiri menuju {destination}"
            },
            "slight right": {
                "default": "Ambil jalan melandai di sebelah kanan",
                "name": "Ambil jalan melandai di sebelah kanan ke {way_name}",
                "destination": "Ambil jalan melandai di sebelah kanan  menuju {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Masuk bundaran",
                    "name": "Masuk bundaran dan keluar arah {way_name}",
                    "destination": "Masuk bundaran dan keluar menuju {destination}"
                },
                "name": {
                    "default": "Masuk {rotary_name}",
                    "name": "Masuk {rotary_name} dan keluar arah {way_name}",
                    "destination": "Masuk {rotary_name} dan keluar menuju {destination}"
                },
                "exit": {
                    "default": "Masuk bundaran dan ambil jalan keluar {exit_number}",
                    "name": "Masuk bundaran dan ambil jalan keluar {exit_number} arah {way_name}",
                    "destination": "Masuk bundaran dan ambil jalan keluar {exit_number} menuju {destination}"
                },
                "name_exit": {
                    "default": "Masuk {rotary_name} dan ambil jalan keluar {exit_number}",
                    "name": "Masuk {rotary_name} dan ambil jalan keluar {exit_number} arah {way_name}",
                    "destination": "Masuk {rotary_name} dan ambil jalan keluar {exit_number} menuju {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Masuk bundaran dan ambil jalan keluar {exit_number}",
                    "name": "Masuk bundaran dan ambil jalan keluar {exit_number} arah {way_name}",
                    "destination": "Masuk bundaran dan ambil jalan keluar {exit_number} menuju {destination}"
                },
                "default": {
                    "default": "Masuk bundaran",
                    "name": "Masuk bundaran dan keluar arah {way_name}",
                    "destination": "Masuk bundaran dan keluar menuju {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Di bundaran, lakukan {modifier}",
                "name": "Di bundaran, lakukan {modifier} ke arah {way_name}",
                "destination": "Di bundaran, lakukan {modifier} menuju {destination}"
            },
            "left": {
                "default": "Di bundaran belok kiri",
                "name": "Di bundaran, belok kiri arah {way_name}",
                "destination": "Di bundaran, belok kiri menuju {destination}"
            },
            "right": {
                "default": "Di bundaran belok kanan",
                "name": "Di bundaran belok kanan ke arah {way_name}",
                "destination": "Di bundaran belok kanan menuju {destination}"
            },
            "straight": {
                "default": "Di bundaran tetap lurus",
                "name": "Di bundaran tetap lurus ke arah {way_name}",
                "destination": "Di bundaran tetap lurus menuju {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Lakukan {modifier}",
                "name": "Lakukan {modifier} ke arah {way_name}",
                "destination": "Lakukan {modifier} menuju {destination}"
            },
            "left": {
                "default": "Belok kiri",
                "name": "Belok kiri ke {way_name}",
                "destination": "Belok kiri menuju {destination}"
            },
            "right": {
                "default": "Belok kanan",
                "name": "Belok kanan ke {way_name}",
                "destination": "Belok kanan menuju {destination}"
            },
            "straight": {
                "default": "Lurus",
                "name": "Lurus arah {way_name}",
                "destination": "Lurus menuju {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Lakukan {modifier}",
                "name": "Lakukan {modifier} ke arah {way_name}",
                "destination": "Lakukan {modifier} menuju {destination}"
            },
            "left": {
                "default": "Belok kiri",
                "name": "Belok kiri ke {way_name}",
                "destination": "Belok kiri menuju {destination}"
            },
            "right": {
                "default": "Belok kanan",
                "name": "Belok kanan ke {way_name}",
                "destination": "Belok kanan menuju {destination}"
            },
            "straight": {
                "default": "Lurus",
                "name": "Lurus arah {way_name}",
                "destination": "Lurus menuju {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Lakukan {modifier}",
                "name": "Lakukan {modifier} ke arah {way_name}",
                "destination": "Lakukan {modifier} menuju {destination}"
            },
            "left": {
                "default": "Belok kiri",
                "name": "Belok kiri ke {way_name}",
                "destination": "Belok kiri menuju {destination}"
            },
            "right": {
                "default": "Belok kanan",
                "name": "Belok kanan ke {way_name}",
                "destination": "Belok kanan menuju {destination}"
            },
            "straight": {
                "default": "Lurus",
                "name": "Lurus arah {way_name}",
                "destination": "Lurus menuju {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Lurus terus"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],13:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1ª",
                "2": "2ª",
                "3": "3ª",
                "4": "4ª",
                "5": "5ª",
                "6": "6ª",
                "7": "7ª",
                "8": "8ª",
                "9": "9ª",
                "10": "10ª"
            },
            "direction": {
                "north": "nord",
                "northeast": "nord-est",
                "east": "est",
                "southeast": "sud-est",
                "south": "sud",
                "southwest": "sud-ovest",
                "west": "ovest",
                "northwest": "nord-ovest"
            },
            "modifier": {
                "left": "sinistra",
                "right": "destra",
                "sharp left": "sinistra",
                "sharp right": "destra",
                "slight left": "sinistra leggermente",
                "slight right": "destra leggermente",
                "straight": "dritto",
                "uturn": "inversione a U"
            },
            "lanes": {
                "xo": "Mantieni la destra",
                "ox": "Mantieni la sinistra",
                "xox": "Rimani in mezzo",
                "oxo": "Mantieni la destra o la sinistra"
            }
        },
        "modes": {
            "ferry": {
                "default": "Prendi il traghetto",
                "name": "Prendi il traghetto {way_name}",
                "destination": "Prendi il traghetto verso {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one}, poi tra {distance},{instruction_two}",
            "two linked": "{instruction_one}, poi {instruction_two}",
            "one in distance": "tra {distance} {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Sei arrivato alla tua {nth} destinazione"
            },
            "left": {
                "default": "sei arrivato alla tua {nth} destinazione, sulla sinistra"
            },
            "right": {
                "default": "sei arrivato alla tua {nth} destinazione, sulla destra"
            },
            "sharp left": {
                "default": "sei arrivato alla tua {nth} destinazione, sulla sinistra"
            },
            "sharp right": {
                "default": "sei arrivato alla tua {nth} destinazione, sulla destra"
            },
            "slight right": {
                "default": "sei arrivato alla tua {nth} destinazione, sulla destra"
            },
            "slight left": {
                "default": "sei arrivato alla tua {nth} destinazione, sulla sinistra"
            },
            "straight": {
                "default": "sei arrivato alla tua {nth} destinazione, si trova davanti a te"
            }
        },
        "continue": {
            "default": {
                "default": "Gira a {modifier}",
                "name": "Gira a {modifier} per stare su {way_name}",
                "destination": "Gira a {modifier} verso {destination}",
                "exit": "Gira a {modifier} in {way_name}"
            },
            "straight": {
                "default": "Continua dritto",
                "name": "Continua dritto per stare su {way_name}",
                "destination": "Continua verso {destination}",
                "distance": "Continua dritto per {distance}",
                "namedistance": "Continua su {way_name} per {distance}"
            },
            "sharp left": {
                "default": "Svolta a sinistra",
                "name": "Fai una stretta curva a sinistra per stare su {way_name}",
                "destination": "Svolta a sinistra verso {destination}"
            },
            "sharp right": {
                "default": "Svolta a destra",
                "name": "Fau una stretta curva a destra per stare su {way_name}",
                "destination": "Svolta a destra verso {destination}"
            },
            "slight left": {
                "default": "Fai una leggera curva a sinistra",
                "name": "Fai una leggera curva a sinistra per stare su {way_name}",
                "destination": "Fai una leggera curva a sinistra verso {destination}"
            },
            "slight right": {
                "default": "Fai una leggera curva a destra",
                "name": "Fai una leggera curva a destra per stare su {way_name}",
                "destination": "Fai una leggera curva a destra verso {destination}"
            },
            "uturn": {
                "default": "Fai un'inversione a U",
                "name": "Fai un'inversione ad U poi continua su {way_name}",
                "destination": "Fai un'inversione a U verso {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Continua verso {direction}",
                "name": "Continua verso {direction} in {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Gira a {modifier}",
                "name": "Gira a {modifier} in {way_name}",
                "destination": "Gira a {modifier} verso {destination}"
            },
            "straight": {
                "default": "Continua dritto",
                "name": "Continua dritto in {way_name}",
                "destination": "Continua dritto verso {destination}"
            },
            "uturn": {
                "default": "Fai un'inversione a U alla fine della strada",
                "name": "Fai un'inversione a U in {way_name} alla fine della strada",
                "destination": "Fai un'inversione a U verso {destination} alla fine della strada"
            }
        },
        "fork": {
            "default": {
                "default": "Mantieni la {modifier} al bivio",
                "name": "Mantieni la {modifier} al bivio in {way_name}",
                "destination": "Mantieni la {modifier} al bivio verso {destination}"
            },
            "slight left": {
                "default": "Mantieni la sinistra al bivio",
                "name": "Mantieni la sinistra al bivio in {way_name}",
                "destination": "Mantieni la sinistra al bivio verso {destination}"
            },
            "slight right": {
                "default": "Mantieni la destra al bivio",
                "name": "Mantieni la destra al bivio in {way_name}",
                "destination": "Mantieni la destra al bivio verso {destination}"
            },
            "sharp left": {
                "default": "Svolta a sinistra al bivio",
                "name": "Svolta a sinistra al bivio in {way_name}",
                "destination": "Svolta a sinistra al bivio verso {destination}"
            },
            "sharp right": {
                "default": "Svolta a destra al bivio",
                "name": "Svolta a destra al bivio in {way_name}",
                "destination": "Svolta a destra al bivio verso {destination}"
            },
            "uturn": {
                "default": "Fai un'inversione a U",
                "name": "Fai un'inversione a U in {way_name}",
                "destination": "Fai un'inversione a U verso {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Immettiti a {modifier}",
                "name": "Immettiti {modifier} in {way_name}",
                "destination": "Immettiti {modifier} verso {destination}"
            },
            "slight left": {
                "default": "Immettiti a sinistra",
                "name": "Immettiti a sinistra in {way_name}",
                "destination": "Immettiti a sinistra verso {destination}"
            },
            "slight right": {
                "default": "Immettiti a destra",
                "name": "Immettiti a destra in {way_name}",
                "destination": "Immettiti a destra verso {destination}"
            },
            "sharp left": {
                "default": "Immettiti a sinistra",
                "name": "Immettiti a sinistra in {way_name}",
                "destination": "Immettiti a sinistra verso {destination}"
            },
            "sharp right": {
                "default": "Immettiti a destra",
                "name": "Immettiti a destra in {way_name}",
                "destination": "Immettiti a destra verso {destination}"
            },
            "uturn": {
                "default": "Fai un'inversione a U",
                "name": "Fai un'inversione a U in {way_name}",
                "destination": "Fai un'inversione a U verso {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Continua a {modifier}",
                "name": "Continua a {modifier} in {way_name}",
                "destination": "Continua a {modifier} verso {destination}"
            },
            "straight": {
                "default": "Continua dritto",
                "name": "Continua in {way_name}",
                "destination": "Continua verso {destination}"
            },
            "sharp left": {
                "default": "Svolta a sinistra",
                "name": "Svolta a sinistra in {way_name}",
                "destination": "Svolta a sinistra verso {destination}"
            },
            "sharp right": {
                "default": "Svolta a destra",
                "name": "Svolta a destra in {way_name}",
                "destination": "Svolta a destra verso {destination}"
            },
            "slight left": {
                "default": "Continua leggermente a sinistra",
                "name": "Continua leggermente a sinistra in {way_name}",
                "destination": "Continua leggermente a sinistra verso {destination}"
            },
            "slight right": {
                "default": "Continua leggermente a destra",
                "name": "Continua leggermente a destra in {way_name} ",
                "destination": "Continua leggermente a destra verso {destination}"
            },
            "uturn": {
                "default": "Fai un'inversione a U",
                "name": "Fai un'inversione a U in {way_name}",
                "destination": "Fai un'inversione a U verso {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Continua a {modifier}",
                "name": "Continua a {modifier} in {way_name}",
                "destination": "Continua a {modifier} verso {destination}"
            },
            "uturn": {
                "default": "Fai un'inversione a U",
                "name": "Fai un'inversione a U in {way_name}",
                "destination": "Fai un'inversione a U verso {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Prendi la rampa",
                "name": "Prendi la rampa in {way_name}",
                "destination": "Prendi la rampa verso {destination}",
                "exit": "Prendi l'uscita {exit}",
                "exit_destination": "Prendi l'uscita  {exit} verso {destination}"
            },
            "left": {
                "default": "Prendi la rampa a sinistra",
                "name": "Prendi la rampa a sinistra in {way_name}",
                "destination": "Prendi la rampa a sinistra verso {destination}",
                "exit": "Prendi l'uscita {exit} a sinistra",
                "exit_destination": "Prendi la {exit}  uscita a sinistra verso {destination}"
            },
            "right": {
                "default": "Prendi la rampa a destra",
                "name": "Prendi la rampa a destra in {way_name}",
                "destination": "Prendi la rampa a destra verso {destination}",
                "exit": "Prendi la {exit} uscita a destra",
                "exit_destination": "Prendi la {exit} uscita a destra verso {destination}"
            },
            "sharp left": {
                "default": "Prendi la rampa a sinistra",
                "name": "Prendi la rampa a sinistra in {way_name}",
                "destination": "Prendi la rampa a sinistra verso {destination}",
                "exit": "Prendi l'uscita {exit} a sinistra",
                "exit_destination": "Prendi la {exit}  uscita a sinistra verso {destination}"
            },
            "sharp right": {
                "default": "Prendi la rampa a destra",
                "name": "Prendi la rampa a destra in {way_name}",
                "destination": "Prendi la rampa a destra verso {destination}",
                "exit": "Prendi la {exit} uscita a destra",
                "exit_destination": "Prendi la {exit} uscita a destra verso {destination}"
            },
            "slight left": {
                "default": "Prendi la rampa a sinistra",
                "name": "Prendi la rampa a sinistra in {way_name}",
                "destination": "Prendi la rampa a sinistra verso {destination}",
                "exit": "Prendi l'uscita {exit} a sinistra",
                "exit_destination": "Prendi la {exit}  uscita a sinistra verso {destination}"
            },
            "slight right": {
                "default": "Prendi la rampa a destra",
                "name": "Prendi la rampa a destra in {way_name}",
                "destination": "Prendi la rampa a destra verso {destination}",
                "exit": "Prendi la {exit} uscita a destra",
                "exit_destination": "Prendi la {exit} uscita a destra verso {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Prendi la rampa",
                "name": "Prendi la rampa in {way_name}",
                "destination": "Prendi la rampa verso {destination}"
            },
            "left": {
                "default": "Prendi la rampa a sinistra",
                "name": "Prendi la rampa a sinistra in {way_name}",
                "destination": "Prendi la rampa a sinistra verso {destination}"
            },
            "right": {
                "default": "Prendi la rampa a destra",
                "name": "Prendi la rampa a destra in {way_name}",
                "destination": "Prendi la rampa a destra verso {destination}"
            },
            "sharp left": {
                "default": "Prendi la rampa a sinistra",
                "name": "Prendi la rampa a sinistra in {way_name}",
                "destination": "Prendi la rampa a sinistra verso {destination}"
            },
            "sharp right": {
                "default": "Prendi la rampa a destra",
                "name": "Prendi la rampa a destra in {way_name}",
                "destination": "Prendi la rampa a destra verso {destination}"
            },
            "slight left": {
                "default": "Prendi la rampa a sinistra",
                "name": "Prendi la rampa a sinistra in {way_name}",
                "destination": "Prendi la rampa a sinistra verso {destination}"
            },
            "slight right": {
                "default": "Prendi la rampa a destra",
                "name": "Prendi la rampa a destra in {way_name}",
                "destination": "Prendi la rampa a destra verso {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Immettiti nella rotonda",
                    "name": "Immettiti nella ritonda ed esci in {way_name}",
                    "destination": "Immettiti nella ritonda ed esci verso {destination}"
                },
                "name": {
                    "default": "Immettiti in {rotary_name}",
                    "name": "Immettiti in {rotary_name} ed esci su {way_name}",
                    "destination": "Immettiti in {rotary_name} ed esci verso {destination}"
                },
                "exit": {
                    "default": "Immettiti nella rotonda e prendi la {exit_number} uscita",
                    "name": "Immettiti nella rotonda e prendi la {exit_number} uscita in {way_name}",
                    "destination": "Immettiti nella rotonda e prendi la {exit_number} uscita verso   {destination}"
                },
                "name_exit": {
                    "default": "Immettiti in {rotary_name} e prendi la {exit_number} uscita",
                    "name": "Immettiti in {rotary_name} e prendi la {exit_number} uscita in {way_name}",
                    "destination": "Immettiti in {rotary_name} e prendi la {exit_number}  uscita verso {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Immettiti nella rotonda e prendi la {exit_number} uscita",
                    "name": "Immettiti nella rotonda e prendi la {exit_number} uscita in {way_name}",
                    "destination": "Immettiti nella rotonda e prendi la {exit_number} uscita verso {destination}"
                },
                "default": {
                    "default": "Entra nella rotonda",
                    "name": "Entra nella rotonda e prendi l'uscita in {way_name}",
                    "destination": "Entra nella rotonda e prendi l'uscita verso {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Alla rotonda fai una {modifier}",
                "name": "Alla rotonda fai una {modifier} in {way_name}",
                "destination": "Alla rotonda fai una {modifier} verso {destination}"
            },
            "left": {
                "default": "Alla rotonda svolta a sinistra",
                "name": "Alla rotonda svolta a sinistra in {way_name}",
                "destination": "Alla rotonda svolta a sinistra verso {destination}"
            },
            "right": {
                "default": "Alla rotonda svolta a destra",
                "name": "Alla rotonda svolta a destra in {way_name}",
                "destination": "Alla rotonda svolta a destra verso {destination}"
            },
            "straight": {
                "default": "Alla rotonda prosegui dritto",
                "name": "Alla rotonda prosegui dritto in {way_name}",
                "destination": "Alla rotonda prosegui dritto verso {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Fai una {modifier}",
                "name": "Fai una {modifier} in {way_name}",
                "destination": "Fai una {modifier} verso {destination}"
            },
            "left": {
                "default": "Svolta a sinistra",
                "name": "Svolta a sinistra in {way_name}",
                "destination": "Svolta a sinistra verso {destination}"
            },
            "right": {
                "default": "Gira a destra",
                "name": "Svolta a destra in {way_name}",
                "destination": "Svolta a destra verso {destination}"
            },
            "straight": {
                "default": "Prosegui dritto",
                "name": "Continua su {way_name}",
                "destination": "Continua verso {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Fai una {modifier}",
                "name": "Fai una {modifier} in {way_name}",
                "destination": "Fai una {modifier} verso {destination}"
            },
            "left": {
                "default": "Svolta a sinistra",
                "name": "Svolta a sinistra in {way_name}",
                "destination": "Svolta a sinistra verso {destination}"
            },
            "right": {
                "default": "Gira a destra",
                "name": "Svolta a destra in {way_name}",
                "destination": "Svolta a destra verso {destination}"
            },
            "straight": {
                "default": "Prosegui dritto",
                "name": "Continua su {way_name}",
                "destination": "Continua verso {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Fai una {modifier}",
                "name": "Fai una {modifier} in {way_name}",
                "destination": "Fai una {modifier} verso {destination}"
            },
            "left": {
                "default": "Svolta a sinistra",
                "name": "Svolta a sinistra in {way_name}",
                "destination": "Svolta a sinistra verso {destination}"
            },
            "right": {
                "default": "Gira a destra",
                "name": "Svolta a destra in {way_name}",
                "destination": "Svolta a destra verso {destination}"
            },
            "straight": {
                "default": "Prosegui dritto",
                "name": "Continua su {way_name}",
                "destination": "Continua verso {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Continua dritto"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],14:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1e",
                "2": "2e",
                "3": "3e",
                "4": "4e",
                "5": "5e",
                "6": "6e",
                "7": "7e",
                "8": "8e",
                "9": "9e",
                "10": "10e"
            },
            "direction": {
                "north": "noord",
                "northeast": "noordoost",
                "east": "oost",
                "southeast": "zuidoost",
                "south": "zuid",
                "southwest": "zuidwest",
                "west": "west",
                "northwest": "noordwest"
            },
            "modifier": {
                "left": "links",
                "right": "rechts",
                "sharp left": "linksaf",
                "sharp right": "rechtsaf",
                "slight left": "links",
                "slight right": "rechts",
                "straight": "rechtdoor",
                "uturn": "omkeren"
            },
            "lanes": {
                "xo": "Rechts aanhouden",
                "ox": "Links aanhouden",
                "xox": "In het midden blijven",
                "oxo": "Links of rechts blijven"
            }
        },
        "modes": {
            "ferry": {
                "default": "Neem het veer",
                "name": "Neem het veer {way_name}",
                "destination": "Neem het veer naar {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} then in {distance} {instruction_two}",
            "two linked": "{instruction_one} then {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Je bent gearriveerd op de {nth} bestemming."
            },
            "left": {
                "default": "Je bent gearriveerd. De {nth} bestemming bevindt zich links."
            },
            "right": {
                "default": "Je bent gearriveerd. De {nth} bestemming bevindt zich rechts."
            },
            "sharp left": {
                "default": "Je bent gearriveerd. De {nth} bestemming bevindt zich links."
            },
            "sharp right": {
                "default": "Je bent gearriveerd. De {nth} bestemming bevindt zich rechts."
            },
            "slight right": {
                "default": "Je bent gearriveerd. De {nth} bestemming bevindt zich rechts."
            },
            "slight left": {
                "default": "Je bent gearriveerd. De {nth} bestemming bevindt zich links."
            },
            "straight": {
                "default": "Je bent gearriveerd. De {nth} bestemming bevindt zich voor je."
            }
        },
        "continue": {
            "default": {
                "default": "Ga {modifier}",
                "name": "Ga {modifier} naar {way_name}",
                "destination": "Ga {modifier} richting {destination}",
                "exit": "Ga {modifier} naar {way_name}"
            },
            "straight": {
                "default": "Ga rechtdoor",
                "name": "Ga rechtdoor naar {way_name}",
                "destination": "Ga rechtdoor richting {destination}",
                "distance": "Continue straight for {distance}",
                "namedistance": "Continue on {way_name} for {distance}"
            },
            "sharp left": {
                "default": "Linksaf",
                "name": "Make a sharp left to stay on {way_name}",
                "destination": "Linksaf richting {destination}"
            },
            "sharp right": {
                "default": "Rechtsaf",
                "name": "Make a sharp right to stay on {way_name}",
                "destination": "Rechtsaf richting {destination}"
            },
            "slight left": {
                "default": "Links aanhouden",
                "name": "Links aanhouden naar {way_name}",
                "destination": "Links aanhouden richting {destination}"
            },
            "slight right": {
                "default": "Rechts aanhouden",
                "name": "Rechts aanhouden naar {way_name}",
                "destination": "Rechts aanhouden richting {destination}"
            },
            "uturn": {
                "default": "Keer om",
                "name": "Keer om naar {way_name}",
                "destination": "Keer om richting {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Vertrek in {direction}elijke richting",
                "name": "Neem {way_name} in {direction}elijke richting",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Ga {modifier}",
                "name": "Ga {modifier} naar {way_name}",
                "destination": "Ga {modifier} richting {destination}"
            },
            "straight": {
                "default": "Ga in de aangegeven richting",
                "name": "Ga naar {way_name}",
                "destination": "Ga richting {destination}"
            },
            "uturn": {
                "default": "Keer om",
                "name": "Keer om naar {way_name}",
                "destination": "Keer om richting {destination}"
            }
        },
        "fork": {
            "default": {
                "default": "Ga {modifier} op de splitsing",
                "name": "Ga {modifier} op de splitsing naar {way_name}",
                "destination": "Ga {modifier} op de splitsing richting {destination}"
            },
            "slight left": {
                "default": "Links aanhouden op de splitsing",
                "name": "Links aanhouden op de splitsing naar {way_name}",
                "destination": "Links aanhouden op de splitsing richting {destination}"
            },
            "slight right": {
                "default": "Rechts aanhouden op de splitsing",
                "name": "Rechts aanhouden op de splitsing naar {way_name}",
                "destination": "Rechts aanhouden op de splitsing richting {destination}"
            },
            "sharp left": {
                "default": "Linksaf op de splitsing",
                "name": "Linksaf op de splitsing naar {way_name}",
                "destination": "Linksaf op de splitsing richting {destination}"
            },
            "sharp right": {
                "default": "Rechtsaf op de splitsing",
                "name": "Rechtsaf op de splitsing naar {way_name}",
                "destination": "Rechtsaf op de splitsing richting {destination}"
            },
            "uturn": {
                "default": "Keer om",
                "name": "Keer om naar {way_name}",
                "destination": "Keer om richting {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Bij de splitsing {modifier}",
                "name": "Bij de splitsing {modifier} naar {way_name}",
                "destination": "Bij de splitsing {modifier} richting {destination}"
            },
            "slight left": {
                "default": "Bij de splitsing links aanhouden",
                "name": "Bij de splitsing links aanhouden naar {way_name}",
                "destination": "Bij de splitsing links aanhouden richting {destination}"
            },
            "slight right": {
                "default": "Bij de splitsing rechts aanhouden",
                "name": "Bij de splitsing rechts aanhouden naar {way_name}",
                "destination": "Bij de splitsing rechts aanhouden richting {destination}"
            },
            "sharp left": {
                "default": "Bij de splitsing linksaf",
                "name": "Bij de splitsing linksaf naar {way_name}",
                "destination": "Bij de splitsing linksaf richting {destination}"
            },
            "sharp right": {
                "default": "Bij de splitsing rechtsaf",
                "name": "Bij de splitsing rechtsaf naar {way_name}",
                "destination": "Bij de splitsing rechtsaf richting {destination}"
            },
            "uturn": {
                "default": "Keer om",
                "name": "Keer om naar {way_name}",
                "destination": "Keer om richting {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Ga {modifier}",
                "name": "Ga {modifier} naar {way_name}",
                "destination": "Ga {modifier} richting {destination}"
            },
            "straight": {
                "default": "Ga in de aangegeven richting",
                "name": "Ga rechtdoor naar {way_name}",
                "destination": "Ga rechtdoor richting {destination}"
            },
            "sharp left": {
                "default": "Linksaf",
                "name": "Linksaf naar {way_name}",
                "destination": "Linksaf richting {destination}"
            },
            "sharp right": {
                "default": "Rechtsaf",
                "name": "Rechtsaf naar {way_name}",
                "destination": "Rechtsaf richting {destination}"
            },
            "slight left": {
                "default": "Links aanhouden",
                "name": "Links aanhouden naar {way_name}",
                "destination": "Links aanhouden richting {destination}"
            },
            "slight right": {
                "default": "Rechts aanhouden",
                "name": "Rechts aanhouden naar {way_name}",
                "destination": "Rechts aanhouden richting {destination}"
            },
            "uturn": {
                "default": "Keer om",
                "name": "Keer om naar {way_name}",
                "destination": "Keer om richting {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Ga {modifier}",
                "name": "Ga {modifier} naar {way_name}",
                "destination": "Ga {modifier} richting {destination}"
            },
            "uturn": {
                "default": "Keer om",
                "name": "Keer om naar {way_name}",
                "destination": "Keer om richting {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Neem de afrit",
                "name": "Neem de afrit naar {way_name}",
                "destination": "Neem de afrit richting {destination}",
                "exit": "Take exit {exit}",
                "exit_destination": "Take exit {exit} towards {destination}"
            },
            "left": {
                "default": "Neem de afrit links",
                "name": "Neem de afrit links naar {way_name}",
                "destination": "Neem de afrit links richting {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "right": {
                "default": "Neem de afrit rechts",
                "name": "Neem de afrit rechts naar {way_name}",
                "destination": "Neem de afrit rechts richting {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "sharp left": {
                "default": "Neem de afrit links",
                "name": "Neem de afrit links naar {way_name}",
                "destination": "Neem de afrit links richting {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "sharp right": {
                "default": "Neem de afrit rechts",
                "name": "Neem de afrit rechts naar {way_name}",
                "destination": "Neem de afrit rechts richting {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            },
            "slight left": {
                "default": "Neem de afrit links",
                "name": "Neem de afrit links naar {way_name}",
                "destination": "Neem de afrit links richting {destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "slight right": {
                "default": "Neem de afrit rechts",
                "name": "Neem de afrit rechts naar {way_name}",
                "destination": "Neem de afrit rechts richting {destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Neem de oprit",
                "name": "Neem de oprit naar {way_name}",
                "destination": "Neem de oprit richting {destination}"
            },
            "left": {
                "default": "Neem de oprit links",
                "name": "Neem de oprit links naar {way_name}",
                "destination": "Neem de oprit links richting {destination}"
            },
            "right": {
                "default": "Neem de oprit rechts",
                "name": "Neem de oprit rechts naar {way_name}",
                "destination": "Neem de oprit rechts richting {destination}"
            },
            "sharp left": {
                "default": "Neem de oprit links",
                "name": "Neem de oprit links naar {way_name}",
                "destination": "Neem de oprit links richting {destination}"
            },
            "sharp right": {
                "default": "Neem de oprit rechts",
                "name": "Neem de oprit rechts naar {way_name}",
                "destination": "Neem de oprit rechts richting {destination}"
            },
            "slight left": {
                "default": "Neem de oprit links",
                "name": "Neem de oprit links naar {way_name}",
                "destination": "Neem de oprit links richting {destination}"
            },
            "slight right": {
                "default": "Neem de oprit rechts",
                "name": "Neem de oprit rechts naar {way_name}",
                "destination": "Neem de oprit rechts richting {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Ga het knooppunt op",
                    "name": "Verlaat het knooppunt naar {way_name}",
                    "destination": "Verlaat het knooppunt richting {destination}"
                },
                "name": {
                    "default": "Ga het knooppunt {rotary_name} op",
                    "name": "Verlaat het knooppunt {rotary_name} naar {way_name}",
                    "destination": "Verlaat het knooppunt {rotary_name} richting {destination}"
                },
                "exit": {
                    "default": "Ga het knooppunt op en neem afslag {exit_number}",
                    "name": "Ga het knooppunt op en neem afslag {exit_number} naar {way_name}",
                    "destination": "Ga het knooppunt op en neem afslag {exit_number} richting {destination}"
                },
                "name_exit": {
                    "default": "Ga het knooppunt {rotary_name} op en neem afslag {exit_number}",
                    "name": "Ga het knooppunt {rotary_name} op en neem afslag {exit_number} naar {way_name}",
                    "destination": "Ga het knooppunt {rotary_name} op en neem afslag {exit_number} richting {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Ga de rotonde op en neem afslag {exit_number}",
                    "name": "Ga de rotonde op en neem afslag {exit_number} naar {way_name}",
                    "destination": "Ga de rotonde op en neem afslag {exit_number} richting {destination}"
                },
                "default": {
                    "default": "Ga de rotonde op",
                    "name": "Verlaat de rotonde naar {way_name}",
                    "destination": "Verlaat de rotonde richting {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Ga {modifier} op de rotonde",
                "name": "Ga {modifier} op de rotonde naar {way_name}",
                "destination": "Ga {modifier} op de rotonde richting {destination}"
            },
            "left": {
                "default": "Ga links op de rotonde",
                "name": "Ga links op de rotonde naar {way_name}",
                "destination": "Ga links op de rotonde richting {destination}"
            },
            "right": {
                "default": "Ga rechts op de rotonde",
                "name": "Ga rechts op de rotonde naar {way_name}",
                "destination": "Ga rechts op de rotonde richting {destination}"
            },
            "straight": {
                "default": "Rechtdoor op de rotonde",
                "name": "Rechtdoor op de rotonde naar {way_name}",
                "destination": "Rechtdoor op de rotonde richting {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Ga {modifier}",
                "name": "Ga {modifier} naar {way_name}",
                "destination": "Ga {modifier} richting {destination}"
            },
            "left": {
                "default": "Ga linksaf",
                "name": "Ga linksaf naar {way_name}",
                "destination": "Ga linksaf richting {destination}"
            },
            "right": {
                "default": "Ga rechtsaf",
                "name": "Ga rechtsaf naar {way_name}",
                "destination": "Ga rechtsaf richting {destination}"
            },
            "straight": {
                "default": "Ga rechtdoor",
                "name": "Ga rechtdoor naar {way_name}",
                "destination": "Ga rechtdoor richting {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Ga {modifier}",
                "name": "Ga {modifier} naar {way_name}",
                "destination": "Ga {modifier} richting {destination}"
            },
            "left": {
                "default": "Ga linksaf",
                "name": "Ga linksaf naar {way_name}",
                "destination": "Ga linksaf richting {destination}"
            },
            "right": {
                "default": "Ga rechtsaf",
                "name": "Ga rechtsaf naar {way_name}",
                "destination": "Ga rechtsaf richting {destination}"
            },
            "straight": {
                "default": "Ga rechtdoor",
                "name": "Ga rechtdoor naar {way_name}",
                "destination": "Ga rechtdoor richting {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Ga {modifier}",
                "name": "Ga {modifier} naar {way_name}",
                "destination": "Ga {modifier} richting {destination}"
            },
            "left": {
                "default": "Ga linksaf",
                "name": "Ga linksaf naar {way_name}",
                "destination": "Ga linksaf richting {destination}"
            },
            "right": {
                "default": "Ga rechtsaf",
                "name": "Ga rechtsaf naar {way_name}",
                "destination": "Ga rechtsaf richting {destination}"
            },
            "straight": {
                "default": "Ga rechtdoor",
                "name": "Ga rechtdoor naar {way_name}",
                "destination": "Ga rechtdoor richting {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Rechtdoor"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],15:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1.",
                "2": "2.",
                "3": "3.",
                "4": "4.",
                "5": "5.",
                "6": "6.",
                "7": "7.",
                "8": "8.",
                "9": "9.",
                "10": "10."
            },
            "direction": {
                "north": "północ",
                "northeast": "północny wschód",
                "east": "wschód",
                "southeast": "południowy wschód",
                "south": "południe",
                "southwest": "południowy zachód",
                "west": "zachód",
                "northwest": "północny zachód"
            },
            "modifier": {
                "left": "lewo",
                "right": "prawo",
                "sharp left": "ostro w lewo",
                "sharp right": "ostro w prawo",
                "slight left": "łagodnie w lewo",
                "slight right": "łagodnie w prawo",
                "straight": "prosto",
                "uturn": "zawróć"
            },
            "lanes": {
                "xo": "Trzymaj się prawej strony",
                "ox": "Trzymaj się lewej strony",
                "xox": "Trzymaj się środka",
                "oxo": "Trzymaj się lewej lub prawej strony"
            }
        },
        "modes": {
            "ferry": {
                "default": "Weź prom",
                "name": "Weź prom {way_name}",
                "destination": "Weź prom w kierunku {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one}, następnie za {distance} {instruction_two}",
            "two linked": "{instruction_one}, następnie {instruction_two}",
            "one in distance": "Za {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Dojechano do miejsca docelowego {nth}"
            },
            "left": {
                "default": "Dojechano do miejsca docelowego {nth}, po lewej stronie"
            },
            "right": {
                "default": "Dojechano do miejsca docelowego {nth}, po prawej stronie"
            },
            "sharp left": {
                "default": "Dojechano do miejsca docelowego {nth}, po lewej stronie"
            },
            "sharp right": {
                "default": "Dojechano do miejsca docelowego {nth}, po prawej stronie"
            },
            "slight right": {
                "default": "Dojechano do miejsca docelowego {nth}, po prawej stronie"
            },
            "slight left": {
                "default": "Dojechano do miejsca docelowego {nth}, po lewej stronie"
            },
            "straight": {
                "default": "Dojechano do miejsca docelowego {nth} , prosto"
            }
        },
        "continue": {
            "default": {
                "default": "Skręć {modifier}",
                "name": "Skręć w {modifier}, aby pozostać na {way_name}",
                "destination": "Skręć {modifier} w kierunku {destination}",
                "exit": "Skręć {modifier} na {way_name}"
            },
            "straight": {
                "default": "Kontynuuj prosto",
                "name": "Jedź dalej prosto, aby pozostać na {way_name}",
                "destination": "Kontynuuj w kierunku {destination}",
                "distance": "Jedź dalej prosto przez {distance}",
                "namedistance": "Jedź dalej {way_name} przez {distance}"
            },
            "sharp left": {
                "default": "Skręć ostro w lewo",
                "name": "Skręć w lewo w ostry zakręt, aby pozostać na {way_name}",
                "destination": "Skręć ostro w lewo w kierunku {destination}"
            },
            "sharp right": {
                "default": "Skręć ostro w prawo",
                "name": "Skręć w prawo w ostry zakręt, aby pozostać na {way_name}",
                "destination": "Skręć ostro w prawo w kierunku {destination}"
            },
            "slight left": {
                "default": "Skręć w lewo w łagodny zakręt",
                "name": "Skręć w lewo w łagodny zakręt, aby pozostać na {way_name}",
                "destination": "Skręć w lewo w łagodny zakręt na {destination}"
            },
            "slight right": {
                "default": "Skręć w prawo w łagodny zakręt",
                "name": "Skręć w prawo w łagodny zakręt, aby pozostać na {way_name}",
                "destination": "Skręć w prawo w łagodny zakręt na {destination}"
            },
            "uturn": {
                "default": "Zawróć",
                "name": "Zawróć i jedź dalej {way_name}",
                "destination": "Zawróć w kierunku {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Kieruj się {direction}",
                "name": "Kieruj się {direction} na {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Skręć {modifier}",
                "name": "Skręć {modifier} na {way_name}",
                "destination": "Skręć {modifier} w kierunku {destination}"
            },
            "straight": {
                "default": "Kontynuuj prosto",
                "name": "Kontynuuj prosto na {way_name}",
                "destination": "Kontynuuj prosto w kierunku {destination}"
            },
            "uturn": {
                "default": "Zawróć na końcu ulicy",
                "name": "Zawróć na końcu ulicy na {way_name}",
                "destination": "Zawróć na końcu ulicy w kierunku {destination}"
            }
        },
        "fork": {
            "default": {
                "default": "Na rozwidleniu trzymaj się {modifier}",
                "name": "Na rozwidleniu trzymaj się {modifier} na {way_name}",
                "destination": "Na rozwidleniu trzymaj się {modifier} w kierunku {destination}"
            },
            "slight left": {
                "default": "Na rozwidleniu trzymaj się lewej strony",
                "name": "Na rozwidleniu trzymaj się lewej strony w {way_name}",
                "destination": "Na rozwidleniu trzymaj się lewej strony w kierunku {destination}"
            },
            "slight right": {
                "default": "Na rozwidleniu trzymaj się prawej strony",
                "name": "Na rozwidleniu trzymaj się prawej strony na {way_name}",
                "destination": "Na rozwidleniu trzymaj się prawej strony w kierunku {destination}"
            },
            "sharp left": {
                "default": "Na rozwidleniu skręć ostro w lewo",
                "name": "Na rozwidleniu skręć ostro w lew na {way_name}",
                "destination": "Na rozwidleniu skręć ostro w lewo w kierunku {destination}"
            },
            "sharp right": {
                "default": "Na rozwidleniu skręć ostro w prawo",
                "name": "Na rozwidleniu skręć ostro w prawo na {way_name}",
                "destination": "Na rozwidleniu skręć ostro w prawo w kierunku {destination}"
            },
            "uturn": {
                "default": "Zawróć",
                "name": "Zawróć na {way_name}",
                "destination": "Zawróć w kierunku {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Włącz się {modifier}",
                "name": "Włącz się {modifier} na {way_name}",
                "destination": "Włącz się {modifier} w kierunku {destination}"
            },
            "slight left": {
                "default": "Włącz się z lewej strony",
                "name": "Włącz się z lewej strony na {way_name}",
                "destination": "Włącz się z lewej strony w kierunku {destination}"
            },
            "slight right": {
                "default": "Włącz się z prawej strony",
                "name": "Włącz się z prawej strony na {way_name}",
                "destination": "Włącz się z prawej strony w kierunku {destination}"
            },
            "sharp left": {
                "default": "Włącz się z lewej strony",
                "name": "Włącz się z lewej strony na {way_name}",
                "destination": "Włącz się z lewej strony w kierunku {destination}"
            },
            "sharp right": {
                "default": "Włącz się z prawej strony",
                "name": "Włącz się z prawej strony na {way_name}",
                "destination": "Włącz się z prawej strony w kierunku {destination}"
            },
            "uturn": {
                "default": "Zawróć",
                "name": "Zawróć na {way_name}",
                "destination": "Zawróć w kierunku {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Kontynuuj {modifier}",
                "name": "Kontynuuj {modifier} na {way_name}",
                "destination": "Kontynuuj {modifier} w kierunku {destination}"
            },
            "straight": {
                "default": "Kontynuuj prosto",
                "name": "Kontynuuj na {way_name}",
                "destination": "Kontynuuj w kierunku {destination}"
            },
            "sharp left": {
                "default": "Skręć ostro w lewo",
                "name": "Skręć ostro w lewo w {way_name}",
                "destination": "Skręć ostro w lewo w kierunku {destination}"
            },
            "sharp right": {
                "default": "Skręć ostro w prawo",
                "name": "Skręć ostro w prawo na {way_name}",
                "destination": "Skręć ostro w prawo w kierunku {destination}"
            },
            "slight left": {
                "default": "Kontynuuj łagodnie w lewo",
                "name": "Kontynuuj łagodnie w lewo na {way_name}",
                "destination": "Kontynuuj łagodnie w lewo w kierunku {destination}"
            },
            "slight right": {
                "default": "Kontynuuj łagodnie w prawo",
                "name": "Kontynuuj łagodnie w prawo na {way_name}",
                "destination": "Kontynuuj łagodnie w prawo w kierunku {destination}"
            },
            "uturn": {
                "default": "Zawróć",
                "name": "Zawróć na {way_name}",
                "destination": "Zawróć w kierunku {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Kontynuuj {modifier}",
                "name": "Kontynuuj {modifier} na {way_name}",
                "destination": "Kontynuuj {modifier} w kierunku {destination}"
            },
            "uturn": {
                "default": "Zawróć",
                "name": "Zawróć na {way_name}",
                "destination": "Zawróć w kierunku {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Zjedź",
                "name": "Weź zjazd na {way_name}",
                "destination": "Weź zjazd w kierunku {destination}",
                "exit": "Zjedź zjazdem {exit}",
                "exit_destination": "Zjedź zjazdem {exit} na {destination}"
            },
            "left": {
                "default": "Weź zjazd po lewej",
                "name": "Weź zjazd po lewej na {way_name}",
                "destination": "Weź zjazd po lewej w kierunku {destination}",
                "exit": "Zjedź zjazdem {exit} po lewej stronie",
                "exit_destination": "Zjedź zjazdem {exit} po lewej stronie na {destination}"
            },
            "right": {
                "default": "Weź zjazd po prawej",
                "name": "Weź zjazd po prawej na {way_name}",
                "destination": "Weź zjazd po prawej w kierunku {destination}",
                "exit": "Zjedź zjazdem {exit} po prawej stronie",
                "exit_destination": "Zjedź zjazdem {exit} po prawej stronie na {destination}"
            },
            "sharp left": {
                "default": "Weź zjazd po lewej",
                "name": "Weź zjazd po lewej na {way_name}",
                "destination": "Weź zjazd po lewej w kierunku {destination}",
                "exit": "Zjedź zjazdem {exit} po lewej stronie",
                "exit_destination": "Zjedź zjazdem {exit} po lewej stronie na {destination}"
            },
            "sharp right": {
                "default": "Weź zjazd po prawej",
                "name": "Weź zjazd po prawej na {way_name}",
                "destination": "Weź zjazd po prawej w kierunku {destination}",
                "exit": "Zjedź zjazdem {exit} po prawej stronie",
                "exit_destination": "Zjedź zjazdem {exit} po prawej stronie na {destination}"
            },
            "slight left": {
                "default": "Weź zjazd po lewej",
                "name": "Weź zjazd po lewej na {way_name}",
                "destination": "Weź zjazd po lewej w kierunku {destination}",
                "exit": "Zjedź zjazdem {exit} po lewej stronie",
                "exit_destination": "Zjedź zjazdem {exit} po lewej stronie na {destination}"
            },
            "slight right": {
                "default": "Weź zjazd po prawej",
                "name": "Weź zjazd po prawej na {way_name}",
                "destination": "Weź zjazd po prawej w kierunku {destination}",
                "exit": "Zjedź zjazdem {exit} po prawej stronie",
                "exit_destination": "Zjedź zjazdem {exit} po prawej stronie na {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Weź zjazd",
                "name": "Weź zjazd na {way_name}",
                "destination": "Weź zjazd w kierunku {destination}"
            },
            "left": {
                "default": "Weź zjazd po lewej",
                "name": "Weź zjazd po lewej na {way_name}",
                "destination": "Weź zjazd po lewej w kierunku {destination}"
            },
            "right": {
                "default": "Weź zjazd po prawej",
                "name": "Weź zjazd po prawej na {way_name}",
                "destination": "Weź zjazd po prawej w kierunku {destination}"
            },
            "sharp left": {
                "default": "Weź zjazd po lewej",
                "name": "Weź zjazd po lewej na {way_name}",
                "destination": "Weź zjazd po lewej w kierunku {destination}"
            },
            "sharp right": {
                "default": "Weź zjazd po prawej",
                "name": "Weź zjazd po prawej na {way_name}",
                "destination": "Weź zjazd po prawej w kierunku {destination}"
            },
            "slight left": {
                "default": "Weź zjazd po lewej",
                "name": "Weź zjazd po lewej na {way_name}",
                "destination": "Weź zjazd po lewej w kierunku {destination}"
            },
            "slight right": {
                "default": "Weź zjazd po prawej",
                "name": "Weź zjazd po prawej na {way_name}",
                "destination": "Weź zjazd po prawej w kierunku {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Wjedź na rondo",
                    "name": "Wjedź na rondo i skręć na {way_name}",
                    "destination": "Wjedź na rondo i skręć w kierunku {destination}"
                },
                "name": {
                    "default": "Wjedź na {rotary_name}",
                    "name": "Wjedź na {rotary_name} i skręć na {way_name}",
                    "destination": "Wjedź na {rotary_name} i skręć w kierunku {destination}"
                },
                "exit": {
                    "default": "Wjedź na rondo i wyjedź {exit_number} zjazdem",
                    "name": "Wjedź na rondo i wyjedź {exit_number} zjazdem na {way_name}",
                    "destination": "Wjedź na rondo i wyjedź {exit_number} zjazdem w kierunku {destination}"
                },
                "name_exit": {
                    "default": "Wjedź na {rotary_name} i wyjedź {exit_number} zjazdem",
                    "name": "Wjedź na {rotary_name} i wyjedź {exit_number} zjazdem na {way_name}",
                    "destination": "Wjedź na {rotary_name} i wyjedź {exit_number} zjazdem w kierunku {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Wjedź na rondo i wyjedź {exit_number} zjazdem",
                    "name": "Wjedź na rondo i wyjedź {exit_number} zjazdem na {way_name}",
                    "destination": "Wjedź na rondo i wyjedź {exit_number} zjazdem w kierunku {destination}"
                },
                "default": {
                    "default": "Wjedź na rondo",
                    "name": "Wjedź na rondo i wyjedź na {way_name}",
                    "destination": "Wjedź na rondo i wyjedź w kierunku {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Na rondzie weź {modifier}",
                "name": "Na rondzie weź {modifier} na {way_name}",
                "destination": "Na rondzie weź {modifier} w kierunku {destination}"
            },
            "left": {
                "default": "Na rondzie skręć w lewo",
                "name": "Na rondzie skręć lewo na {way_name}",
                "destination": "Na rondzie skręć w lewo w kierunku {destination}"
            },
            "right": {
                "default": "Na rondzie skręć w prawo",
                "name": "Na rondzie skręć w prawo na {way_name}",
                "destination": "Na rondzie skręć w prawo w kierunku {destination}"
            },
            "straight": {
                "default": "Na rondzie kontynuuj prosto",
                "name": "Na rondzie kontynuuj prosto na {way_name}",
                "destination": "Na rondzie kontynuuj prosto w kierunku {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "{modifier}",
                "name": "{modifier} na {way_name}",
                "destination": "{modifier} w kierunku {destination}"
            },
            "left": {
                "default": "Skręć w lewo",
                "name": "Skręć w lewo na {way_name}",
                "destination": "Skręć w lewo w kierunku {destination}"
            },
            "right": {
                "default": "Skręć w prawo",
                "name": "Skręć w prawo na {way_name}",
                "destination": "Skręć w prawo w kierunku {destination}"
            },
            "straight": {
                "default": "Jedź prosto",
                "name": "Jedź prosto na {way_name}",
                "destination": "Jedź prosto w kierunku {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "{modifier}",
                "name": "{modifier} na {way_name}",
                "destination": "{modifier} w kierunku {destination}"
            },
            "left": {
                "default": "Skręć w lewo",
                "name": "Skręć w lewo na {way_name}",
                "destination": "Skręć w lewo w kierunku {destination}"
            },
            "right": {
                "default": "Skręć w prawo",
                "name": "Skręć w prawo na {way_name}",
                "destination": "Skręć w prawo w kierunku {destination}"
            },
            "straight": {
                "default": "Jedź prosto",
                "name": "Jedź prosto na {way_name}",
                "destination": "Jedź prosto w kierunku {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "{modifier}",
                "name": "{modifier} na {way_name}",
                "destination": "{modifier} w kierunku {destination}"
            },
            "left": {
                "default": "Skręć w lewo",
                "name": "Skręć w lewo na {way_name}",
                "destination": "Skręć w lewo w kierunku {destination}"
            },
            "right": {
                "default": "Skręć w prawo",
                "name": "Skręć w prawo na {way_name}",
                "destination": "Skręć w prawo w kierunku {destination}"
            },
            "straight": {
                "default": "Jedź prosto",
                "name": "Jedź prosto na {way_name}",
                "destination": "Jedź prosto w kierunku {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Kontynuuj prosto"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],16:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1º",
                "2": "2º",
                "3": "3º",
                "4": "4º",
                "5": "5º",
                "6": "6º",
                "7": "7º",
                "8": "8º",
                "9": "9º",
                "10": "10º"
            },
            "direction": {
                "north": "norte",
                "northeast": "nordeste",
                "east": "leste",
                "southeast": "sudeste",
                "south": "sul",
                "southwest": "sudoeste",
                "west": "oeste",
                "northwest": "noroeste"
            },
            "modifier": {
                "left": "à esquerda",
                "right": "à direita",
                "sharp left": "acentuadamente à esquerda",
                "sharp right": "acentuadamente à direita",
                "slight left": "ligeiramente à esquerda",
                "slight right": "ligeiramente à direita",
                "straight": "reto",
                "uturn": "retorno"
            },
            "lanes": {
                "xo": "Mantenha-se à direita",
                "ox": "Mantenha-se à esquerda",
                "xox": "Mantenha-se ao centro",
                "oxo": "Mantenha-se à esquerda ou direita"
            }
        },
        "modes": {
            "ferry": {
                "default": "Pegue a balsa",
                "name": "Pegue a balsa {way_name}",
                "destination": "Pegue a balsa sentido {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} then in {distance} {instruction_two}",
            "two linked": "{instruction_one} then {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Você chegou ao seu {nth} destino"
            },
            "left": {
                "default": "Você chegou ao seu {nth} destino, à esquerda"
            },
            "right": {
                "default": "Você chegou ao seu {nth} destino, à direita"
            },
            "sharp left": {
                "default": "Você chegou ao seu {nth} destino, à esquerda"
            },
            "sharp right": {
                "default": "Você chegou ao seu {nth} destino, à direita"
            },
            "slight right": {
                "default": "Você chegou ao seu {nth} destino, à direita"
            },
            "slight left": {
                "default": "Você chegou ao seu {nth} destino, à esquerda"
            },
            "straight": {
                "default": "Você chegou ao seu {nth} destino, em frente"
            }
        },
        "continue": {
            "default": {
                "default": "Vire {modifier}",
                "name": "Continue {modifier} em {way_name}",
                "destination": "Vire {modifier} sentido {destination}",
                "exit": "Vire {modifier} em {way_name}"
            },
            "straight": {
                "default": "Continue reto",
                "name": "Continue em {way_name}",
                "destination": "Continue até {destination}",
                "distance": "Continue straight for {distance}",
                "namedistance": "Continue on {way_name} for {distance}"
            },
            "sharp left": {
                "default": "Vire acentuadamente à esquerda",
                "name": "Make a sharp left to stay on {way_name}",
                "destination": "Vire acentuadamente à esquerda sentido {destination}"
            },
            "sharp right": {
                "default": "Vire acentuadamente à direita",
                "name": "Make a sharp right to stay on {way_name}",
                "destination": "Vire acentuadamente à direita sentido {destination}"
            },
            "slight left": {
                "default": "Continue ligeiramente à esquerda",
                "name": "Continue ligeiramente à esquerda em {way_name}",
                "destination": "Continue ligeiramente à esquerda sentido {destination}"
            },
            "slight right": {
                "default": "Continue ligeiramente à direita",
                "name": "Continue ligeiramente à direita em {way_name}",
                "destination": "Continue ligeiramente à direita sentido {destination}"
            },
            "uturn": {
                "default": "Faça o retorno",
                "name": "Faça o retorno em {way_name}",
                "destination": "Faça o retorno sentido {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Siga {direction}",
                "name": "Siga {direction} em {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Vire {modifier}",
                "name": "Vire {modifier} em {way_name}",
                "destination": "Vire {modifier} sentido {destination}"
            },
            "straight": {
                "default": "Continue reto",
                "name": "Continue reto em {way_name}",
                "destination": "Continue reto sentido {destination}"
            },
            "uturn": {
                "default": "Faça o retorno no fim da rua",
                "name": "Faça o retorno em {way_name} no fim da rua",
                "destination": "Faça o retorno sentido {destination} no fim da rua"
            }
        },
        "fork": {
            "default": {
                "default": "Mantenha-se {modifier} na bifurcação",
                "name": "Mantenha-se {modifier} na bifurcação em {way_name}",
                "destination": "Mantenha-se {modifier} na bifurcação sentido {destination}"
            },
            "slight left": {
                "default": "Mantenha-se à esquerda na bifurcação",
                "name": "Mantenha-se à esquerda na bifurcação em {way_name}",
                "destination": "Mantenha-se à esquerda na bifurcação sentido {destination}"
            },
            "slight right": {
                "default": "Mantenha-se à direita na bifurcação",
                "name": "Mantenha-se à direita na bifurcação em {way_name}",
                "destination": "Mantenha-se à direita na bifurcação sentido {destination}"
            },
            "sharp left": {
                "default": "Vire acentuadamente à esquerda na bifurcação",
                "name": "Vire acentuadamente à esquerda na bifurcação em {way_name}",
                "destination": "Vire acentuadamente à esquerda na bifurcação sentido {destination}"
            },
            "sharp right": {
                "default": "Vire acentuadamente à direita na bifurcação",
                "name": "Vire acentuadamente à direita na bifurcação em {way_name}",
                "destination": "Vire acentuadamente à direita na bifurcação sentido {destination}"
            },
            "uturn": {
                "default": "Faça o retorno",
                "name": "Faça o retorno em {way_name}",
                "destination": "Faça o retorno sentido {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Entre {modifier}",
                "name": "Entre {modifier} na {way_name}",
                "destination": "Entre {modifier} em direção à {destination}"
            },
            "slight left": {
                "default": "Entre à esquerda",
                "name": "Entre à esquerda na {way_name}",
                "destination": "Entre à esquerda em direção à {destination}"
            },
            "slight right": {
                "default": "Entre à direita",
                "name": "Entre à direita na {way_name}",
                "destination": "Entre à direita em direção à {destination}"
            },
            "sharp left": {
                "default": "Entre à esquerda",
                "name": "Entre à esquerda na {way_name}",
                "destination": "Entre à esquerda em direção à {destination}"
            },
            "sharp right": {
                "default": "Entre à direita",
                "name": "Entre à direita na {way_name}",
                "destination": "Entre à direita em direção à {destination}"
            },
            "uturn": {
                "default": "Faça o retorno",
                "name": "Faça o retorno em {way_name}",
                "destination": "Faça o retorno sentido {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Continue {modifier}",
                "name": "Continue {modifier} em {way_name}",
                "destination": "Continue {modifier} sentido {destination}"
            },
            "straight": {
                "default": "Continue em frente",
                "name": "Continue em {way_name}",
                "destination": "Continue em direção à {destination}"
            },
            "sharp left": {
                "default": "Vire acentuadamente à esquerda",
                "name": "Vire acentuadamente à esquerda em {way_name}",
                "destination": "Vire acentuadamente à esquerda sentido {destination}"
            },
            "sharp right": {
                "default": "Vire acentuadamente à direita",
                "name": "Vire acentuadamente à direita em {way_name}",
                "destination": "Vire acentuadamente à direita sentido {destination}"
            },
            "slight left": {
                "default": "Continue ligeiramente à esquerda",
                "name": "Continue ligeiramente à esquerda em {way_name}",
                "destination": "Continue ligeiramente à esquerda sentido {destination}"
            },
            "slight right": {
                "default": "Continue ligeiramente à direita",
                "name": "Continue ligeiramente à direita em {way_name}",
                "destination": "Continue ligeiramente à direita sentido {destination}"
            },
            "uturn": {
                "default": "Faça o retorno",
                "name": "Faça o retorno em {way_name}",
                "destination": "Faça o retorno sentido {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Continue {modifier}",
                "name": "Continue {modifier} em {way_name}",
                "destination": "Continue {modifier} sentido {destination}"
            },
            "uturn": {
                "default": "Faça o retorno",
                "name": "Faça o retorno em {way_name}",
                "destination": "Faça o retorno sentido {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Pegue a rampa",
                "name": "Pegue a rampa em {way_name}",
                "destination": "Pegue a rampa sentido {destination}",
                "exit": "Pegue a saída {exit}",
                "exit_destination": "Pegue a saída {exit} em direção à {destination}"
            },
            "left": {
                "default": "Pegue a rampa à esquerda",
                "name": "Pegue a rampa à esquerda em {way_name}",
                "destination": "Pegue a rampa à esquerda sentido {destination}",
                "exit": "Pegue a saída {exit} à esquerda",
                "exit_destination": "Pegue a saída {exit}  à esquerda em direção à {destination}"
            },
            "right": {
                "default": "Pegue a rampa à direita",
                "name": "Pegue a rampa à direita em {way_name}",
                "destination": "Pegue a rampa à direita sentido {destination}",
                "exit": "Pegue a saída {exit} à direita",
                "exit_destination": "Pegue a saída {exit} à direita em direção à {destination}"
            },
            "sharp left": {
                "default": "Pegue a rampa à esquerda",
                "name": "Pegue a rampa à esquerda em {way_name}",
                "destination": "Pegue a rampa à esquerda sentido {destination}",
                "exit": "Pegue a saída {exit} à esquerda",
                "exit_destination": "Pegue a saída {exit}  à esquerda em direção à {destination}"
            },
            "sharp right": {
                "default": "Pegue a rampa à direita",
                "name": "Pegue a rampa à direita em {way_name}",
                "destination": "Pegue a rampa à direita sentido {destination}",
                "exit": "Pegue a saída {exit} à direita",
                "exit_destination": "Pegue a saída {exit} à direita em direção à {destination}"
            },
            "slight left": {
                "default": "Pegue a rampa à esquerda",
                "name": "Pegue a rampa à esquerda em {way_name}",
                "destination": "Pegue a rampa à esquerda sentido {destination}",
                "exit": "Pegue a saída {exit} à esquerda",
                "exit_destination": "Pegue a saída {exit}  à esquerda em direção à {destination}"
            },
            "slight right": {
                "default": "Pegue a rampa à direita",
                "name": "Pegue a rampa à direita em {way_name}",
                "destination": "Pegue a rampa à direita sentido {destination}",
                "exit": "Pegue a saída {exit} à direita",
                "exit_destination": "Pegue a saída {exit} à direita em direção à {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Pegue a rampa",
                "name": "Pegue a rampa em {way_name}",
                "destination": "Pegue a rampa sentido {destination}"
            },
            "left": {
                "default": "Pegue a rampa à esquerda",
                "name": "Pegue a rampa à esquerda em {way_name}",
                "destination": "Pegue a rampa à esquerda sentido {destination}"
            },
            "right": {
                "default": "Pegue a rampa à direita",
                "name": "Pegue a rampa à direita em {way_name}",
                "destination": "Pegue a rampa à direita sentid {destination}"
            },
            "sharp left": {
                "default": "Pegue a rampa à esquerda",
                "name": "Pegue a rampa à esquerda em {way_name}",
                "destination": "Pegue a rampa à esquerda sentido {destination}"
            },
            "sharp right": {
                "default": "Pegue a rampa à direita",
                "name": "Pegue a rampa à direita em {way_name}",
                "destination": "Pegue a rampa à direita sentido {destination}"
            },
            "slight left": {
                "default": "Pegue a rampa à esquerda",
                "name": "Pegue a rampa à esquerda em {way_name}",
                "destination": "Pegue a rampa à esquerda sentido {destination}"
            },
            "slight right": {
                "default": "Pegue a rampa à direita",
                "name": "Pegue a rampa à direita em {way_name}",
                "destination": "Pegue a rampa à direita sentido {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Entre na rotatória",
                    "name": "Entre na rotatória e saia em {way_name}",
                    "destination": "Entre na rotatória e saia sentido {destination}"
                },
                "name": {
                    "default": "Entre em {rotary_name}",
                    "name": "Entre em {rotary_name} e saia em {way_name}",
                    "destination": "Entre em {rotary_name} e saia sentido {destination}"
                },
                "exit": {
                    "default": "Entre na rotatória e saia na {exit_number} saída",
                    "name": "Entre na rotatória e saia na {exit_number} saída em {way_name}",
                    "destination": "Entre na rotatória e saia na {exit_number} saída sentido {destination}"
                },
                "name_exit": {
                    "default": "Entre em {rotary_name} e saia na {exit_number} saída",
                    "name": "Entre em {rotary_name} e saia na {exit_number} saída em {way_name}",
                    "destination": "Entre em {rotary_name} e saia na {exit_number} saída sentido {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Entre na rotatória e saia na {exit_number} saída",
                    "name": "Entre na rotatória e saia na {exit_number} saída em {way_name}",
                    "destination": "Entre na rotatória e saia na {exit_number} saída sentido {destination}"
                },
                "default": {
                    "default": "Entre na rotatória",
                    "name": "Entre na rotatória e saia em {way_name}",
                    "destination": "Entre na rotatória e saia sentido {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Na rotatória, vire {modifier}",
                "name": "Na rotatória, vire {modifier} na {way_name}",
                "destination": "Na rotatória, vire {modifier} em direção à {destination}"
            },
            "left": {
                "default": "Na rotatória vire à esquerda",
                "name": "Na rotatória vire à esquerda em {way_name}",
                "destination": "Na rotatória vire à esquerda sentido {destination}"
            },
            "right": {
                "default": "Na rotatória vire à direita",
                "name": "Na rotatória vire à direita em {way_name}",
                "destination": "Na rotatória vire à direita sentido {destination}"
            },
            "straight": {
                "default": "Na rotatória siga reto",
                "name": "Na rotatória siga reto em {way_name}",
                "destination": "Na rotatória siga reto sentido {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} em {way_name}",
                "destination": "Siga {modifier} sentido {destination}"
            },
            "left": {
                "default": "Vire à esquerda",
                "name": "Vire à esquerda em {way_name}",
                "destination": "Vire à esquerda sentido {destination}"
            },
            "right": {
                "default": "Vire à direita",
                "name": "Vire à direita em {way_name}",
                "destination": "Vire à direita sentido {destination}"
            },
            "straight": {
                "default": "Siga reto",
                "name": "Siga reto em {way_name}",
                "destination": "Siga reto sentido {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} em {way_name}",
                "destination": "Siga {modifier} sentido {destination}"
            },
            "left": {
                "default": "Vire à esquerda",
                "name": "Vire à esquerda em {way_name}",
                "destination": "Vire à esquerda sentido {destination}"
            },
            "right": {
                "default": "Vire à direita",
                "name": "Vire à direita em {way_name}",
                "destination": "Vire à direita sentido {destination}"
            },
            "straight": {
                "default": "Siga reto",
                "name": "Siga reto em {way_name}",
                "destination": "Siga reto sentido {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Siga {modifier}",
                "name": "Siga {modifier} em {way_name}",
                "destination": "Siga {modifier} sentido {destination}"
            },
            "left": {
                "default": "Vire à esquerda",
                "name": "Vire à esquerda em {way_name}",
                "destination": "Vire à esquerda sentido {destination}"
            },
            "right": {
                "default": "Vire à direita",
                "name": "Vire à direita em {way_name}",
                "destination": "Vire à direita sentido {destination}"
            },
            "straight": {
                "default": "Siga reto",
                "name": "Siga reto em {way_name}",
                "destination": "Siga reto sentido {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Continue reto"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],17:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "prima",
                "2": "a 2-a",
                "3": "a 3-a",
                "4": "a 4-a",
                "5": "a 5-a",
                "6": "a 6-a",
                "7": "a 7-a",
                "8": "a 8-a",
                "9": "a 9-a",
                "10": "a 10-a"
            },
            "direction": {
                "north": "nord",
                "northeast": "nord-est",
                "east": "est",
                "southeast": "sud-est",
                "south": "sud",
                "southwest": "sud-vest",
                "west": "vest",
                "northwest": "nord-vest"
            },
            "modifier": {
                "left": "stânga",
                "right": "dreapta",
                "sharp left": "brusc stânga",
                "sharp right": "brusc dreapta",
                "slight left": "ușor stânga",
                "slight right": "ușor dreapta",
                "straight": "înainte",
                "uturn": "întoarcere"
            },
            "lanes": {
                "xo": "Menține dreapta",
                "ox": "Menține dreapta",
                "xox": "Menține pe interior",
                "oxo": "Menține pe laterale"
            }
        },
        "modes": {
            "ferry": {
                "default": "Ia feribotul",
                "name": "Ia feribotul {way_name}",
                "destination": "Ia feribotul spre {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} then in {distance} {instruction_two}",
            "two linked": "{instruction_one} apoi {instruction_two}",
            "one in distance": "În {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Ați ajuns la {nth} destinație"
            },
            "left": {
                "default": "Ați ajuns la {nth} destinație, pe stânga"
            },
            "right": {
                "default": "Ați ajuns la {nth} destinație, pe dreapta"
            },
            "sharp left": {
                "default": "Ați ajuns la {nth} destinație, pe stânga"
            },
            "sharp right": {
                "default": "Ați ajuns la {nth} destinație, pe dreapta"
            },
            "slight right": {
                "default": "Ați ajuns la {nth} destinație, pe dreapta"
            },
            "slight left": {
                "default": "Ați ajuns la {nth} destinație, pe stânga"
            },
            "straight": {
                "default": "Ați ajuns la {nth} destinație, în față"
            }
        },
        "continue": {
            "default": {
                "default": "Virează {modifier}",
                "name": "Virați {modifier} pe {way_name}",
                "destination": "Virați {modifier} spre {destination}",
                "exit": "Virați {modifier} pe {way_name}"
            },
            "straight": {
                "default": "Mergeți înainte",
                "name": "Continuați înainte pe {way_name}",
                "destination": "Continuați spre {destination}",
                "distance": "Continuați înainte {distance}",
                "namedistance": "Continuați pe {way_name} {distance}"
            },
            "sharp left": {
                "default": "Virați brusc stânga",
                "name": "Virați brusc stânga pe {way_name}",
                "destination": "Virați brusc stânga spre {destination}"
            },
            "sharp right": {
                "default": "Virați brusc dreapta",
                "name": "Virați brusc stânga pe {way_name}",
                "destination": "Virați brusc dreapta spre {destination}"
            },
            "slight left": {
                "default": "Virați ușor stânga",
                "name": "Virați ușor stânga pe {way_name}",
                "destination": "Virați ușor stânga spre {destination}"
            },
            "slight right": {
                "default": "Virați ușor dreapta",
                "name": "Virați ușor dreapta pe {way_name}",
                "destination": "Virați ușor dreapta spre {destination}"
            },
            "uturn": {
                "default": "Întoarceți-vă",
                "name": "Întoarceți-vă și continuați pe {way_name}",
                "destination": "Întoarceți-vă spre {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Mergeți {direction}",
                "name": "Mergeți {direction} pe {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Virați {modifier}",
                "name": "Virați {modifier} pe {way_name}",
                "destination": "Virați {modifier} spre {destination}"
            },
            "straight": {
                "default": "Continuați înainte",
                "name": "Continuați înainte pe {way_name}",
                "destination": "Continuați înainte spre {destination}"
            },
            "uturn": {
                "default": "Întoarceți-vă la sfârșitul drumului",
                "name": "Întoarceți-vă pe {way_name} la sfârșitul drumului",
                "destination": "Întoarceți-vă spre {destination} la sfârșitul drumului"
            }
        },
        "fork": {
            "default": {
                "default": "Mențineți {modifier} la bifurcație",
                "name": "Mențineți {modifier} la bifurcație pe {way_name}",
                "destination": "Mențineți {modifier} la bifurcație spre {destination}"
            },
            "slight left": {
                "default": "Mențineți stânga la bifurcație",
                "name": "Mențineți stânga la bifurcație pe {way_name}",
                "destination": "Mențineți stânga la bifurcație spre {destination}"
            },
            "slight right": {
                "default": "Mențineți dreapta la bifurcație",
                "name": "Mențineți dreapta la bifurcație pe {way_name}",
                "destination": "Mențineți dreapta la bifurcație spre {destination}"
            },
            "sharp left": {
                "default": "Virați brusc stânga la bifurcație",
                "name": "Virați brusc stânga la bifurcație pe {way_name}",
                "destination": "Virați brusc stânga la bifurcație spre {destination}"
            },
            "sharp right": {
                "default": "Virați brusc dreapta la bifurcație",
                "name": "Virați brusc dreapta la bifurcație pe {way_name}",
                "destination": "Virați brusc dreapta la bifurcație spre {destination}"
            },
            "uturn": {
                "default": "Întoarceți-vă",
                "name": "Întoarceți-vă pe {way_name}",
                "destination": "Întoarceți-vă spre {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Intrați în {modifier}",
                "name": "Intrați în {modifier} pe {way_name}",
                "destination": "Intrați în {modifier} spre {destination}"
            },
            "slight left": {
                "default": "Intrați în stânga",
                "name": "Intrați în stânga pe {way_name}",
                "destination": "Intrați în stânga spre {destination}"
            },
            "slight right": {
                "default": "Intrați în dreapta",
                "name": "Intrați în dreapta pe {way_name}",
                "destination": "Intrați în dreapta spre {destination}"
            },
            "sharp left": {
                "default": "Intrați în stânga",
                "name": "Intrați în stânga pe {way_name}",
                "destination": "Intrați în stânga spre {destination}"
            },
            "sharp right": {
                "default": "Intrați în dreapta",
                "name": "Intrați în dreapta pe {way_name}",
                "destination": "Intrați în dreapta spre {destination}"
            },
            "uturn": {
                "default": "Întoarceți-vă",
                "name": "Întoarceți-vă pe {way_name}",
                "destination": "Întoarceți-vă spre {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Continuați {modifier}",
                "name": "Continuați {modifier} pe {way_name}",
                "destination": "Continuați {modifier} spre {destination}"
            },
            "straight": {
                "default": "Continuați înainte",
                "name": "Continuați pe {way_name}",
                "destination": "Continuați spre {destination}"
            },
            "sharp left": {
                "default": "Virați brusc stânga",
                "name": "Virați brusc stânga pe {way_name}",
                "destination": "Virați brusc stânga spre {destination}"
            },
            "sharp right": {
                "default": "Virați brusc dreapta",
                "name": "Virați brusc dreapta pe {way_name}",
                "destination": "Virați brusc dreapta spre {destination}"
            },
            "slight left": {
                "default": "Continuați ușor stânga",
                "name": "Continuați ușor stânga pe {way_name}",
                "destination": "Continuați ușor stânga spre {destination}"
            },
            "slight right": {
                "default": "Continuați ușor dreapta",
                "name": "Continuați ușor dreapta pe {way_name}",
                "destination": "Continuați ușor dreapta spre {destination}"
            },
            "uturn": {
                "default": "Întoarceți-vă",
                "name": "Întoarceți-vă pe {way_name}",
                "destination": "Întoarceți-vă spre {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Continuați {modifier}",
                "name": "Continuați {modifier} pe {way_name}",
                "destination": "Continuați {modifier} spre {destination}"
            },
            "uturn": {
                "default": "Întoarceți-vă",
                "name": "Întoarceți-vă pe {way_name}",
                "destination": "Întoarceți-vă spre {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Urmați rampa",
                "name": "Urmați rampa pe {way_name}",
                "destination": "Urmați rampa spre {destination}",
                "exit": "Ieșiți pe ieșirea {exit}",
                "exit_destination": "Ieșiți pe ieșirea {exit}spre {destination}"
            },
            "left": {
                "default": "Urmați rampa pe stânga",
                "name": "Urmați rampa pe stânga pe {way_name}",
                "destination": "Urmați rampa pe stânga spre {destination}",
                "exit": "Ieșiți pe ieșirea {exit} pe stânga",
                "exit_destination": "Ieșiți pe ieșirea {exit} pe stânga spre {destination}"
            },
            "right": {
                "default": "Urmați rampa pe dreapta",
                "name": "Urmați rampa pe dreapta pe {way_name}",
                "destination": "Urmați rampa pe dreapta spre {destination}",
                "exit": "Ieșiți pe ieșirea {exit} pe dreapta",
                "exit_destination": "Ieșiți pe ieșirea {exit} pe dreapta spre {destination}"
            },
            "sharp left": {
                "default": "Urmați rampa pe stânga",
                "name": "Urmați rampa pe stânga pe {way_name}",
                "destination": "Urmați rampa pe stânga spre {destination}",
                "exit": "Ieșiți pe ieșirea {exit} pe stânga",
                "exit_destination": "Ieșiți pe ieșirea {exit} pe stânga spre {destination}"
            },
            "sharp right": {
                "default": "Urmați rampa pe dreapta",
                "name": "Urmați rampa pe dreapta pe {way_name}",
                "destination": "Urmați rampa pe dreapta spre {destination}",
                "exit": "Ieșiți pe ieșirea {exit} pe dreapta",
                "exit_destination": "Ieșiți pe ieșirea {exit} pe dreapta spre {destination}"
            },
            "slight left": {
                "default": "Urmați rampa pe stânga",
                "name": "Urmați rampa pe stânga pe {way_name}",
                "destination": "Urmați rampa pe stânga spre {destination}",
                "exit": "Ieșiți pe ieșirea {exit} pe stânga",
                "exit_destination": "Ieșiți pe ieșirea {exit} pe stânga spre {destination}"
            },
            "slight right": {
                "default": "Urmați rampa pe dreapta",
                "name": "Urmați rampa pe dreapta pe {way_name}",
                "destination": "Urmați rampa pe dreapta spre {destination}",
                "exit": "Ieșiți pe ieșirea {exit} pe dreapta",
                "exit_destination": "Ieșiți pe ieșirea {exit} pe dreapta spre {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Urmați rampa",
                "name": "Urmați rampa pe {way_name}",
                "destination": "Urmați rampa spre {destination}"
            },
            "left": {
                "default": "Urmați rampa pe stânga",
                "name": "Urmați rampa pe stânga pe {way_name}",
                "destination": "Urmați rampa pe stânga spre {destination}"
            },
            "right": {
                "default": "Urmați rampa pe dreapta",
                "name": "Urmați rampa pe dreapta pe {way_name}",
                "destination": "Urmați rampa pe dreapta spre {destination}"
            },
            "sharp left": {
                "default": "Urmați rampa pe stânga",
                "name": "Urmați rampa pe stânga pe {way_name}",
                "destination": "Urmați rampa pe stânga spre {destination}"
            },
            "sharp right": {
                "default": "Urmați rampa pe dreapta",
                "name": "Urmați rampa pe dreapta pe {way_name}",
                "destination": "Urmați rampa pe dreapta spre {destination}"
            },
            "slight left": {
                "default": "Urmați rampa pe stânga",
                "name": "Urmați rampa pe stânga pe {way_name}",
                "destination": "Urmați rampa pe stânga spre {destination}"
            },
            "slight right": {
                "default": "Urmați rampa pe dreapta",
                "name": "Urmați rampa pe dreapta pe {way_name}",
                "destination": "Urmați rampa pe dreapta spre {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Intrați în sensul giratoriu",
                    "name": "Intrați în sensul giratoriu și ieșiți pe {way_name}",
                    "destination": "Intrați în sensul giratoriu și ieșiți spre {destination}"
                },
                "name": {
                    "default": "Intrați în  {rotary_name}",
                    "name": "Intrați în  {rotary_name} și ieșiți pe {way_name}",
                    "destination": "Intrați în  {rotary_name} și ieșiți spre {destination}"
                },
                "exit": {
                    "default": "Intrați în sensul giratoriu și mergeți spre ieșirea {exit_number}",
                    "name": "Intrați în sensul giratoriu și mergeți spre ieșirea {exit_number} pe {way_name}",
                    "destination": "Intrați în sensul giratoriu și mergeți spre ieșirea {exit_number} spre {destination}"
                },
                "name_exit": {
                    "default": "Intrați în  {rotary_name} și mergeți spre ieșirea {exit_number}",
                    "name": "Intrați în  {rotary_name} și mergeți spre ieșirea {exit_number} pe {way_name}",
                    "destination": "Intrați în  {rotary_name} și mergeți spre ieșirea {exit_number} spre {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Intrați în sensul giratoriu și mergeți spre ieșirea {exit_number}",
                    "name": "Intrați în sensul giratoriu și mergeți spre ieșirea {exit_number} pe {way_name}",
                    "destination": "Intrați în sensul giratoriu și mergeți spre ieșirea {exit_number} spre {destination}"
                },
                "default": {
                    "default": "Intrați în sensul giratoriu",
                    "name": "Intrați în sensul giratoriu și ieșiți pe {way_name}",
                    "destination": "Intrați în sensul giratoriu și ieșiți spre {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "La sensul giratoriu virați {modifier}",
                "name": "La sensul giratoriu virați {modifier} pe {way_name}",
                "destination": "La sensul giratoriu virați {modifier} spre {destination}"
            },
            "left": {
                "default": "La sensul giratoriu virați stânga",
                "name": "La sensul giratoriu virați stânga pe {way_name}",
                "destination": "La sensul giratoriu virați stânga spre {destination}"
            },
            "right": {
                "default": "La sensul giratoriu virați dreapta",
                "name": "La sensul giratoriu virați dreapta pe {way_name}",
                "destination": "La sensul giratoriu virați dreapta spre {destination}"
            },
            "straight": {
                "default": "La sensul giratoriu continuați înainte",
                "name": "La sensul giratoriu continuați înainte pe {way_name}",
                "destination": "La sensul giratoriu continuați înainte spre {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Virați {modifier}",
                "name": "Virați {modifier} pe {way_name}",
                "destination": "Virați {modifier} spre {destination}"
            },
            "left": {
                "default": "Virați stânga",
                "name": "Virați stânga pe {way_name}",
                "destination": "Virați stânga spre {destination}"
            },
            "right": {
                "default": "Virați dreapta",
                "name": "Virați dreapta pe {way_name}",
                "destination": "Virați dreapta spre {destination}"
            },
            "straight": {
                "default": "Mergeți înainte",
                "name": "Mergeți înainte pe {way_name}",
                "destination": "Mergeți înainte spre {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Virați {modifier}",
                "name": "Virați {modifier} pe {way_name}",
                "destination": "Virați {modifier} spre {destination}"
            },
            "left": {
                "default": "Virați stânga",
                "name": "Virați stânga pe {way_name}",
                "destination": "Virați stânga spre {destination}"
            },
            "right": {
                "default": "Virați dreapta",
                "name": "Virați dreapta pe {way_name}",
                "destination": "Virați dreapta spre {destination}"
            },
            "straight": {
                "default": "Mergeți înainte",
                "name": "Mergeți înainte pe {way_name}",
                "destination": "Mergeți înainte spre {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Virați {modifier}",
                "name": "Virați {modifier} pe {way_name}",
                "destination": "Virați {modifier} spre {destination}"
            },
            "left": {
                "default": "Virați stânga",
                "name": "Virați stânga pe {way_name}",
                "destination": "Virați stânga spre {destination}"
            },
            "right": {
                "default": "Virați dreapta",
                "name": "Virați dreapta pe {way_name}",
                "destination": "Virați dreapta spre {destination}"
            },
            "straight": {
                "default": "Mergeți înainte",
                "name": "Mergeți înainte pe {way_name}",
                "destination": "Mergeți înainte spre {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Mergeți înainte"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],18:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "первый",
                "2": "второй",
                "3": "третий",
                "4": "четвёртый",
                "5": "пятый",
                "6": "шестой",
                "7": "седьмой",
                "8": "восьмой",
                "9": "девятый",
                "10": "десятый"
            },
            "direction": {
                "north": "северном",
                "northeast": "северо-восточном",
                "east": "восточном",
                "southeast": "юго-восточном",
                "south": "южном",
                "southwest": "юго-западном",
                "west": "западном",
                "northwest": "северо-западном"
            },
            "modifier": {
                "left": "налево",
                "right": "направо",
                "sharp left": "налево",
                "sharp right": "направо",
                "slight left": "левее",
                "slight right": "правее",
                "straight": "прямо",
                "uturn": "на разворот"
            },
            "lanes": {
                "xo": "Держитесь правее",
                "ox": "Держитесь левее",
                "xox": "Держитесь посередине",
                "oxo": "Держитесь слева или справа"
            }
        },
        "modes": {
            "ferry": {
                "default": "Погрузитесь на паром",
                "name": "Погрузитесь на паром {way_name}",
                "destination": "Погрузитесь на паром в направлении {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one}, затем через {distance} {instruction_two}",
            "two linked": "{instruction_one}, затем {instruction_two}",
            "one in distance": "Через {distance} {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Вы прибыли в {nth} пункт назначения"
            },
            "left": {
                "default": "Вы прибыли в {nth} пункт назначения, он находится слева"
            },
            "right": {
                "default": "Вы прибыли в {nth} пункт назначения, он находится справа"
            },
            "sharp left": {
                "default": "Вы прибыли в {nth} пункт назначения, он находится слева"
            },
            "sharp right": {
                "default": "Вы прибыли в {nth} пункт назначения, он находится справа"
            },
            "slight right": {
                "default": "Вы прибыли в {nth} пункт назначения, он находится справа"
            },
            "slight left": {
                "default": "Вы прибыли в {nth} пункт назначения, он находится слева"
            },
            "straight": {
                "default": "Вы прибыли в {nth} пункт назначения, он находится перед вами"
            }
        },
        "continue": {
            "default": {
                "default": "Двигайтесь {modifier}",
                "name": "Двигайтесь {modifier} по {way_name:dative}",
                "destination": "Двигайтесь {modifier} в направлении {destination}",
                "exit": "Двигайтесь {modifier} на {way_name:accusative}"
            },
            "straight": {
                "default": "Двигайтесь прямо",
                "name": "Продолжите движение по {way_name:dative}",
                "destination": "Продолжите движение в направлении {destination}",
                "distance": "Двигайтесь прямо {distance}",
                "namedistance": "Двигайтесь прямо {distance} по {way_name:dative}"
            },
            "sharp left": {
                "default": "Резко поверните налево",
                "name": "Резко поверните налево на {way_name:accusative}",
                "destination": "Резко поверните налево в направлении {destination}"
            },
            "sharp right": {
                "default": "Резко поверните направо",
                "name": "Резко поверните направо на {way_name:accusative}",
                "destination": "Резко поверните направо в направлении {destination}"
            },
            "slight left": {
                "default": "Плавно поверните налево",
                "name": "Плавно поверните налево на {way_name:accusative}",
                "destination": "Плавно поверните налево в направлении {destination}"
            },
            "slight right": {
                "default": "Плавно поверните направо",
                "name": "Плавно поверните направо на {way_name:accusative}",
                "destination": "Плавно поверните направо в направлении {destination}"
            },
            "uturn": {
                "default": "Развернитесь",
                "name": "Развернитесь и продолжите движение по {way_name:dative}",
                "destination": "Развернитесь в направлении {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Двигайтесь в {direction} направлении",
                "name": "Двигайтесь в {direction} направлении по {way_name:dative}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Поверните {modifier}",
                "name": "Поверните {modifier} на {way_name:accusative}",
                "destination": "Поверните {modifier} в направлении {destination}"
            },
            "straight": {
                "default": "Двигайтесь прямо",
                "name": "Двигайтесь прямо по {way_name:dative}",
                "destination": "Двигайтесь прямо в направлении {destination}"
            },
            "uturn": {
                "default": "В конце дороги развернитесь",
                "name": "Развернитесь в конце {way_name:genitive}",
                "destination": "В конце дороги развернитесь в направлении {destination}"
            }
        },
        "fork": {
            "default": {
                "default": "На развилке двигайтесь {modifier}",
                "name": "На развилке двигайтесь {modifier} на {way_name:accusative}",
                "destination": "На развилке двигайтесь {modifier} в направлении {destination}"
            },
            "slight left": {
                "default": "На развилке держитесь левее",
                "name": "На развилке держитесь левее на {way_name:accusative}",
                "destination": "На развилке держитесь левее и продолжите движение в направлении {destination}"
            },
            "slight right": {
                "default": "На развилке держитесь правее",
                "name": "На развилке держитесь правее на {way_name:accusative}",
                "destination": "На развилке держитесь правее и продолжите движение в направлении {destination}"
            },
            "sharp left": {
                "default": "На развилке резко поверните налево",
                "name": "На развилке резко поверните налево на {way_name:accusative}",
                "destination": "На развилке резко поверните налево и продолжите движение в направлении {destination}"
            },
            "sharp right": {
                "default": "На развилке резко поверните направо",
                "name": "На развилке резко поверните направо на {way_name:accusative}",
                "destination": "На развилке резко поверните направо и продолжите движение в направлении {destination}"
            },
            "uturn": {
                "default": "На развилке развернитесь",
                "name": "На развилке развернитесь на {way_name:prepositional}",
                "destination": "На развилке развернитесь и продолжите движение в направлении {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Перестройтесь {modifier}",
                "name": "Перестройтесь {modifier} на {way_name:accusative}",
                "destination": "Перестройтесь {modifier} в направлении {destination}"
            },
            "slight left": {
                "default": "Перестройтесь левее",
                "name": "Перестройтесь левее на {way_name:accusative}",
                "destination": "Перестройтесь левее в направлении {destination}"
            },
            "slight right": {
                "default": "Перестройтесь правее",
                "name": "Перестройтесь правее на {way_name:accusative}",
                "destination": "Перестройтесь правее в направлении {destination}"
            },
            "sharp left": {
                "default": "Перестраивайтесь левее",
                "name": "Перестраивайтесь левее на {way_name:accusative}",
                "destination": "Перестраивайтесь левее в направлении {destination}"
            },
            "sharp right": {
                "default": "Перестраивайтесь правее",
                "name": "Перестраивайтесь правее на {way_name:accusative}",
                "destination": "Перестраивайтесь правее в направлении {destination}"
            },
            "uturn": {
                "default": "Развернитесь",
                "name": "Развернитесь на {way_name:prepositional}",
                "destination": "Развернитесь в направлении {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Двигайтесь {modifier}",
                "name": "Двигайтесь {modifier} на {way_name:accusative}",
                "destination": "Двигайтесь {modifier} в направлении {destination}"
            },
            "straight": {
                "default": "Двигайтесь прямо",
                "name": "Продолжите движение по {way_name:dative}",
                "destination": "Продолжите движение в направлении {destination}"
            },
            "sharp left": {
                "default": "Резко поверните налево",
                "name": "Резко поверните налево на {way_name:accusative}",
                "destination": "Резко поверните налево и продолжите движение в направлении {destination}"
            },
            "sharp right": {
                "default": "Резко поверните направо",
                "name": "Резко поверните направо на {way_name:accusative}",
                "destination": "Резко поверните направо и продолжите движение в направлении {destination}"
            },
            "slight left": {
                "default": "Плавно поверните налево",
                "name": "Плавно поверните налево на {way_name:accusative}",
                "destination": "Плавно поверните налево в направлении {destination}"
            },
            "slight right": {
                "default": "Плавно поверните направо",
                "name": "Плавно поверните направо на {way_name:accusative}",
                "destination": "Плавно поверните направо в направлении {destination}"
            },
            "uturn": {
                "default": "Развернитесь",
                "name": "Развернитесь на {way_name:prepositional}",
                "destination": "Развернитесь и продолжите движение в направлении {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Двигайтесь {modifier}",
                "name": "Двигайтесь {modifier} по {way_name:dative}",
                "destination": "Двигайтесь {modifier} в направлении {destination}"
            },
            "uturn": {
                "default": "Развернитесь",
                "name": "Развернитесь на {way_name:prepositional}",
                "destination": "Развернитесь и продолжите движение в направлении {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Сверните на съезд",
                "name": "Сверните на съезд на {way_name:accusative}",
                "destination": "Сверните на съезд в направлении {destination}",
                "exit": "Сверните на съезд {exit}",
                "exit_destination": "Сверните на съезд {exit} в направлении {destination}"
            },
            "left": {
                "default": "Сверните на левый съезд",
                "name": "Сверните на левый съезд на {way_name:accusative}",
                "destination": "Сверните на левый съезд в направлении {destination}",
                "exit": "Сверните на съезд {exit} слева",
                "exit_destination": "Сверните на съезд {exit} слева в направлении {destination}"
            },
            "right": {
                "default": "Сверните на правый съезд",
                "name": "Сверните на правый съезд на {way_name:accusative}",
                "destination": "Сверните на правый съезд в направлении {destination}",
                "exit": "Сверните на съезд {exit} справа",
                "exit_destination": "Сверните на съезд {exit} справа в направлении {destination}"
            },
            "sharp left": {
                "default": "Поверните налево на съезд",
                "name": "Поверните налево на съезд на {way_name:accusative}",
                "destination": "Поверните налево на съезд в направлении {destination}",
                "exit": "Поверните налево на съезд {exit}",
                "exit_destination": "Поверните налево на съезд {exit} в направлении {destination}"
            },
            "sharp right": {
                "default": "Поверните направо на съезд",
                "name": "Поверните направо на съезд на {way_name:accusative}",
                "destination": "Поверните направо на съезд в направлении {destination}",
                "exit": "Поверните направо на съезд {exit}",
                "exit_destination": "Поверните направо на съезд {exit} в направлении {destination}"
            },
            "slight left": {
                "default": "Перестройтесь левее на съезд",
                "name": "Перестройтесь левее на съезд на {way_name:accusative}",
                "destination": "Перестройтесь левее на съезд в направлении {destination}",
                "exit": "Перестройтесь левее на {exit}",
                "exit_destination": "Перестройтесь левее на съезд {exit} в направлении {destination}"
            },
            "slight right": {
                "default": "Перестройтесь правее на съезд",
                "name": "Перестройтесь правее на съезд на {way_name:accusative}",
                "destination": "Перестройтесь правее на съезд в направлении {destination}",
                "exit": "Перестройтесь правее на съезд {exit}",
                "exit_destination": "Перестройтесь правее на съезд {exit} в направлении {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Сверните на автомагистраль",
                "name": "Сверните на въезд на {way_name:accusative}",
                "destination": "Сверните на въезд на автомагистраль в направлении {destination}"
            },
            "left": {
                "default": "Сверните на левый въезд на автомагистраль",
                "name": "Сверните на левый въезд на {way_name:accusative}",
                "destination": "Сверните на левый въезд на автомагистраль в направлении {destination}"
            },
            "right": {
                "default": "Сверните на правый въезд на автомагистраль",
                "name": "Сверните на правый въезд на {way_name:accusative}",
                "destination": "Сверните на правый въезд на автомагистраль в направлении {destination}"
            },
            "sharp left": {
                "default": "Поверните на левый въезд на автомагистраль",
                "name": "Поверните на левый въезд на {way_name:accusative}",
                "destination": "Поверните на левый въезд на автомагистраль в направлении {destination}"
            },
            "sharp right": {
                "default": "Поверните на правый въезд на автомагистраль",
                "name": "Поверните на правый въезд на {way_name:accusative}",
                "destination": "Поверните на правый въезд на автомагистраль в направлении {destination}"
            },
            "slight left": {
                "default": "Перестройтесь левее на въезд на автомагистраль",
                "name": "Перестройтесь левее на {way_name:accusative}",
                "destination": "Перестройтесь левее на автомагистраль в направлении {destination}"
            },
            "slight right": {
                "default": "Перестройтесь правее на въезд на автомагистраль",
                "name": "Перестройтесь правее на {way_name:accusative}",
                "destination": "Перестройтесь правее на автомагистраль в направлении {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Продолжите движение по круговой развязке",
                    "name": "На круговой развязке сверните на {way_name:accusative}",
                    "destination": "На круговой развязке сверните в направлении {destination}"
                },
                "name": {
                    "default": "Продолжите движение по {rotary_name:dative}",
                    "name": "На {rotary_name:prepositional} сверните на {way_name:accusative}",
                    "destination": "На {rotary_name:prepositional} сверните в направлении {destination}"
                },
                "exit": {
                    "default": "На круговой развязке сверните на {exit_number} съезд",
                    "name": "На круговой развязке сверните на {exit_number} съезд на {way_name:accusative}",
                    "destination": "На круговой развязке сверните на {exit_number} съезд в направлении {destination}"
                },
                "name_exit": {
                    "default": "На {rotary_name:prepositional} сверните на {exit_number} съезд",
                    "name": "На {rotary_name:prepositional} сверните на {exit_number} съезд на {way_name:accusative}",
                    "destination": "На {rotary_name:prepositional} сверните на {exit_number} съезд в направлении {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "На круговой развязке сверните на {exit_number} съезд",
                    "name": "На круговой развязке сверните на {exit_number} съезд на {way_name:accusative}",
                    "destination": "На круговой развязке сверните на {exit_number} съезд в направлении {destination}"
                },
                "default": {
                    "default": "Продолжите движение по круговой развязке",
                    "name": "На круговой развязке сверните на {way_name:accusative}",
                    "destination": "На круговой развязке сверните в направлении {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "На круговой развязке двигайтесь {modifier}",
                "name": "На круговой развязке двигайтесь {modifier} на {way_name:accusative}",
                "destination": "На круговой развязке двигайтесь {modifier} в направлении {destination}"
            },
            "left": {
                "default": "На круговой развязке сверните налево",
                "name": "На круговой развязке сверните налево на {way_name:accusative}",
                "destination": "На круговой развязке сверните налево в направлении {destination}"
            },
            "right": {
                "default": "На круговой развязке сверните направо",
                "name": "На круговой развязке сверните направо на {way_name:accusative}",
                "destination": "На круговой развязке сверните направо в направлении {destination}"
            },
            "straight": {
                "default": "На круговой развязке двигайтесь прямо",
                "name": "На круговой развязке двигайтесь по {way_name:dative}",
                "destination": "На круговой развязке двигайтесь в направлении {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Двигайтесь {modifier}",
                "name": "Двигайтесь {modifier} на {way_name:accusative}",
                "destination": "Двигайтесь {modifier} в направлении {destination}"
            },
            "left": {
                "default": "Сверните налево",
                "name": "Сверните налево на {way_name:accusative}",
                "destination": "Сверните налево в направлении {destination}"
            },
            "right": {
                "default": "Сверните направо",
                "name": "Сверните направо на {way_name:accusative}",
                "destination": "Сверните направо в направлении {destination}"
            },
            "straight": {
                "default": "Двигайтесь прямо",
                "name": "Двигайтесь по {way_name:dative}",
                "destination": "Двигайтесь в направлении {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Двигайтесь {modifier}",
                "name": "Двигайтесь {modifier} на {way_name:accusative}",
                "destination": "Двигайтесь {modifier} в направлении {destination}"
            },
            "left": {
                "default": "Сверните налево",
                "name": "Сверните налево на {way_name:accusative}",
                "destination": "Сверните налево в направлении {destination}"
            },
            "right": {
                "default": "Сверните направо",
                "name": "Сверните направо на {way_name:accusative}",
                "destination": "Сверните направо в направлении {destination}"
            },
            "straight": {
                "default": "Двигайтесь прямо",
                "name": "Двигайтесь по {way_name:dative}",
                "destination": "Двигайтесь в направлении {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Двигайтесь {modifier}",
                "name": "Двигайтесь {modifier} на {way_name:accusative}",
                "destination": "Двигайтесь {modifier}  в направлении {destination}"
            },
            "left": {
                "default": "Поверните налево",
                "name": "Поверните налево на {way_name:accusative}",
                "destination": "Поверните налево в направлении {destination}"
            },
            "right": {
                "default": "Поверните направо",
                "name": "Поверните направо на {way_name:accusative}",
                "destination": "Поверните направо  в направлении {destination}"
            },
            "straight": {
                "default": "Двигайтесь прямо",
                "name": "Двигайтесь по {way_name:dative}",
                "destination": "Двигайтесь в направлении {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Продолжайте движение прямо"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],19:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1:a",
                "2": "2:a",
                "3": "3:e",
                "4": "4:e",
                "5": "5:e",
                "6": "6:e",
                "7": "7:e",
                "8": "8:e",
                "9": "9:e",
                "10": "10:e"
            },
            "direction": {
                "north": "norr",
                "northeast": "nordost",
                "east": "öster",
                "southeast": "sydost",
                "south": "söder",
                "southwest": "sydväst",
                "west": "väster",
                "northwest": "nordväst"
            },
            "modifier": {
                "left": "vänster",
                "right": "höger",
                "sharp left": "vänster",
                "sharp right": "höger",
                "slight left": "vänster",
                "slight right": "höger",
                "straight": "rakt fram",
                "uturn": "U-sväng"
            },
            "lanes": {
                "xo": "Håll till höger",
                "ox": "Håll till vänster",
                "xox": "Håll till mitten",
                "oxo": "Håll till vänster eller höger"
            }
        },
        "modes": {
            "ferry": {
                "default": "Ta färjan",
                "name": "Ta färjan på {way_name}",
                "destination": "Ta färjan mot {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one}, sedan efter {distance}, {instruction_two}",
            "two linked": "{instruction_one}, sedan {instruction_two}",
            "one in distance": "Om {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Du är framme vid din {nth} destination"
            },
            "left": {
                "default": "Du är framme vid din {nth} destination, till vänster"
            },
            "right": {
                "default": "Du är framme vid din {nth} destination, till höger"
            },
            "sharp left": {
                "default": "Du är framme vid din {nth} destination, skarpt till vänster"
            },
            "sharp right": {
                "default": "Du är framme vid din {nth} destination, skarpt till höger"
            },
            "slight right": {
                "default": "Du är framme vid din {nth} destination, till höger"
            },
            "slight left": {
                "default": "Du är framme vid din {nth} destination, till vänster"
            },
            "straight": {
                "default": "Du är framme vid din {nth} destination, rakt fram"
            }
        },
        "continue": {
            "default": {
                "default": "Sväng {modifier}",
                "name": "Sväng {modifier} och fortsätt på {way_name}",
                "destination": "Sväng {modifier} mot {destination}",
                "exit": "Sväng {modifier} in på {way_name}"
            },
            "straight": {
                "default": "Fortsätt rakt fram",
                "name": "Kör rakt fram och fortsätt på {way_name}",
                "destination": "Fortsätt mot {destination}",
                "distance": "Fortsätt rakt fram i {distance}",
                "namedistance": "Fortsätt på {way_name} i {distance}"
            },
            "sharp left": {
                "default": "Sväng vänster",
                "name": "Sväng vänster och fortsätt på {way_name}",
                "destination": "Sväng vänster mot {destination}"
            },
            "sharp right": {
                "default": "Sväng höger",
                "name": "Sväng höger och fortsätt på {way_name}",
                "destination": "Sväng höger mot {destination}"
            },
            "slight left": {
                "default": "Sväng vänster",
                "name": "Sväng vänster och fortsätt på {way_name}",
                "destination": "Sväng vänster mot {destination}"
            },
            "slight right": {
                "default": "Sväng höger",
                "name": "Sväng höger och fortsätt på {way_name}",
                "destination": "Sväng höger mot {destination}"
            },
            "uturn": {
                "default": "Gör en U-sväng",
                "name": "Gör en U-sväng och fortsätt på {way_name}",
                "destination": "Gör en U-sväng mot {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Kör åt {direction}",
                "name": "Kör åt {direction} på {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Sväng {modifier}",
                "name": "Sväng {modifier} in på {way_name}",
                "destination": "Sväng {modifier} mot {destination}"
            },
            "straight": {
                "default": "Fortsätt rakt fram",
                "name": "Fortsätt rakt fram in på {way_name}",
                "destination": "Fortsätt rakt fram mot {destination}"
            },
            "uturn": {
                "default": "Gör en U-sväng i slutet av vägen",
                "name": "Gör en U-sväng in på {way_name} i slutet av vägen",
                "destination": "Gör en U-sväng mot {destination} i slutet av vägen"
            }
        },
        "fork": {
            "default": {
                "default": "Håll till {modifier} där vägen delar sig",
                "name": "Håll till {modifier} in på {way_name}",
                "destination": "Håll till {modifier} mot {destination}"
            },
            "slight left": {
                "default": "Håll till vänster där vägen delar sig",
                "name": "Håll till vänster in på {way_name}",
                "destination": "Håll till vänster mot {destination}"
            },
            "slight right": {
                "default": "Håll till höger där vägen delar sig",
                "name": "Håll till höger in på {way_name}",
                "destination": "Håll till höger mot {destination}"
            },
            "sharp left": {
                "default": "Sväng vänster där vägen delar sig",
                "name": "Sväng vänster in på {way_name}",
                "destination": "Sväng vänster mot {destination}"
            },
            "sharp right": {
                "default": "Sväng höger där vägen delar sig",
                "name": "Sväng höger in på {way_name}",
                "destination": "Sväng höger mot {destination}"
            },
            "uturn": {
                "default": "Gör en U-sväng",
                "name": "Gör en U-sväng in på {way_name}",
                "destination": "Gör en U-sväng mot {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Byt till {modifier} körfält",
                "name": "Byt till {modifier} körfält in på {way_name}",
                "destination": "Byt till {modifier} körfält mot {destination}"
            },
            "slight left": {
                "default": "Byt till vänstra körfältet",
                "name": "Byt till vänstra körfältet in på {way_name}",
                "destination": "Byt till vänstra körfältet mot {destination}"
            },
            "slight right": {
                "default": "Byt till högra körfältet",
                "name": "Byt till högra körfältet in på {way_name}",
                "destination": "Byt till högra körfältet mot {destination}"
            },
            "sharp left": {
                "default": "Byt till vänstra körfältet",
                "name": "Byt till vänstra körfältet in på {way_name}",
                "destination": "Byt till vänstra körfältet mot {destination}"
            },
            "sharp right": {
                "default": "Byt till högra körfältet",
                "name": "Byt till högra körfältet in på {way_name}",
                "destination": "Byt till högra körfältet mot {destination}"
            },
            "uturn": {
                "default": "Gör en U-sväng",
                "name": "Gör en U-sväng in på {way_name}",
                "destination": "Gör en U-sväng mot {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Fortsätt {modifier}",
                "name": "Fortsätt {modifier} på {way_name}",
                "destination": "Fortsätt {modifier} mot {destination}"
            },
            "straight": {
                "default": "Fortsätt rakt fram",
                "name": "Fortsätt in på {way_name}",
                "destination": "Fortsätt mot {destination}"
            },
            "sharp left": {
                "default": "Gör en skarp vänstersväng",
                "name": "Gör en skarp vänstersväng in på {way_name}",
                "destination": "Gör en skarp vänstersväng mot {destination}"
            },
            "sharp right": {
                "default": "Gör en skarp högersväng",
                "name": "Gör en skarp högersväng in på {way_name}",
                "destination": "Gör en skarp högersväng mot {destination}"
            },
            "slight left": {
                "default": "Fortsätt med lätt vänstersväng",
                "name": "Fortsätt med lätt vänstersväng in på {way_name}",
                "destination": "Fortsätt med lätt vänstersväng mot {destination}"
            },
            "slight right": {
                "default": "Fortsätt med lätt högersväng",
                "name": "Fortsätt med lätt högersväng in på {way_name}",
                "destination": "Fortsätt med lätt högersväng mot {destination}"
            },
            "uturn": {
                "default": "Gör en U-sväng",
                "name": "Gör en U-sväng in på {way_name}",
                "destination": "Gör en U-sväng mot {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Fortsätt {modifier}",
                "name": "Fortsätt {modifier} på {way_name}",
                "destination": "Fortsätt {modifier} mot {destination}"
            },
            "uturn": {
                "default": "Gör en U-sväng",
                "name": "Gör en U-sväng in på {way_name}",
                "destination": "Gör en U-sväng mot {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Ta avfarten",
                "name": "Ta avfarten in på {way_name}",
                "destination": "Ta avfarten mot {destination}",
                "exit": "Ta avfart {exit} ",
                "exit_destination": "Ta avfart {exit} mot {destination}"
            },
            "left": {
                "default": "Ta avfarten till vänster",
                "name": "Ta avfarten till vänster in på {way_name}",
                "destination": "Ta avfarten till vänster mot {destination}",
                "exit": "Ta avfart {exit} till vänster",
                "exit_destination": "Ta avfart {exit} till vänster mot {destination}"
            },
            "right": {
                "default": "Ta avfarten till höger",
                "name": "Ta avfarten till höger in på {way_name}",
                "destination": "Ta avfarten till höger mot {destination}",
                "exit": "Ta avfart {exit} till höger",
                "exit_destination": "Ta avfart {exit} till höger mot {destination}"
            },
            "sharp left": {
                "default": "Ta avfarten till vänster",
                "name": "Ta avfarten till vänster in på {way_name}",
                "destination": "Ta avfarten till vänster mot {destination}",
                "exit": "Ta avfart {exit} till vänster",
                "exit_destination": "Ta avfart {exit} till vänster mot {destination}"
            },
            "sharp right": {
                "default": "Ta avfarten till höger",
                "name": "Ta avfarten till höger in på {way_name}",
                "destination": "Ta avfarten till höger mot {destination}",
                "exit": "Ta avfart {exit} till höger",
                "exit_destination": "Ta avfart {exit} till höger mot {destination}"
            },
            "slight left": {
                "default": "Ta avfarten till vänster",
                "name": "Ta avfarten till vänster in på {way_name}",
                "destination": "Ta avfarten till vänster mot {destination}",
                "exit": "Ta avfart {exit} till vänster",
                "exit_destination": "Ta avfart{exit} till vänster mot {destination}"
            },
            "slight right": {
                "default": "Ta avfarten till höger",
                "name": "Ta avfarten till höger in på {way_name}",
                "destination": "Ta avfarten till höger mot {destination}",
                "exit": "Ta avfart {exit} till höger",
                "exit_destination": "Ta avfart {exit} till höger mot {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Ta påfarten",
                "name": "Ta påfarten in på {way_name}",
                "destination": "Ta påfarten mot {destination}"
            },
            "left": {
                "default": "Ta påfarten till vänster",
                "name": "Ta påfarten till vänster in på {way_name}",
                "destination": "Ta påfarten till vänster mot {destination}"
            },
            "right": {
                "default": "Ta påfarten till höger",
                "name": "Ta påfarten till höger in på {way_name}",
                "destination": "Ta påfarten till höger mot {destination}"
            },
            "sharp left": {
                "default": "Ta påfarten till vänster",
                "name": "Ta påfarten till vänster in på {way_name}",
                "destination": "Ta påfarten till vänster mot {destination}"
            },
            "sharp right": {
                "default": "Ta påfarten till höger",
                "name": "Ta påfarten till höger in på {way_name}",
                "destination": "Ta påfarten till höger mot {destination}"
            },
            "slight left": {
                "default": "Ta påfarten till vänster",
                "name": "Ta påfarten till vänster in på {way_name}",
                "destination": "Ta påfarten till vänster mot {destination}"
            },
            "slight right": {
                "default": "Ta påfarten till höger",
                "name": "Ta påfarten till höger in på {way_name}",
                "destination": "Ta påfarten till höger mot {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Kör in i rondellen",
                    "name": "I rondellen ta av in på {way_name}",
                    "destination": "I rondellen ta av mot {destination}"
                },
                "name": {
                    "default": "Kör in i {rotary_name}",
                    "name": "I {rotary_name} ta av in på {way_name}",
                    "destination": "I {rotary_name} ta av mot {destination}"
                },
                "exit": {
                    "default": "I rondellen ta {exit_number} avfarten",
                    "name": "I rondellen ta {exit_number} avfarten in på {way_name}",
                    "destination": "I rondellen ta {exit_number} avfarten mot {destination}"
                },
                "name_exit": {
                    "default": "I {rotary_name} ta {exit_number} avfarten",
                    "name": "I {rotary_name} ta {exit_number}  avfarten in på {way_name}",
                    "destination": "I {rotary_name} ta {exit_number} avfarten mot {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "I rondellen ta {exit_number} avfarten",
                    "name": "I rondellen ta {exit_number} avfarten in på {way_name}",
                    "destination": "I rondellen ta {exit_number} avfarten mot {destination}"
                },
                "default": {
                    "default": "Kör in i rondellen",
                    "name": "I rondellen ta av mot {way_name}",
                    "destination": "I rondellen ta av mot {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "I rondellen sväng {modifier}",
                "name": "I rondellen sväng {modifier} in på {way_name}",
                "destination": "I rondellen sväng {modifier} mot {destination}"
            },
            "left": {
                "default": "I rondellen sväng vänster",
                "name": "I rondellen sväng vänster in på {way_name}",
                "destination": "I rondellen sväng vänster mot {destination}"
            },
            "right": {
                "default": "I rondellen sväng höger",
                "name": "I rondellen sväng höger in på {way_name}",
                "destination": "I rondellen sväng höger mot {destination}"
            },
            "straight": {
                "default": "I rondellen fortsätt rakt fram",
                "name": "I rondellen fortsätt rakt fram in på {way_name}",
                "destination": "I rondellen fortsätt rakt fram mot {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Sväng {modifier}",
                "name": "Sväng {modifier} in på {way_name}",
                "destination": "Sväng {modifier} mot {destination}"
            },
            "left": {
                "default": "Sväng vänster",
                "name": "Sväng vänster in på {way_name}",
                "destination": "Sväng vänster mot {destination}"
            },
            "right": {
                "default": "Sväng höger",
                "name": "Sväng höger in på {way_name}",
                "destination": "Sväng höger mot {destination}"
            },
            "straight": {
                "default": "Kör rakt fram",
                "name": "Kör rakt fram in på {way_name}",
                "destination": "Kör rakt fram mot {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Sväng {modifier}",
                "name": "Sväng {modifier} in på {way_name}",
                "destination": "Sväng {modifier} mot {destination}"
            },
            "left": {
                "default": "Sväng vänster",
                "name": "Sväng vänster in på {way_name}",
                "destination": "Sväng vänster mot {destination}"
            },
            "right": {
                "default": "Sväng höger",
                "name": "Sväng höger in på {way_name}",
                "destination": "Sväng höger mot {destination}"
            },
            "straight": {
                "default": "Kör rakt fram",
                "name": "Kör rakt fram in på {way_name}",
                "destination": "Kör rakt fram mot {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Sväng {modifier}",
                "name": "Sväng {modifier} in på {way_name}",
                "destination": "Sväng {modifier} mot {destination}"
            },
            "left": {
                "default": "Sväng vänster",
                "name": "Sväng vänster in på {way_name}",
                "destination": "Sväng vänster mot {destination}"
            },
            "right": {
                "default": "Sväng höger",
                "name": "Sväng höger in på {way_name}",
                "destination": "Sväng höger mot {destination}"
            },
            "straight": {
                "default": "Kör rakt fram",
                "name": "Kör rakt fram in på {way_name}",
                "destination": "Kör rakt fram mot {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Fortsätt rakt fram"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],20:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "birinci",
                "2": "ikinci",
                "3": "üçüncü",
                "4": "dördüncü",
                "5": "beşinci",
                "6": "altıncı",
                "7": "yedinci",
                "8": "sekizinci",
                "9": "dokuzuncu",
                "10": "onuncu"
            },
            "direction": {
                "north": "kuzey",
                "northeast": "kuzeydoğu",
                "east": "doğu",
                "southeast": "güneydoğu",
                "south": "güney",
                "southwest": "güneybatı",
                "west": "batı",
                "northwest": "kuzeybatı"
            },
            "modifier": {
                "left": "sol",
                "right": "sağ",
                "sharp left": "keskin sol",
                "sharp right": "keskin sağ",
                "slight left": "hafif sol",
                "slight right": "hafif sağ",
                "straight": "düz",
                "uturn": "U dönüşü"
            },
            "lanes": {
                "xo": "Sağda kalın",
                "ox": "Solda kalın",
                "xox": "Ortada kalın",
                "oxo": "Solda veya sağda kalın"
            }
        },
        "modes": {
            "ferry": {
                "default": "Vapur kullan",
                "name": "{way_name} vapurunu kullan",
                "destination": "{destination} istikametine giden vapuru kullan"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} ve {distance} sonra {instruction_two}",
            "two linked": "{instruction_one} ve sonra {instruction_two}",
            "one in distance": "{distance} sonra, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "{nth} hedefinize ulaştınız"
            },
            "left": {
                "default": "{nth} hedefinize ulaştınız, hedefiniz solunuzdadır"
            },
            "right": {
                "default": "{nth} hedefinize ulaştınız, hedefiniz sağınızdadır"
            },
            "sharp left": {
                "default": "{nth} hedefinize ulaştınız, hedefiniz solunuzdadır"
            },
            "sharp right": {
                "default": "{nth} hedefinize ulaştınız, hedefiniz sağınızdadır"
            },
            "slight right": {
                "default": "{nth} hedefinize ulaştınız, hedefiniz sağınızdadır"
            },
            "slight left": {
                "default": "{nth} hedefinize ulaştınız, hedefiniz solunuzdadır"
            },
            "straight": {
                "default": "{nth} hedefinize ulaştınız, hedefiniz karşınızdadır"
            }
        },
        "continue": {
            "default": {
                "default": "{modifier} yöne dön",
                "name": "{way_name} üzerinde kalmak için {modifier} yöne dön",
                "destination": "{destination} istikametinde {modifier} yöne dön",
                "exit": "{way_name} üzerinde {modifier} yöne dön"
            },
            "straight": {
                "default": "Düz devam edin",
                "name": "{way_name} üzerinde kalmak için düz devam et",
                "destination": "{destination} istikametinde devam et",
                "distance": "{distance} boyunca düz devam et",
                "namedistance": "{distance} boyunca {way_name} üzerinde devam et"
            },
            "sharp left": {
                "default": "Sola keskin dönüş yap",
                "name": "{way_name} üzerinde kalmak için sola keskin dönüş yap",
                "destination": "{destination} istikametinde sola keskin dönüş yap"
            },
            "sharp right": {
                "default": "Sağa keskin dönüş yap",
                "name": "{way_name} üzerinde kalmak için sağa keskin dönüş yap",
                "destination": "{destination} istikametinde sağa keskin dönüş yap"
            },
            "slight left": {
                "default": "Sola hafif dönüş yap",
                "name": "{way_name} üzerinde kalmak için sola hafif dönüş yap",
                "destination": "{destination} istikametinde sola hafif dönüş yap"
            },
            "slight right": {
                "default": "Sağa hafif dönüş yap",
                "name": "{way_name} üzerinde kalmak için sağa hafif dönüş yap",
                "destination": "{destination} istikametinde sağa hafif dönüş yap"
            },
            "uturn": {
                "default": "U dönüşü yapın",
                "name": "Bir U-dönüşü yap ve {way_name} devam et",
                "destination": "{destination} istikametinde bir U-dönüşü yap"
            }
        },
        "depart": {
            "default": {
                "default": "{direction} tarafına yönelin",
                "name": "{way_name} üzerinde {direction} yöne git",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "{modifier} tarafa dönün",
                "name": "{way_name} üzerinde {modifier} yöne dön",
                "destination": "{destination} istikametinde {modifier} yöne dön"
            },
            "straight": {
                "default": "Düz devam edin",
                "name": "{way_name} üzerinde düz devam et",
                "destination": "{destination} istikametinde düz devam et"
            },
            "uturn": {
                "default": "Yolun sonunda U dönüşü yapın",
                "name": "Yolun sonunda {way_name} üzerinde bir U-dönüşü yap",
                "destination": "Yolun sonunda {destination} istikametinde bir U-dönüşü yap"
            }
        },
        "fork": {
            "default": {
                "default": "Yol ayrımında {modifier} yönde kal",
                "name": "{way_name} üzerindeki yol ayrımında {modifier} yönde kal",
                "destination": "{destination} istikametindeki yol ayrımında {modifier} yönde kal"
            },
            "slight left": {
                "default": "Çatalın solundan devam edin",
                "name": "Çatalın solundan {way_name} yoluna doğru ",
                "destination": "{destination} istikametindeki yol ayrımında solda kal"
            },
            "slight right": {
                "default": "Çatalın sağından devam edin",
                "name": "{way_name} üzerindeki yol ayrımında sağda kal",
                "destination": "{destination} istikametindeki yol ayrımında sağda kal"
            },
            "sharp left": {
                "default": "Çatalda keskin sola dönün",
                "name": "{way_name} üzerindeki yol ayrımında sola keskin dönüş yap",
                "destination": "{destination} istikametindeki yol ayrımında sola keskin dönüş yap"
            },
            "sharp right": {
                "default": "Çatalda keskin sağa dönün",
                "name": "{way_name} üzerindeki yol ayrımında sağa keskin dönüş yap",
                "destination": "{destination} istikametindeki yol ayrımında sola keskin dönüş yap"
            },
            "uturn": {
                "default": "U dönüşü yapın",
                "name": "{way_name} yoluna U dönüşü yapın",
                "destination": "{destination} istikametinde bir U-dönüşü yap"
            }
        },
        "merge": {
            "default": {
                "default": "{modifier} yöne gir",
                "name": "{way_name} üzerinde {modifier} yöne gir",
                "destination": "{destination} istikametinde {modifier} yöne gir"
            },
            "slight left": {
                "default": "Sola gir",
                "name": "{way_name} üzerinde sola gir",
                "destination": "{destination} istikametinde sola gir"
            },
            "slight right": {
                "default": "Sağa gir",
                "name": "{way_name} üzerinde sağa gir",
                "destination": "{destination} istikametinde sağa gir"
            },
            "sharp left": {
                "default": "Sola gir",
                "name": "{way_name} üzerinde sola gir",
                "destination": "{destination} istikametinde sola gir"
            },
            "sharp right": {
                "default": "Sağa gir",
                "name": "{way_name} üzerinde sağa gir",
                "destination": "{destination} istikametinde sağa gir"
            },
            "uturn": {
                "default": "U dönüşü yapın",
                "name": "{way_name} yoluna U dönüşü yapın",
                "destination": "{destination} istikametinde bir U-dönüşü yap"
            }
        },
        "new name": {
            "default": {
                "default": "{modifier} yönde devam et",
                "name": "{way_name} üzerinde {modifier} yönde devam et",
                "destination": "{destination} istikametinde {modifier} yönde devam et"
            },
            "straight": {
                "default": "Düz devam et",
                "name": "{way_name} üzerinde devam et",
                "destination": "{destination} istikametinde devam et"
            },
            "sharp left": {
                "default": "Sola keskin dönüş yapın",
                "name": "{way_name} yoluna doğru sola keskin dönüş yapın",
                "destination": "{destination} istikametinde sola keskin dönüş yap"
            },
            "sharp right": {
                "default": "Sağa keskin dönüş yapın",
                "name": "{way_name} yoluna doğru sağa keskin dönüş yapın",
                "destination": "{destination} istikametinde sağa keskin dönüş yap"
            },
            "slight left": {
                "default": "Hafif soldan devam edin",
                "name": "{way_name} üzerinde hafif solda devam et",
                "destination": "{destination} istikametinde hafif solda devam et"
            },
            "slight right": {
                "default": "Hafif sağdan devam edin",
                "name": "{way_name} üzerinde hafif sağda devam et",
                "destination": "{destination} istikametinde hafif sağda devam et"
            },
            "uturn": {
                "default": "U dönüşü yapın",
                "name": "{way_name} yoluna U dönüşü yapın",
                "destination": "{destination} istikametinde bir U-dönüşü yap"
            }
        },
        "notification": {
            "default": {
                "default": "{modifier} yönde devam et",
                "name": "{way_name} üzerinde {modifier} yönde devam et",
                "destination": "{destination} istikametinde {modifier} yönde devam et"
            },
            "uturn": {
                "default": "U dönüşü yapın",
                "name": "{way_name} yoluna U dönüşü yapın",
                "destination": "{destination} istikametinde bir U-dönüşü yap"
            }
        },
        "off ramp": {
            "default": {
                "default": "Bağlantı yoluna geç",
                "name": "{way_name} üzerindeki bağlantı yoluna geç",
                "destination": "{destination} istikametine giden bağlantı yoluna geç",
                "exit": "{exit} çıkış yoluna geç",
                "exit_destination": "{destination} istikametindeki {exit} çıkış yoluna geç"
            },
            "left": {
                "default": "Soldaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sol bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sol bağlantı yoluna geç",
                "exit": "Soldaki {exit} çıkış yoluna geç",
                "exit_destination": "{destination} istikametindeki {exit} sol çıkış yoluna geç"
            },
            "right": {
                "default": "Sağdaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sağ bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sağ bağlantı yoluna geç",
                "exit": "Sağdaki {exit} çıkış yoluna geç",
                "exit_destination": "{destination} istikametindeki {exit} sağ çıkış yoluna geç"
            },
            "sharp left": {
                "default": "Soldaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sol bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sol bağlantı yoluna geç",
                "exit": "Soldaki {exit} çıkış yoluna geç",
                "exit_destination": "{destination} istikametindeki {exit} sol çıkış yoluna geç"
            },
            "sharp right": {
                "default": "Sağdaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sağ bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sağ bağlantı yoluna geç",
                "exit": "Sağdaki {exit} çıkış yoluna geç",
                "exit_destination": "{destination} istikametindeki {exit} sağ çıkış yoluna geç"
            },
            "slight left": {
                "default": "Soldaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sol bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sol bağlantı yoluna geç",
                "exit": "Soldaki {exit} çıkış yoluna geç",
                "exit_destination": "{destination} istikametindeki {exit} sol çıkış yoluna geç"
            },
            "slight right": {
                "default": "Sağdaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sağ bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sağ bağlantı yoluna geç",
                "exit": "Sağdaki {exit} çıkış yoluna geç",
                "exit_destination": "{destination} istikametindeki {exit} sağ çıkış yoluna geç"
            }
        },
        "on ramp": {
            "default": {
                "default": "Bağlantı yoluna geç",
                "name": "{way_name} üzerindeki bağlantı yoluna geç",
                "destination": "{destination} istikametine giden bağlantı yoluna geç"
            },
            "left": {
                "default": "Soldaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sol bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sol bağlantı yoluna geç"
            },
            "right": {
                "default": "Sağdaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sağ bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sağ bağlantı yoluna geç"
            },
            "sharp left": {
                "default": "Soldaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sol bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sol bağlantı yoluna geç"
            },
            "sharp right": {
                "default": "Sağdaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sağ bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sağ bağlantı yoluna geç"
            },
            "slight left": {
                "default": "Soldaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sol bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sol bağlantı yoluna geç"
            },
            "slight right": {
                "default": "Sağdaki bağlantı yoluna geç",
                "name": "{way_name} üzerindeki sağ bağlantı yoluna geç",
                "destination": "{destination} istikametine giden sağ bağlantı yoluna geç"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Dönel kavşağa gir",
                    "name": "Dönel kavşağa gir ve {way_name} üzerinde çık",
                    "destination": "Dönel kavşağa gir ve {destination} istikametinde çık"
                },
                "name": {
                    "default": "{rotary_name} dönel kavşağa gir",
                    "name": "{rotary_name} dönel kavşağa gir ve {way_name} üzerinde çık",
                    "destination": "{rotary_name} dönel kavşağa gir ve {destination} istikametinde çık"
                },
                "exit": {
                    "default": "Dönel kavşağa gir ve {exit_number} numaralı çıkışa gir",
                    "name": "Dönel kavşağa gir ve {way_name} üzerindeki {exit_number} numaralı çıkışa gir",
                    "destination": "Dönel kavşağa gir ve {destination} istikametindeki {exit_number} numaralı çıkışa gir"
                },
                "name_exit": {
                    "default": "{rotary_name} dönel kavşağa gir ve {exit_number} numaralı çıkışa gir",
                    "name": "{rotary_name} dönel kavşağa gir ve {way_name} üzerindeki {exit_number} numaralı çıkışa gir",
                    "destination": "{rotary_name} dönel kavşağa gir ve {destination} istikametindeki {exit_number} numaralı çıkışa gir"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Göbekli kavşağa gir ve {exit_number} numaralı çıkışa gir",
                    "name": "Göbekli kavşağa gir ve {way_name} üzerindeki {exit_number} numaralı çıkışa gir",
                    "destination": "Göbekli kavşağa gir ve {destination} istikametindeki {exit_number} numaralı çıkışa gir"
                },
                "default": {
                    "default": "Göbekli kavşağa gir",
                    "name": "Göbekli kavşağa gir ve {way_name} üzerinde çık",
                    "destination": "Göbekli kavşağa gir ve {destination} istikametinde çık"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Göbekli kavşakta {modifier} yöne dön",
                "name": "{way_name} üzerindeki göbekli kavşakta {modifier} yöne dön",
                "destination": "{destination} üzerindeki göbekli kavşakta {modifier} yöne dön"
            },
            "left": {
                "default": "Göbekli kavşakta sola dön",
                "name": "Göbekli kavşakta {way_name} üzerinde sola dön",
                "destination": "Göbekli kavşakta {destination} istikametinde sola dön"
            },
            "right": {
                "default": "Göbekli kavşakta sağa dön",
                "name": "Göbekli kavşakta {way_name} üzerinde sağa dön",
                "destination": "Göbekli kavşakta {destination} üzerinde sağa dön"
            },
            "straight": {
                "default": "Göbekli kavşakta düz devam et",
                "name": "Göbekli kavşakta {way_name} üzerinde düz devam et",
                "destination": "Göbekli kavşakta {destination} istikametinde düz devam et"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "{modifier} yöne dön",
                "name": "{way_name} üzerinde {modifier} yöne dön",
                "destination": "{destination} istikametinde {modifier} yöne dön"
            },
            "left": {
                "default": "Sola dön",
                "name": "{way_name} üzerinde sola dön",
                "destination": "{destination} istikametinde sola dön"
            },
            "right": {
                "default": "Sağa dön",
                "name": "{way_name} üzerinde sağa dön",
                "destination": "{destination} istikametinde sağa dön"
            },
            "straight": {
                "default": "Düz git",
                "name": "{way_name} üzerinde düz git",
                "destination": "{destination} istikametinde düz git"
            }
        },
        "exit rotary": {
            "default": {
                "default": "{modifier} yöne dön",
                "name": "{way_name} üzerinde {modifier} yöne dön",
                "destination": "{destination} istikametinde {modifier} yöne dön"
            },
            "left": {
                "default": "Sola dön",
                "name": "{way_name} üzerinde sola dön",
                "destination": "{destination} istikametinde sola dön"
            },
            "right": {
                "default": "Sağa dön",
                "name": "{way_name} üzerinde sağa dön",
                "destination": "{destination} istikametinde sağa dön"
            },
            "straight": {
                "default": "Düz git",
                "name": "{way_name} üzerinde düz git",
                "destination": "{destination} istikametinde düz git"
            }
        },
        "turn": {
            "default": {
                "default": "{modifier} yöne dön",
                "name": "{way_name} üzerinde {modifier} yöne dön",
                "destination": "{destination} istikametinde {modifier} yöne dön"
            },
            "left": {
                "default": "Sola dönün",
                "name": "{way_name} üzerinde sola dön",
                "destination": "{destination} istikametinde sola dön"
            },
            "right": {
                "default": "Sağa dönün",
                "name": "{way_name} üzerinde sağa dön",
                "destination": "{destination} istikametinde sağa dön"
            },
            "straight": {
                "default": "Düz git",
                "name": "{way_name} üzerinde düz git",
                "destination": "{destination} istikametinde düz git"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Düz devam edin"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],21:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "1й",
                "2": "2й",
                "3": "3й",
                "4": "4й",
                "5": "5й",
                "6": "6й",
                "7": "7й",
                "8": "8й",
                "9": "9й",
                "10": "10й"
            },
            "direction": {
                "north": "північ",
                "northeast": "північний схід",
                "east": "схід",
                "southeast": "південний схід",
                "south": "південь",
                "southwest": "південний захід",
                "west": "захід",
                "northwest": "північний захід"
            },
            "modifier": {
                "left": "ліворуч",
                "right": "праворуч",
                "sharp left": "різко ліворуч",
                "sharp right": "різко праворуч",
                "slight left": "плавно ліворуч",
                "slight right": "плавно праворуч",
                "straight": "прямо",
                "uturn": "розворот"
            },
            "lanes": {
                "xo": "Тримайтесь праворуч",
                "ox": "Тримайтесь ліворуч",
                "xox": "Тримайтесь в середині",
                "oxo": "Тримайтесь праворуч або ліворуч"
            }
        },
        "modes": {
            "ferry": {
                "default": "Скористайтесь поромом",
                "name": "Скористайтесь поромом {way_name}",
                "destination": "Скористайтесь поромом у напрямку {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} then in {distance} {instruction_two}",
            "two linked": "{instruction_one} then {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Ви прибули у ваш {nth} пункт призначення"
            },
            "left": {
                "default": "Ви прибули у ваш {nth} пункт призначення, він – ліворуч"
            },
            "right": {
                "default": "Ви прибули у ваш {nth} пункт призначення, він – праворуч"
            },
            "sharp left": {
                "default": "Ви прибули у ваш {nth} пункт призначення, він – ліворуч"
            },
            "sharp right": {
                "default": "Ви прибули у ваш {nth} пункт призначення, він – праворуч"
            },
            "slight right": {
                "default": "Ви прибули у ваш {nth} пункт призначення, він – праворуч"
            },
            "slight left": {
                "default": "Ви прибули у ваш {nth} пункт призначення, він – ліворуч"
            },
            "straight": {
                "default": "Ви прибули у ваш {nth} пункт призначення, він – прямо перед вами"
            }
        },
        "continue": {
            "default": {
                "default": "Поверніть {modifier}",
                "name": "Рухайтесь {modifier} на {way_name}",
                "destination": "Поверніть {modifier} у напрямку {destination}",
                "exit": "Поверніть {modifier} на {way_name}"
            },
            "straight": {
                "default": "Продовжуйте рух прямо",
                "name": "Рухайтесь по {way_name}",
                "destination": "Рухайтесь у напрямку {destination}",
                "distance": "Continue straight for {distance}",
                "namedistance": "Continue on {way_name} for {distance}"
            },
            "sharp left": {
                "default": "Прийміть різко ліворуч",
                "name": "Make a sharp left to stay on {way_name}",
                "destination": "Прийміть різко ліворуч у напрямку {destination}"
            },
            "sharp right": {
                "default": "Прийміть різко праворуч",
                "name": "Make a sharp right to stay on {way_name}",
                "destination": "Прийміть різко праворуч у напрямку {destination}"
            },
            "slight left": {
                "default": "Прийміть різко ліворуч",
                "name": "Рухайтесь плавно ліворуч на {way_name}",
                "destination": "Рухайтесь плавно ліворуч у напрямку {destination}"
            },
            "slight right": {
                "default": "Прийміть плавно праворуч",
                "name": "Рухайтесь плавно праворуч на {way_name}",
                "destination": "Рухайтесь плавно праворуч у напрямку {destination}"
            },
            "uturn": {
                "default": "Здійсніть розворот",
                "name": "Здійсніть розворот на {way_name}",
                "destination": "Здійсніть розворот у напрямку {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Прямуйте на {direction}",
                "name": "Прямуйте на {direction} по {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Поверніть {modifier}",
                "name": "Поверніть {modifier} на {way_name}",
                "destination": "Поверніть {modifier} у напрямку {destination}"
            },
            "straight": {
                "default": "Продовжуйте рух прямо",
                "name": "Продовжуйте рух прямо по {way_name}",
                "destination": "Продовжуйте рух прямо у напрямку {destination}"
            },
            "uturn": {
                "default": "Здійсніть розворот в кінці дороги",
                "name": "Здійсніть розворот на {way_name} в кінці дороги",
                "destination": "Здійсніть розворот у напрямку {destination} в кінці дороги"
            }
        },
        "fork": {
            "default": {
                "default": "На роздоріжжі тримайтеся {modifier}",
                "name": "На роздоріжжі тримайтеся {modifier} і виїжджайте на {way_name}",
                "destination": "На роздоріжжі тримайтеся {modifier} у напрямку {destination}"
            },
            "slight left": {
                "default": "На роздоріжжі тримайтеся ліворуч",
                "name": "На роздоріжжі тримайтеся ліворуч і виїжджайте на {way_name}",
                "destination": "На роздоріжжі тримайтеся ліворуч у напрямку {destination}"
            },
            "slight right": {
                "default": "На роздоріжжі тримайтеся праворуч",
                "name": "На роздоріжжі тримайтеся праворуч і виїжджайте на {way_name}",
                "destination": "На роздоріжжі тримайтеся праворуч у напрямку {destination}"
            },
            "sharp left": {
                "default": "На роздоріжжі різко поверніть ліворуч",
                "name": "На роздоріжжі різко поверніть ліворуч на {way_name}",
                "destination": "На роздоріжжі різко поверніть ліворуч в напрямку {destination}"
            },
            "sharp right": {
                "default": "На роздоріжжі різко поверніть праворуч",
                "name": "На роздоріжжі різко поверніть праворуч на {way_name}",
                "destination": "На роздоріжжі різко поверніть праворуч в напрямку {destination}"
            },
            "uturn": {
                "default": "Здійсніть розворот",
                "name": "Здійсніть розворот на {way_name}",
                "destination": "Здійсніть розворот у напрямку {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Приєднайтеся до потоку {modifier}",
                "name": "Приєднайтеся до потоку {modifier} на {way_name}",
                "destination": "Приєднайтеся до потоку {modifier} у напрямку {destination}"
            },
            "slight left": {
                "default": "Приєднайтеся до потоку ліворуч",
                "name": "Приєднайтеся до потоку ліворуч на {way_name}",
                "destination": "Приєднайтеся до потоку ліворуч у напрямку {destination}"
            },
            "slight right": {
                "default": "Приєднайтеся до потоку праворуч",
                "name": "Приєднайтеся до потоку праворуч на {way_name}",
                "destination": "Приєднайтеся до потоку праворуч у напрямку {destination}"
            },
            "sharp left": {
                "default": "Приєднайтеся до потоку ліворуч",
                "name": "Приєднайтеся до потоку ліворуч на {way_name}",
                "destination": "Приєднайтеся до потоку ліворуч у напрямку {destination}"
            },
            "sharp right": {
                "default": "Приєднайтеся до потоку праворуч",
                "name": "Приєднайтеся до потоку праворуч на {way_name}",
                "destination": "Приєднайтеся до потоку праворуч у напрямку {destination}"
            },
            "uturn": {
                "default": "Здійсніть розворот",
                "name": "Здійсніть розворот на {way_name}",
                "destination": "Здійсніть розворот у напрямку {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Рухайтесь {modifier}",
                "name": "Рухайтесь {modifier} на {way_name}",
                "destination": "Рухайтесь {modifier} у напрямку {destination}"
            },
            "straight": {
                "default": "Продовжуйте рух прямо",
                "name": "Продовжуйте рух по {way_name}",
                "destination": "Продовжуйте рух у напрямку {destination}"
            },
            "sharp left": {
                "default": "Прийміть різко ліворуч",
                "name": "Прийміть різко ліворуч на {way_name}",
                "destination": "Прийміть різко ліворуч у напрямку {destination}"
            },
            "sharp right": {
                "default": "Прийміть різко праворуч",
                "name": "Прийміть різко праворуч на {way_name}",
                "destination": "Прийміть різко праворуч у напрямку {destination}"
            },
            "slight left": {
                "default": "Прийміть плавно ліворуч",
                "name": "Рухайтесь плавно ліворуч на {way_name}",
                "destination": "Рухайтесь плавно ліворуч у напрямку {destination}"
            },
            "slight right": {
                "default": "Прийміть плавно праворуч",
                "name": "Рухайтесь плавно праворуч на {way_name}",
                "destination": "Рухайтесь плавно праворуч у напрямку {destination}"
            },
            "uturn": {
                "default": "Здійсніть розворот",
                "name": "Здійсніть розворот на {way_name}",
                "destination": "Здійсніть розворот у напрямку {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Рухайтесь {modifier}",
                "name": "Рухайтесь {modifier} на {way_name}",
                "destination": "Рухайтесь {modifier} у напрямку {destination}"
            },
            "uturn": {
                "default": "Здійсніть розворот",
                "name": "Здійсніть розворот на {way_name}",
                "destination": "Здійсніть розворот у напрямку {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Рухайтесь на зʼїзд",
                "name": "Рухайтесь на зʼїзд на {way_name}",
                "destination": "Рухайтесь на зʼїзд у напрямку {destination}",
                "exit": "Оберіть з'їзд {exit}",
                "exit_destination": "Оберіть з'їзд {exit} у напрямку {destination}"
            },
            "left": {
                "default": "Рухайтесь на зʼїзд ліворуч",
                "name": "Рухайтесь на зʼїзд ліворуч на {way_name}",
                "destination": "Рухайтесь на зʼїзд ліворуч у напрямку {destination}",
                "exit": "Оберіть з'їзд {exit} ліворуч",
                "exit_destination": "Оберіть з'їзд {exit} ліворуч у напрямку {destination}"
            },
            "right": {
                "default": "Рухайтесь на зʼїзд праворуч",
                "name": "Рухайтесь на зʼїзд праворуч на {way_name}",
                "destination": "Рухайтесь на зʼїзд праворуч у напрямку {destination}",
                "exit": "Оберіть з'їзд {exit} праворуч",
                "exit_destination": "Оберіть з'їзд {exit} праворуч у напрямку {destination}"
            },
            "sharp left": {
                "default": "Рухайтесь на зʼїзд ліворуч",
                "name": "Рухайтесь на зʼїзд ліворуч на {way_name}",
                "destination": "Рухайтесь на зʼїзд ліворуч у напрямку {destination}",
                "exit": "Оберіть з'їзд {exit} ліворуч",
                "exit_destination": "Оберіть з'їзд {exit} ліворуч у напрямку {destination}"
            },
            "sharp right": {
                "default": "Рухайтесь на зʼїзд праворуч",
                "name": "Рухайтесь на зʼїзд праворуч на {way_name}",
                "destination": "Рухайтесь на зʼїзд праворуч у напрямку {destination}",
                "exit": "Оберіть з'їзд {exit} праворуч",
                "exit_destination": "Оберіть з'їзд {exit} праворуч у напрямку {destination}"
            },
            "slight left": {
                "default": "Рухайтесь на зʼїзд ліворуч",
                "name": "Рухайтесь на зʼїзд ліворуч на {way_name}",
                "destination": "Рухайтесь на зʼїзд ліворуч у напрямку {destination}",
                "exit": "Оберіть з'їзд {exit} ліворуч",
                "exit_destination": "Оберіть з'їзд {exit} ліворуч у напрямку {destination}"
            },
            "slight right": {
                "default": "Рухайтесь на зʼїзд праворуч",
                "name": "Рухайтесь на зʼїзд праворуч на {way_name}",
                "destination": "Рухайтесь на зʼїзд праворуч у напрямку {destination}",
                "exit": "Оберіть з'їзд {exit} праворуч",
                "exit_destination": "Оберіть з'їзд {exit} праворуч у напрямку {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Рухайтесь на вʼїзд",
                "name": "Рухайтесь на вʼїзд на {way_name}",
                "destination": "Рухайтесь на вʼїзд у напрямку {destination}"
            },
            "left": {
                "default": "Рухайтесь на вʼїзд ліворуч",
                "name": "Рухайтесь на вʼїзд ліворуч на {way_name}",
                "destination": "Рухайтесь на вʼїзд ліворуч у напрямку {destination}"
            },
            "right": {
                "default": "Рухайтесь на вʼїзд праворуч",
                "name": "Рухайтесь на вʼїзд праворуч на {way_name}",
                "destination": "Рухайтесь на вʼїзд праворуч у напрямку {destination}"
            },
            "sharp left": {
                "default": "Рухайтесь на вʼїзд ліворуч",
                "name": "Рухайтесь на вʼїзд ліворуч на {way_name}",
                "destination": "Рухайтесь на вʼїзд ліворуч у напрямку {destination}"
            },
            "sharp right": {
                "default": "Рухайтесь на вʼїзд праворуч",
                "name": "Рухайтесь на вʼїзд праворуч на {way_name}",
                "destination": "Рухайтесь на вʼїзд праворуч у напрямку {destination}"
            },
            "slight left": {
                "default": "Рухайтесь на вʼїзд ліворуч",
                "name": "Рухайтесь на вʼїзд ліворуч на {way_name}",
                "destination": "Рухайтесь на вʼїзд ліворуч у напрямку {destination}"
            },
            "slight right": {
                "default": "Рухайтесь на вʼїзд праворуч",
                "name": "Рухайтесь на вʼїзд праворуч на {way_name}",
                "destination": "Рухайтесь на вʼїзд праворуч у напрямку {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Рухайтесь по колу",
                    "name": "Рухайтесь по колу до {way_name}",
                    "destination": "Рухайтесь по колу в напрямку {destination}"
                },
                "name": {
                    "default": "Рухайтесь по {rotary_name}",
                    "name": "Рухайтесь по {rotary_name} та поверніть на {way_name}",
                    "destination": "Рухайтесь по {rotary_name} та поверніть в напрямку {destination}"
                },
                "exit": {
                    "default": "Рухайтесь по колу та повереніть у {exit_number} з'їзд",
                    "name": "Рухайтесь по колу та поверніть у {exit_number} з'їзд на {way_name}",
                    "destination": "Рухайтесь по колу та поверніть у {exit_number} з'їзд у напрямку {destination}"
                },
                "name_exit": {
                    "default": "Рухайтесь по {rotary_name} та поверніть у {exit_number} з'їзд",
                    "name": "Рухайтесь по {rotary_name} та поверніть у {exit_number} з'їзд на {way_name}",
                    "destination": "Рухайтесь по {rotary_name} та поверніть у {exit_number} з'їзд в напрямку {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Рухайтесь по кільцю та повереніть у {exit_number} з'їзд",
                    "name": "Рухайтесь по кільцю та поверніть у {exit_number} з'їзд на {way_name}",
                    "destination": "Рухайтесь по кільцю та поверніть у {exit_number} з'їзд у напрямку {destination}"
                },
                "default": {
                    "default": "Рухайтесь по кільцю",
                    "name": "Рухайтесь по кільцю до {way_name}",
                    "destination": "Рухайтесь по кільцю в напрямку {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "На кільці {modifier}",
                "name": "На кільці {modifier} на {way_name}",
                "destination": "На кільці {modifier} в напрямку {destination}"
            },
            "left": {
                "default": "На кільці поверніть ліворуч",
                "name": "На кільці поверніть ліворуч на {way_name}",
                "destination": "На кільці поверніть ліворуч в напрямку {destination}"
            },
            "right": {
                "default": "На кільці поверніть праворуч",
                "name": "На кільці поверніть праворуч на {way_name}",
                "destination": "На кільці поверніть праворуч в напрямку {destination}"
            },
            "straight": {
                "default": "На кільці продовжуйте рухатись прямо",
                "name": "На кільці продовжуйте рухатись прямо на {way_name}",
                "destination": "На кільці продовжуйте рухатись прямо в напрямку {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Рухайтесь {modifier}",
                "name": "Рухайтесь {modifier} на {way_name}",
                "destination": "Рухайтесь {modifier} в напрямку {destination}"
            },
            "left": {
                "default": "Поверніть ліворуч",
                "name": "Поверніть ліворуч на {way_name}",
                "destination": "Поверніть ліворуч у напрямку {destination}"
            },
            "right": {
                "default": "Поверніть праворуч",
                "name": "Поверніть праворуч на {way_name}",
                "destination": "Поверніть праворуч у напрямку {destination}"
            },
            "straight": {
                "default": "Рухайтесь прямо",
                "name": "Рухайтесь прямо по {way_name}",
                "destination": "Рухайтесь прямо у напрямку {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Рухайтесь {modifier}",
                "name": "Рухайтесь {modifier} на {way_name}",
                "destination": "Рухайтесь {modifier} в напрямку {destination}"
            },
            "left": {
                "default": "Поверніть ліворуч",
                "name": "Поверніть ліворуч на {way_name}",
                "destination": "Поверніть ліворуч у напрямку {destination}"
            },
            "right": {
                "default": "Поверніть праворуч",
                "name": "Поверніть праворуч на {way_name}",
                "destination": "Поверніть праворуч у напрямку {destination}"
            },
            "straight": {
                "default": "Рухайтесь прямо",
                "name": "Рухайтесь прямо по {way_name}",
                "destination": "Рухайтесь прямо у напрямку {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Рухайтесь {modifier}",
                "name": "Рухайтесь {modifier} на {way_name}",
                "destination": "Рухайтесь {modifier} в напрямку {destination}"
            },
            "left": {
                "default": "Поверніть ліворуч",
                "name": "Поверніть ліворуч на {way_name}",
                "destination": "Поверніть ліворуч у напрямку {destination}"
            },
            "right": {
                "default": "Поверніть праворуч",
                "name": "Поверніть праворуч на {way_name}",
                "destination": "Поверніть праворуч у напрямку {destination}"
            },
            "straight": {
                "default": "Рухайтесь прямо",
                "name": "Рухайтесь прямо по {way_name}",
                "destination": "Рухайтесь прямо у напрямку {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Продовжуйте рух прямо"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],22:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": true
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "đầu tiên",
                "2": "thứ 2",
                "3": "thứ 3",
                "4": "thứ 4",
                "5": "thứ 5",
                "6": "thú 6",
                "7": "thứ 7",
                "8": "thứ 8",
                "9": "thứ 9",
                "10": "thứ 10"
            },
            "direction": {
                "north": "bắc",
                "northeast": "đông bắc",
                "east": "đông",
                "southeast": "đông nam",
                "south": "nam",
                "southwest": "tây nam",
                "west": "tây",
                "northwest": "tây bắc"
            },
            "modifier": {
                "left": "trái",
                "right": "phải",
                "sharp left": "trái gắt",
                "sharp right": "phải gắt",
                "slight left": "trái nghiêng",
                "slight right": "phải nghiêng",
                "straight": "thẳng",
                "uturn": "ngược"
            },
            "lanes": {
                "xo": "Đi bên phải",
                "ox": "Đi bên trái",
                "xox": "Đi vào giữa",
                "oxo": "Đi bên trái hay bên phải"
            }
        },
        "modes": {
            "ferry": {
                "default": "Lên phà",
                "name": "Lên phà {way_name}",
                "destination": "Lên phà đi {destination}"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one}, rồi {distance} nữa thì {instruction_two}",
            "two linked": "{instruction_one}, rồi {instruction_two}",
            "one in distance": "{distance} nữa thì {instruction_one}",
            "name and ref": "{name} ({ref})"
        },
        "arrive": {
            "default": {
                "default": "Đến nơi {nth}"
            },
            "left": {
                "default": "Đến nơi {nth} ở bên trái"
            },
            "right": {
                "default": "Đến nơi {nth} ở bên phải"
            },
            "sharp left": {
                "default": "Đến nơi {nth} ở bên trái"
            },
            "sharp right": {
                "default": "Đến nơi {nth} ở bên phải"
            },
            "slight right": {
                "default": "Đến nơi {nth} ở bên phải"
            },
            "slight left": {
                "default": "Đến nơi {nth} ở bên trái"
            },
            "straight": {
                "default": "Đến nơi {nth} ở trước mặt"
            }
        },
        "continue": {
            "default": {
                "default": "Quẹo {modifier}",
                "name": "Quẹo {modifier} để chạy tiếp trên {way_name}",
                "destination": "Quẹo {modifier} đến {destination}",
                "exit": "Quẹo {modifier} vào {way_name}"
            },
            "straight": {
                "default": "Chạy thẳng",
                "name": "Chạy tiếp trên {way_name}",
                "destination": "Chạy tiếp đến {destination}",
                "distance": "Chạy thẳng cho {distance}",
                "namedistance": "Chạy tiếp trên {way_name} cho {distance}"
            },
            "sharp left": {
                "default": "Quẹo gắt bên trái",
                "name": "Quẹo gắt bên trái để chạy tiếp trên {way_name}",
                "destination": "Quẹo gắt bên trái đến {destination}"
            },
            "sharp right": {
                "default": "Quẹo gắt bên phải",
                "name": "Quẹo gắt bên phải để chạy tiếp trên {way_name}",
                "destination": "Quẹo gắt bên phải đến {destination}"
            },
            "slight left": {
                "default": "Nghiêng về bên trái",
                "name": "Nghiêng về bên trái để chạy tiếp trên {way_name}",
                "destination": "Nghiêng về bên trái đến {destination}"
            },
            "slight right": {
                "default": "Nghiêng về bên phải",
                "name": "Nghiêng về bên phải để chạy tiếp trên {way_name}",
                "destination": "Nghiêng về bên phải đến {destination}"
            },
            "uturn": {
                "default": "Quẹo ngược lại",
                "name": "Quẹo ngược lại trên {way_name}",
                "destination": "Quẹo ngược đến {destination}"
            }
        },
        "depart": {
            "default": {
                "default": "Đi về hướng {direction}",
                "name": "Đi về hướng {direction} trên {way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "Quẹo {modifier}",
                "name": "Quẹo {modifier} vào {way_name}",
                "destination": "Quẹo {modifier} đến {destination}"
            },
            "straight": {
                "default": "Chạy thẳng",
                "name": "Chạy tiếp trên {way_name}",
                "destination": "Chạy tiếp đến {destination}"
            },
            "uturn": {
                "default": "Quẹo ngược lại tại cuối đường",
                "name": "Quẹo ngược vào {way_name} tại cuối đường",
                "destination": "Quẹo ngược đến {destination} tại cuối đường"
            }
        },
        "fork": {
            "default": {
                "default": "Đi bên {modifier} ở ngã ba",
                "name": "Đi bên {modifier} ở ngã ba vào {way_name}",
                "destination": "Đi bên {modifier} ở ngã ba đến {destination}"
            },
            "slight left": {
                "default": "Nghiêng về bên trái ở ngã ba",
                "name": "Nghiêng về bên trái ở ngã ba vào {way_name}",
                "destination": "Nghiêng về bên trái ở ngã ba đến {destination}"
            },
            "slight right": {
                "default": "Nghiêng về bên phải ở ngã ba",
                "name": "Nghiêng về bên phải ở ngã ba vào {way_name}",
                "destination": "Nghiêng về bên phải ở ngã ba đến {destination}"
            },
            "sharp left": {
                "default": "Quẹo gắt bên trái ở ngã ba",
                "name": "Quẹo gắt bên trái ở ngã ba vào {way_name}",
                "destination": "Quẹo gắt bên trái ở ngã ba đến {destination}"
            },
            "sharp right": {
                "default": "Quẹo gắt bên phải ở ngã ba",
                "name": "Quẹo gắt bên phải ở ngã ba vào {way_name}",
                "destination": "Quẹo gắt bên phải ở ngã ba đến {destination}"
            },
            "uturn": {
                "default": "Quẹo ngược lại",
                "name": "Quẹo ngược lại {way_name}",
                "destination": "Quẹo ngược lại đến {destination}"
            }
        },
        "merge": {
            "default": {
                "default": "Nhập sang {modifier}",
                "name": "Nhập sang {modifier} vào {way_name}",
                "destination": "Nhập sang {modifier} đến {destination}"
            },
            "slight left": {
                "default": "Nhập sang trái",
                "name": "Nhập sang trái vào {way_name}",
                "destination": "Nhập sang trái đến {destination}"
            },
            "slight right": {
                "default": "Nhập sang phải",
                "name": "Nhập sang phải vào {way_name}",
                "destination": "Nhập sang phải đến {destination}"
            },
            "sharp left": {
                "default": "Nhập sang trái",
                "name": "Nhập sang trái vào {way_name}",
                "destination": "Nhập sang trái đến {destination}"
            },
            "sharp right": {
                "default": "Nhập sang phải",
                "name": "Nhập sang phải vào {way_name}",
                "destination": "Nhập sang phải đến {destination}"
            },
            "uturn": {
                "default": "Quẹo ngược lại",
                "name": "Quẹo ngược lại {way_name}",
                "destination": "Quẹo ngược lại đến {destination}"
            }
        },
        "new name": {
            "default": {
                "default": "Chạy tiếp bên {modifier}",
                "name": "Chạy tiếp bên {modifier} trên {way_name}",
                "destination": "Chạy tiếp bên {modifier} đến {destination}"
            },
            "straight": {
                "default": "Chạy thẳng",
                "name": "Chạy tiếp trên {way_name}",
                "destination": "Chạy tiếp đến {destination}"
            },
            "sharp left": {
                "default": "Quẹo gắt bên trái",
                "name": "Quẹo gắt bên trái vào {way_name}",
                "destination": "Quẹo gắt bên trái đến {destination}"
            },
            "sharp right": {
                "default": "Quẹo gắt bên phải",
                "name": "Quẹo gắt bên phải vào {way_name}",
                "destination": "Quẹo gắt bên phải đến {destination}"
            },
            "slight left": {
                "default": "Nghiêng về bên trái",
                "name": "Nghiêng về bên trái vào {way_name}",
                "destination": "Nghiêng về bên trái đến {destination}"
            },
            "slight right": {
                "default": "Nghiêng về bên phải",
                "name": "Nghiêng về bên phải vào {way_name}",
                "destination": "Nghiêng về bên phải đến {destination}"
            },
            "uturn": {
                "default": "Quẹo ngược lại",
                "name": "Quẹo ngược lại {way_name}",
                "destination": "Quẹo ngược lại đến {destination}"
            }
        },
        "notification": {
            "default": {
                "default": "Chạy tiếp bên {modifier}",
                "name": "Chạy tiếp bên {modifier} trên {way_name}",
                "destination": "Chạy tiếp bên {modifier} đến {destination}"
            },
            "uturn": {
                "default": "Quẹo ngược lại",
                "name": "Quẹo ngược lại {way_name}",
                "destination": "Quẹo ngược lại đến {destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "Đi đường nhánh",
                "name": "Đi đường nhánh {way_name}",
                "destination": "Đi đường nhánh đến {destination}",
                "exit": "Đi theo lối ra {exit}",
                "exit_destination": "Đi theo lối ra {exit} về hướng {destination}"
            },
            "left": {
                "default": "Đi đường nhánh bên trái",
                "name": "Đi đường nhánh {way_name} bên trái",
                "destination": "Đi đường nhánh bên trái đến {destination}",
                "exit": "Đi theo lối ra {exit} bên trái",
                "exit_destination": "Đi theo lối ra {exit} bên trái về hướng {destination}"
            },
            "right": {
                "default": "Đi đường nhánh bên phải",
                "name": "Đi đường nhánh {way_name} bên phải",
                "destination": "Đi đường nhánh bên phải đến {destination}",
                "exit": "Đi theo lối ra {exit} bên phải",
                "exit_destination": "Đi theo lối ra {exit} bên phải về hướng {destination}"
            },
            "sharp left": {
                "default": "Đi đường nhánh bên trái",
                "name": "Đi đường nhánh {way_name} bên trái",
                "destination": "Đi đường nhánh bên trái đến {destination}",
                "exit": "Đi theo lối ra {exit} bên trái",
                "exit_destination": "Đi theo lối ra {exit} bên trái về hướng {destination}"
            },
            "sharp right": {
                "default": "Đi đường nhánh bên phải",
                "name": "Đi đường nhánh {way_name} bên phải",
                "destination": "Đi đường nhánh bên phải đến {destination}",
                "exit": "Đi theo lối ra {exit} bên phải",
                "exit_destination": "Đi theo lối ra {exit} bên phải về hướng {destination}"
            },
            "slight left": {
                "default": "Đi đường nhánh bên trái",
                "name": "Đi đường nhánh {way_name} bên trái",
                "destination": "Đi đường nhánh bên trái đến {destination}",
                "exit": "Đi theo lối ra {exit} bên trái",
                "exit_destination": "Đi theo lối ra {exit} bên trái về hướng {destination}"
            },
            "slight right": {
                "default": "Đi đường nhánh bên phải",
                "name": "Đi đường nhánh {way_name} bên phải",
                "destination": "Đi đường nhánh bên phải đến {destination}",
                "exit": "Đi theo lối ra {exit} bên phải",
                "exit_destination": "Đi theo lối ra {exit} bên phải về hướng {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "Đi đường nhánh",
                "name": "Đi đường nhánh {way_name}",
                "destination": "Đi đường nhánh đến {destination}"
            },
            "left": {
                "default": "Đi đường nhánh bên trái",
                "name": "Đi đường nhánh {way_name} bên trái",
                "destination": "Đi đường nhánh bên trái đến {destination}"
            },
            "right": {
                "default": "Đi đường nhánh bên phải",
                "name": "Đi đường nhánh {way_name} bên phải",
                "destination": "Đi đường nhánh bên phải đến {destination}"
            },
            "sharp left": {
                "default": "Đi đường nhánh bên trái",
                "name": "Đi đường nhánh {way_name} bên trái",
                "destination": "Đi đường nhánh bên trái đến {destination}"
            },
            "sharp right": {
                "default": "Đi đường nhánh bên phải",
                "name": "Đi đường nhánh {way_name} bên phải",
                "destination": "Đi đường nhánh bên phải đến {destination}"
            },
            "slight left": {
                "default": "Đi đường nhánh bên trái",
                "name": "Đi đường nhánh {way_name} bên trái",
                "destination": "Đi đường nhánh bên trái đến {destination}"
            },
            "slight right": {
                "default": "Đi đường nhánh bên phải",
                "name": "Đi đường nhánh {way_name} bên phải",
                "destination": "Đi đường nhánh bên phải đến {destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "Đi vào bùng binh",
                    "name": "Đi vào bùng binh và ra tại {way_name}",
                    "destination": "Vào bùng binh và ra để đi {destination}"
                },
                "name": {
                    "default": "Đi vào {rotary_name}",
                    "name": "Đi vào {rotary_name} và ra tại {way_name}",
                    "destination": "Đi và {rotary_name} và ra để đi {destination}"
                },
                "exit": {
                    "default": "Đi vào bùng binh và ra tại đường {exit_number}",
                    "name": "Đi vào bùng binh và ra tại đường {exit_number} tức {way_name}",
                    "destination": "Đi vào bùng binh và ra tại đường {exit_number} đến {destination}"
                },
                "name_exit": {
                    "default": "Đi vào {rotary_name} và ra tại đường {exit_number}",
                    "name": "Đi vào {rotary_name} và ra tại đường {exit_number} tức {way_name}",
                    "destination": "Đi vào {rotary_name} và ra tại đường {exit_number} đến {destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "Đi vào vòng xuyến và ra tại đường {exit_number}",
                    "name": "Đi vào vòng xuyến và ra tại đường {exit_number} tức {way_name}",
                    "destination": "Đi vào vòng xuyến và ra tại đường {exit_number} đến {destination}"
                },
                "default": {
                    "default": "Đi vào vòng xuyến",
                    "name": "Đi vào vòng xuyến và ra tại {way_name}",
                    "destination": "Đi vào vòng xuyến và ra để đi {destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "Đi bên {modifier} tại vòng xuyến",
                "name": "Đi bên {modifier} tại vòng xuyến để vào {way_name}",
                "destination": "Đi bên {modifier} tại vòng xuyến để đi {destination}"
            },
            "left": {
                "default": "Quẹo trái tại vòng xuyến",
                "name": "Quẹo trái tại vòng xuyến để vào {way_name}",
                "destination": "Quẹo trái tại vòng xuyến để đi {destination}"
            },
            "right": {
                "default": "Quẹo phải tại vòng xuyến",
                "name": "Quẹo phải ti vòng xuyến để vào {way_name}",
                "destination": "Quẹo phải tại vòng xuyến để đi {destination}"
            },
            "straight": {
                "default": "Chạy thẳng tại vòng xuyến",
                "name": "Chạy thẳng tại vòng xuyến để chạy tiếp trên {way_name}",
                "destination": "Chạy thẳng tại vòng xuyến để đi {destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "Quẹo {modifier}",
                "name": "Quẹo {modifier} vào {way_name}",
                "destination": "Quẹo {modifier} đến {destination}"
            },
            "left": {
                "default": "Quẹo trái",
                "name": "Quẹo trái vào {way_name}",
                "destination": "Quẹo trái đến {destination}"
            },
            "right": {
                "default": "Quẹo phải",
                "name": "Quẹo phải vào {way_name}",
                "destination": "Quẹo phải đến {destination}"
            },
            "straight": {
                "default": "Chạy thẳng",
                "name": "Chạy thẳng vào {way_name}",
                "destination": "Chạy thẳng đến {destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "Quẹo {modifier}",
                "name": "Quẹo {modifier} vào {way_name}",
                "destination": "Quẹo {modifier} đến {destination}"
            },
            "left": {
                "default": "Quẹo trái",
                "name": "Quẹo trái vào {way_name}",
                "destination": "Quẹo trái đến {destination}"
            },
            "right": {
                "default": "Quẹo phải",
                "name": "Quẹo phải vào {way_name}",
                "destination": "Quẹo phải đến {destination}"
            },
            "straight": {
                "default": "Chạy thẳng",
                "name": "Chạy thẳng vào {way_name}",
                "destination": "Chạy thẳng đến {destination}"
            }
        },
        "turn": {
            "default": {
                "default": "Quẹo {modifier}",
                "name": "Quẹo {modifier} vào {way_name}",
                "destination": "Quẹo {modifier} đến {destination}"
            },
            "left": {
                "default": "Quẹo trái",
                "name": "Quẹo trái vào {way_name}",
                "destination": "Quẹo trái đến {destination}"
            },
            "right": {
                "default": "Quẹo phải",
                "name": "Quẹo phải vào {way_name}",
                "destination": "Quẹo phải đến {destination}"
            },
            "straight": {
                "default": "Chạy thẳng",
                "name": "Chạy thẳng vào {way_name}",
                "destination": "Chạy thẳng đến {destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "Chạy thẳng"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}
},{}],23:[function(_dereq_,module,exports){
module.exports={
    "meta": {
        "capitalizeFirstLetter": false
    },
    "v5": {
        "constants": {
            "ordinalize": {
                "1": "第一",
                "2": "第二",
                "3": "第三",
                "4": "第四",
                "5": "第五",
                "6": "第六",
                "7": "第七",
                "8": "第八",
                "9": "第九",
                "10": "第十"
            },
            "direction": {
                "north": "北",
                "northeast": "东北",
                "east": "东",
                "southeast": "东南",
                "south": "南",
                "southwest": "西南",
                "west": "西",
                "northwest": "西北"
            },
            "modifier": {
                "left": "向左",
                "right": "向右",
                "sharp left": "向左",
                "sharp right": "向右",
                "slight left": "向左",
                "slight right": "向右",
                "straight": "直行",
                "uturn": "调头"
            },
            "lanes": {
                "xo": "靠右直行",
                "ox": "靠左直行",
                "xox": "保持在道路中间直行",
                "oxo": "保持在道路两侧直行"
            }
        },
        "modes": {
            "ferry": {
                "default": "乘坐轮渡",
                "name": "乘坐{way_name}轮渡",
                "destination": "乘坐开往{destination}的轮渡"
            }
        },
        "phrase": {
            "two linked by distance": "{instruction_one} then in {distance} {instruction_two}",
            "two linked": "{instruction_one} then {instruction_two}",
            "one in distance": "In {distance}, {instruction_one}",
            "name and ref": "{name}（{ref}）"
        },
        "arrive": {
            "default": {
                "default": "您已经到达您的{nth}个目的地"
            },
            "left": {
                "default": "您已经到达您的{nth}个目的地，在道路左侧"
            },
            "right": {
                "default": "您已经到达您的{nth}个目的地，在道路右侧"
            },
            "sharp left": {
                "default": "您已经到达您的{nth}个目的地，在道路左侧"
            },
            "sharp right": {
                "default": "您已经到达您的{nth}个目的地，在道路右侧"
            },
            "slight right": {
                "default": "您已经到达您的{nth}个目的地，在道路右侧"
            },
            "slight left": {
                "default": "您已经到达您的{nth}个目的地，在道路左侧"
            },
            "straight": {
                "default": "您已经到达您的{nth}个目的地，在您正前方"
            }
        },
        "continue": {
            "default": {
                "default": "{modifier}行驶",
                "name": "继续{modifier}，上{way_name}",
                "destination": "{modifier}行驶，前往{destination}",
                "exit": "{modifier}行驶，上{way_name}"
            },
            "sharp left": {
                "default": "Make a sharp left",
                "name": "Make a sharp left to stay on {way_name}",
                "destination": "Make a sharp left towards {destination}"
            },
            "sharp right": {
                "default": "Make a sharp right",
                "name": "Make a sharp right to stay on {way_name}",
                "destination": "Make a sharp right towards {destination}"
            },
            "uturn": {
                "default": "调头",
                "name": "调头上{way_name}",
                "destination": "调头后前往{destination}"
            }
        },
        "depart": {
            "default": {
                "default": "出发向{direction}",
                "name": "出发向{direction}，上{way_name}",
                "namedistance": "Head {direction} on {way_name} for {distance}"
            }
        },
        "end of road": {
            "default": {
                "default": "{modifier}行驶",
                "name": "{modifier}行驶，上{way_name}",
                "destination": "{modifier}行驶，前往{destination}"
            },
            "straight": {
                "default": "继续直行",
                "name": "继续直行，上{way_name}",
                "destination": "继续直行，前往{destination}"
            },
            "uturn": {
                "default": "在道路尽头调头",
                "name": "在道路尽头调头上{way_name}",
                "destination": "在道路尽头调头，前往{destination}"
            }
        },
        "fork": {
            "default": {
                "default": "在岔道保持{modifier}",
                "name": "在岔道保持{modifier}，上{way_name}",
                "destination": "在岔道保持{modifier}，前往{destination}"
            },
            "uturn": {
                "default": "调头",
                "name": "调头，上{way_name}",
                "destination": "调头，前往{destination}"
            }
        },
        "merge": {
            "default": {
                "default": "{modifier}并道",
                "name": "{modifier}并道，上{way_name}",
                "destination": "{modifier}并道，前往{destination}"
            },
            "uturn": {
                "default": "调头",
                "name": "调头，上{way_name}",
                "destination": "调头，前往{destination}"
            }
        },
        "new name": {
            "default": {
                "default": "继续{modifier}",
                "name": "继续{modifier}，上{way_name}",
                "destination": "继续{modifier}，前往{destination}"
            },
            "straight": {
                "default": "继续直行",
                "name": "Continue onto {way_name}",
                "destination": "Continue towards {destination}"
            },
            "uturn": {
                "default": "调头",
                "name": "调头，上{way_name}",
                "destination": "调头，前往{destination}"
            }
        },
        "notification": {
            "default": {
                "default": "继续{modifier}",
                "name": "继续{modifier}，上{way_name}",
                "destination": "继续{modifier}，前往{destination}"
            },
            "uturn": {
                "default": "调头",
                "name": "调头，上{way_name}",
                "destination": "调头，前往{destination}"
            }
        },
        "off ramp": {
            "default": {
                "default": "上匝道",
                "name": "通过匝道驶入{way_name}",
                "destination": "通过匝道前往{destination}",
                "exit": "Take exit {exit}",
                "exit_destination": "Take exit {exit} towards {destination}"
            },
            "left": {
                "default": "通过左边的匝道",
                "name": "通过左边的匝道驶入{way_name}",
                "destination": "通过左边的匝道前往{destination}",
                "exit": "Take exit {exit} on the left",
                "exit_destination": "Take exit {exit} on the left towards {destination}"
            },
            "right": {
                "default": "通过右边的匝道",
                "name": "通过右边的匝道驶入{way_name}",
                "destination": "通过右边的匝道前往{destination}",
                "exit": "Take exit {exit} on the right",
                "exit_destination": "Take exit {exit} on the right towards {destination}"
            }
        },
        "on ramp": {
            "default": {
                "default": "通过匝道",
                "name": "通过匝道驶入{way_name}",
                "destination": "通过匝道前往{destination}"
            },
            "left": {
                "default": "通过左边的匝道",
                "name": "通过左边的匝道驶入{way_name}",
                "destination": "通过左边的匝道前往{destination}"
            },
            "right": {
                "default": "通过右边的匝道",
                "name": "通过右边的匝道驶入{way_name}",
                "destination": "通过右边的匝道前往{destination}"
            }
        },
        "rotary": {
            "default": {
                "default": {
                    "default": "进入环岛",
                    "name": "通过环岛后驶入{way_name}",
                    "destination": "通过环岛前往{destination}"
                },
                "name": {
                    "default": "进入{rotary_name}环岛",
                    "name": "通过{rotary_name}环岛后驶入{way_name}",
                    "destination": "通过{rotary_name}环岛后前往{destination}"
                },
                "exit": {
                    "default": "进入环岛并从{exit_number}出口驶出",
                    "name": "进入环岛后从{exit_number}出口驶出进入{way_name}",
                    "destination": "进入环岛后从{exit_number}出口驶出前往{destination}"
                },
                "name_exit": {
                    "default": "进入{rotary_name}环岛后从{exit_number}出口驶出",
                    "name": "进入{rotary_name}环岛后从{exit_number}出口驶出进入{way_name}",
                    "destination": "进入{rotary_name}环岛后从{exit_number}出口驶出前往{destination}"
                }
            }
        },
        "roundabout": {
            "default": {
                "exit": {
                    "default": "进入环岛后从{exit_number}出口驶出",
                    "name": "进入环岛后从{exit_number}出口驶出前往{way_name}",
                    "destination": "进入环岛后从{exit_number}出口驶出前往{destination}"
                },
                "default": {
                    "default": "进入环岛",
                    "name": "通过环岛后驶入{way_name}",
                    "destination": "通过环岛后前往{destination}"
                }
            }
        },
        "roundabout turn": {
            "default": {
                "default": "在环岛{modifier}行驶",
                "name": "在环岛{modifier}行驶，上{way_name}",
                "destination": "在环岛{modifier}行驶，前往{destination}"
            },
            "left": {
                "default": "在环岛左转",
                "name": "在环岛左转，上{way_name}",
                "destination": "在环岛左转，前往{destination}"
            },
            "right": {
                "default": "在环岛右转",
                "name": "在环岛右转，上{way_name}",
                "destination": "在环岛右转，前往{destination}"
            },
            "straight": {
                "default": "在环岛继续直行",
                "name": "在环岛继续直行，上{way_name}",
                "destination": "在环岛继续直行，前往{destination}"
            }
        },
        "exit roundabout": {
            "default": {
                "default": "{modifier}转弯",
                "name": "{modifier}转弯，上{way_name}",
                "destination": "{modifier}转弯，前往{destination}"
            },
            "left": {
                "default": "左转",
                "name": "左转，上{way_name}",
                "destination": "左转，前往{destination}"
            },
            "right": {
                "default": "右转",
                "name": "右转，上{way_name}",
                "destination": "右转，前往{destination}"
            },
            "straight": {
                "default": "直行",
                "name": "直行，上{way_name}",
                "destination": "直行，前往{destination}"
            }
        },
        "exit rotary": {
            "default": {
                "default": "{modifier}转弯",
                "name": "{modifier}转弯，上{way_name}",
                "destination": "{modifier}转弯，前往{destination}"
            },
            "left": {
                "default": "左转",
                "name": "左转，上{way_name}",
                "destination": "左转，前往{destination}"
            },
            "right": {
                "default": "右转",
                "name": "右转，上{way_name}",
                "destination": "右转，前往{destination}"
            },
            "straight": {
                "default": "直行",
                "name": "直行，上{way_name}",
                "destination": "直行，前往{destination}"
            }
        },
        "turn": {
            "default": {
                "default": "{modifier}转弯",
                "name": "{modifier}转弯，上{way_name}",
                "destination": "{modifier}转弯，前往{destination}"
            },
            "left": {
                "default": "左转",
                "name": "左转，上{way_name}",
                "destination": "左转，前往{destination}"
            },
            "right": {
                "default": "右转",
                "name": "右转，上{way_name}",
                "destination": "右转，前往{destination}"
            },
            "straight": {
                "default": "直行",
                "name": "直行，上{way_name}",
                "destination": "直行，前往{destination}"
            }
        },
        "use lane": {
            "no_lanes": {
                "default": "继续直行"
            },
            "default": {
                "default": "{lane_instruction}"
            }
        }
    }
}

},{}],24:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);

	module.exports = L.Class.extend({
		options: {
			timeout: 500,
			blurTimeout: 100,
			noResultsMessage: 'No results found.'
		},

		initialize: function(elem, callback, context, options) {
			L.setOptions(this, options);

			this._elem = elem;
			this._resultFn = options.resultFn ? L.Util.bind(options.resultFn, options.resultContext) : null;
			this._autocomplete = options.autocompleteFn ? L.Util.bind(options.autocompleteFn, options.autocompleteContext) : null;
			this._selectFn = L.Util.bind(callback, context);
			this._container = L.DomUtil.create('div', 'leaflet-routing-geocoder-result');
			this._resultTable = L.DomUtil.create('table', '', this._container);

			// TODO: looks a bit like a kludge to register same for input and keypress -
			// browsers supporting both will get duplicate events; just registering
			// input will not catch enter, though.
			L.DomEvent.addListener(this._elem, 'input', this._keyPressed, this);
			L.DomEvent.addListener(this._elem, 'keypress', this._keyPressed, this);
			L.DomEvent.addListener(this._elem, 'keydown', this._keyDown, this);
			L.DomEvent.addListener(this._elem, 'blur', function() {
				if (this._isOpen) {
					this.close();
				}
			}, this);
		},

		close: function() {
			L.DomUtil.removeClass(this._container, 'leaflet-routing-geocoder-result-open');
			this._isOpen = false;
		},

		_open: function() {
			var rect = this._elem.getBoundingClientRect();
			if (!this._container.parentElement) {
				// See notes section under https://developer.mozilla.org/en-US/docs/Web/API/Window/scrollX
				// This abomination is required to support all flavors of IE
				var scrollX = (window.pageXOffset !== undefined) ? window.pageXOffset
					: (document.documentElement || document.body.parentNode || document.body).scrollLeft;
				var scrollY = (window.pageYOffset !== undefined) ? window.pageYOffset
					: (document.documentElement || document.body.parentNode || document.body).scrollTop;
				this._container.style.left = (rect.left + scrollX) + 'px';
				this._container.style.top = (rect.bottom + scrollY) + 'px';
				this._container.style.width = (rect.right - rect.left) + 'px';
				document.body.appendChild(this._container);
			}

			L.DomUtil.addClass(this._container, 'leaflet-routing-geocoder-result-open');
			this._isOpen = true;
		},

		_setResults: function(results) {
			var i,
			    tr,
			    td,
			    text;

			delete this._selection;
			this._results = results;

			while (this._resultTable.firstChild) {
				this._resultTable.removeChild(this._resultTable.firstChild);
			}

			for (i = 0; i < results.length; i++) {
				tr = L.DomUtil.create('tr', '', this._resultTable);
				tr.setAttribute('data-result-index', i);
				td = L.DomUtil.create('td', '', tr);
				text = document.createTextNode(results[i].name);
				td.appendChild(text);
				// mousedown + click because:
				// http://stackoverflow.com/questions/10652852/jquery-fire-click-before-blur-event
				L.DomEvent.addListener(td, 'mousedown', L.DomEvent.preventDefault);
				L.DomEvent.addListener(td, 'click', this._createClickListener(results[i]));
			}

			if (!i) {
				tr = L.DomUtil.create('tr', '', this._resultTable);
				td = L.DomUtil.create('td', 'leaflet-routing-geocoder-no-results', tr);
				td.innerHTML = this.options.noResultsMessage;
			}

			this._open();

			if (results.length > 0) {
				// Select the first entry
				this._select(1);
			}
		},

		_createClickListener: function(r) {
			var resultSelected = this._resultSelected(r);
			return L.bind(function() {
				this._elem.blur();
				resultSelected();
			}, this);
		},

		_resultSelected: function(r) {
			return L.bind(function() {
				this.close();
				this._elem.value = r.name;
				this._lastCompletedText = r.name;
				this._selectFn(r);
			}, this);
		},

		_keyPressed: function(e) {
			var index;

			if (this._isOpen && e.keyCode === 13 && this._selection) {
				index = parseInt(this._selection.getAttribute('data-result-index'), 10);
				this._resultSelected(this._results[index])();
				L.DomEvent.preventDefault(e);
				return;
			}

			if (e.keyCode === 13) {
				this._complete(this._resultFn, true);
				return;
			}

			if (this._autocomplete && document.activeElement === this._elem) {
				if (this._timer) {
					clearTimeout(this._timer);
				}
				this._timer = setTimeout(L.Util.bind(function() { this._complete(this._autocomplete); }, this),
					this.options.timeout);
				return;
			}

			this._unselect();
		},

		_select: function(dir) {
			var sel = this._selection;
			if (sel) {
				L.DomUtil.removeClass(sel.firstChild, 'leaflet-routing-geocoder-selected');
				sel = sel[dir > 0 ? 'nextSibling' : 'previousSibling'];
			}
			if (!sel) {
				sel = this._resultTable[dir > 0 ? 'firstChild' : 'lastChild'];
			}

			if (sel) {
				L.DomUtil.addClass(sel.firstChild, 'leaflet-routing-geocoder-selected');
				this._selection = sel;
			}
		},

		_unselect: function() {
			if (this._selection) {
				L.DomUtil.removeClass(this._selection.firstChild, 'leaflet-routing-geocoder-selected');
			}
			delete this._selection;
		},

		_keyDown: function(e) {
			if (this._isOpen) {
				switch (e.keyCode) {
				// Escape
				case 27:
					this.close();
					L.DomEvent.preventDefault(e);
					return;
				// Up
				case 38:
					this._select(-1);
					L.DomEvent.preventDefault(e);
					return;
				// Down
				case 40:
					this._select(1);
					L.DomEvent.preventDefault(e);
					return;
				}
			}
		},

		_complete: function(completeFn, trySelect) {
			var v = this._elem.value;
			function completeResults(results) {
				this._lastCompletedText = v;
				if (trySelect && results.length === 1) {
					this._resultSelected(results[0])();
				} else {
					this._setResults(results);
				}
			}

			if (!v) {
				return;
			}

			if (v !== this._lastCompletedText) {
				completeFn(v, completeResults, this);
			} else if (trySelect) {
				completeResults.call(this, this._results);
			}
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{}],25:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);

	var Itinerary = _dereq_('./itinerary');
	var Line = _dereq_('./line');
	var Plan = _dereq_('./plan');
	var OSRMv1 = _dereq_('./osrm-v1');

	module.exports = Itinerary.extend({
		options: {
			fitSelectedRoutes: 'smart',
			routeLine: function(route, options) { return new Line(route, options); },
			autoRoute: true,
			routeWhileDragging: false,
			routeDragInterval: 500,
			waypointMode: 'connect',
			showAlternatives: false,
			defaultErrorHandler: function(e) {
				console.error('Routing error:', e.error);
			}
		},

		initialize: function(options) {
			L.Util.setOptions(this, options);

			this._router = this.options.router || new OSRMv1(options);
			this._plan = this.options.plan || new Plan(this.options.waypoints, options);
			this._requestCount = 0;

			Itinerary.prototype.initialize.call(this, options);

			this.on('routeselected', this._routeSelected, this);
			if (this.options.defaultErrorHandler) {
				this.on('routingerror', this.options.defaultErrorHandler);
			}
			this._plan.on('waypointschanged', this._onWaypointsChanged, this);
			if (options.routeWhileDragging) {
				this._setupRouteDragging();
			}

			if (this.options.autoRoute) {
				this.route();
			}
		},

		_onZoomEnd: function() {
			if (!this._selectedRoute ||
				!this._router.requiresMoreDetail) {
				return;
			}

			var map = this._map;
			if (this._router.requiresMoreDetail(this._selectedRoute,
					map.getZoom(), map.getBounds())) {
				this.route({
					callback: L.bind(function(err, routes) {
						var i;
						if (!err) {
							for (i = 0; i < routes.length; i++) {
								this._routes[i].properties = routes[i].properties;
							}
							this._updateLineCallback(err, routes);
						}

					}, this),
					simplifyGeometry: false,
					geometryOnly: true
				});
			}
		},

		onAdd: function(map) {
			var container = Itinerary.prototype.onAdd.call(this, map);

			this._map = map;
			this._map.addLayer(this._plan);

			this._map.on('zoomend', this._onZoomEnd, this);

			if (this._plan.options.geocoder) {
				container.insertBefore(this._plan.createGeocoders(), container.firstChild);
			}

			return container;
		},

		onRemove: function(map) {
			map.off('zoomend', this._onZoomEnd, this);
			if (this._line) {
				map.removeLayer(this._line);
			}
			map.removeLayer(this._plan);
			if (this._alternatives && this._alternatives.length > 0) {
				for (var i = 0, len = this._alternatives.length; i < len; i++) {
					map.removeLayer(this._alternatives[i]);
				}
			}
			return Itinerary.prototype.onRemove.call(this, map);
		},

		getWaypoints: function() {
			return this._plan.getWaypoints();
		},

		setWaypoints: function(waypoints) {
			this._plan.setWaypoints(waypoints);
			return this;
		},

		spliceWaypoints: function() {
			var removed = this._plan.spliceWaypoints.apply(this._plan, arguments);
			return removed;
		},

		getPlan: function() {
			return this._plan;
		},

		getRouter: function() {
			return this._router;
		},

		_routeSelected: function(e) {
			var route = this._selectedRoute = e.route,
				alternatives = this.options.showAlternatives && e.alternatives,
				fitMode = this.options.fitSelectedRoutes,
				fitBounds =
					(fitMode === 'smart' && !this._waypointsVisible()) ||
					(fitMode !== 'smart' && fitMode);

			this._updateLines({route: route, alternatives: alternatives});

			if (fitBounds) {
				this._map.fitBounds(this._line.getBounds());
			}

			if (this.options.waypointMode === 'snap') {
				this._plan.off('waypointschanged', this._onWaypointsChanged, this);
				this.setWaypoints(route.waypoints);
				this._plan.on('waypointschanged', this._onWaypointsChanged, this);
			}
		},

		_waypointsVisible: function() {
			var wps = this.getWaypoints(),
				mapSize,
				bounds,
				boundsSize,
				i,
				p;

			try {
				mapSize = this._map.getSize();

				for (i = 0; i < wps.length; i++) {
					p = this._map.latLngToLayerPoint(wps[i].latLng);

					if (bounds) {
						bounds.extend(p);
					} else {
						bounds = L.bounds([p]);
					}
				}

				boundsSize = bounds.getSize();
				return (boundsSize.x > mapSize.x / 5 ||
					boundsSize.y > mapSize.y / 5) && this._waypointsInViewport();

			} catch (e) {
				return false;
			}
		},

		_waypointsInViewport: function() {
			var wps = this.getWaypoints(),
				mapBounds,
				i;

			try {
				mapBounds = this._map.getBounds();
			} catch (e) {
				return false;
			}

			for (i = 0; i < wps.length; i++) {
				if (mapBounds.contains(wps[i].latLng)) {
					return true;
				}
			}

			return false;
		},

		_updateLines: function(routes) {
			var addWaypoints = this.options.addWaypoints !== undefined ?
				this.options.addWaypoints : true;
			this._clearLines();

			// add alternatives first so they lie below the main route
			this._alternatives = [];
			if (routes.alternatives) routes.alternatives.forEach(function(alt, i) {
				this._alternatives[i] = this.options.routeLine(alt,
					L.extend({
						isAlternative: true
					}, this.options.altLineOptions || this.options.lineOptions));
				this._alternatives[i].addTo(this._map);
				this._hookAltEvents(this._alternatives[i]);
			}, this);

			this._line = this.options.routeLine(routes.route,
				L.extend({
					addWaypoints: addWaypoints,
					extendToWaypoints: this.options.waypointMode === 'connect'
				}, this.options.lineOptions));
			this._line.addTo(this._map);
			this._hookEvents(this._line);
		},

		_hookEvents: function(l) {
			l.on('linetouched', function(e) {
				this._plan.dragNewWaypoint(e);
			}, this);
		},

		_hookAltEvents: function(l) {
			l.on('linetouched', function(e) {
				var alts = this._routes.slice();
				var selected = alts.splice(e.target._route.routesIndex, 1)[0];
				this.fire('routeselected', {route: selected, alternatives: alts});
			}, this);
		},

		_onWaypointsChanged: function(e) {
			if (this.options.autoRoute) {
				this.route({});
			}
			if (!this._plan.isReady()) {
				this._clearLines();
				this._clearAlts();
			}
			this.fire('waypointschanged', {waypoints: e.waypoints});
		},

		_setupRouteDragging: function() {
			var timer = 0,
				waypoints;

			this._plan.on('waypointdrag', L.bind(function(e) {
				waypoints = e.waypoints;

				if (!timer) {
					timer = setTimeout(L.bind(function() {
						this.route({
							waypoints: waypoints,
							geometryOnly: true,
							callback: L.bind(this._updateLineCallback, this)
						});
						timer = undefined;
					}, this), this.options.routeDragInterval);
				}
			}, this));
			this._plan.on('waypointdragend', function() {
				if (timer) {
					clearTimeout(timer);
					timer = undefined;
				}
				this.route();
			}, this);
		},

		_updateLineCallback: function(err, routes) {
			if (!err) {
				routes = routes.slice();
				var selected = routes.splice(this._selectedRoute.routesIndex, 1)[0];
				this._updateLines({route: selected, alternatives: routes });
			} else if (err.type !== 'abort') {
				this._clearLines();
			}
		},

		route: function(options) {
			var ts = ++this._requestCount,
				wps;

			if (this._pendingRequest && this._pendingRequest.abort) {
				this._pendingRequest.abort();
				this._pendingRequest = null;
			}

			options = options || {};

			if (this._plan.isReady()) {
				if (this.options.useZoomParameter) {
					options.z = this._map && this._map.getZoom();
				}

				wps = options && options.waypoints || this._plan.getWaypoints();
				this.fire('routingstart', {waypoints: wps});
				this._pendingRequest = this._router.route(wps, function(err, routes) {
					this._pendingRequest = null;

					if (options.callback) {
						return options.callback.call(this, err, routes);
					}

					// Prevent race among multiple requests,
					// by checking the current request's count
					// against the last request's; ignore result if
					// this isn't the last request.
					if (ts === this._requestCount) {
						this._clearLines();
						this._clearAlts();
						if (err && err.type !== 'abort') {
							this.fire('routingerror', {error: err});
							return;
						}

						routes.forEach(function(route, i) { route.routesIndex = i; });

						if (!options.geometryOnly) {
							this.fire('routesfound', {waypoints: wps, routes: routes});
							this.setAlternatives(routes);
						} else {
							var selectedRoute = routes.splice(0,1)[0];
							this._routeSelected({route: selectedRoute, alternatives: routes});
						}
					}
				}, this, options);
			}
		},

		_clearLines: function() {
			if (this._line) {
				this._map.removeLayer(this._line);
				delete this._line;
			}
			if (this._alternatives && this._alternatives.length) {
				for (var i in this._alternatives) {
					this._map.removeLayer(this._alternatives[i]);
				}
				this._alternatives = [];
			}
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./itinerary":31,"./line":32,"./osrm-v1":35,"./plan":36}],26:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);

	module.exports = L.Control.extend({
		options: {
			header: 'Routing error',
			formatMessage: function(error) {
				if (error.status < 0) {
					return 'Calculating the route caused an error. Technical description follows: <code><pre>' +
						error.message + '</pre></code';
				} else {
					return 'The route could not be calculated. ' +
						error.message;
				}
			}
		},

		initialize: function(routingControl, options) {
			L.Control.prototype.initialize.call(this, options);
			routingControl
				.on('routingerror', L.bind(function(e) {
					if (this._element) {
						this._element.children[1].innerHTML = this.options.formatMessage(e.error);
						this._element.style.visibility = 'visible';
					}
				}, this))
				.on('routingstart', L.bind(function() {
					if (this._element) {
						this._element.style.visibility = 'hidden';
					}
				}, this));
		},

		onAdd: function() {
			var header,
				message;

			this._element = L.DomUtil.create('div', 'leaflet-bar leaflet-routing-error');
			this._element.style.visibility = 'hidden';

			header = L.DomUtil.create('h3', null, this._element);
			message = L.DomUtil.create('span', null, this._element);

			header.innerHTML = this.options.header;

			return this._element;
		},

		onRemove: function() {
			delete this._element;
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{}],27:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);

	var Localization = _dereq_('./localization');

	module.exports = L.Class.extend({
		options: {
			units: 'metric',
			unitNames: null,
			language: 'en',
			roundingSensitivity: 1,
			distanceTemplate: '{value} {unit}'
		},

		initialize: function(options) {
			L.setOptions(this, options);

			var langs = L.Util.isArray(this.options.language) ?
				this.options.language :
				[this.options.language, 'en'];
			this._localization = new Localization(langs);
		},

		formatDistance: function(d /* Number (meters) */, sensitivity) {
			var un = this.options.unitNames || this._localization.localize('units'),
				simpleRounding = sensitivity <= 0,
				round = simpleRounding ? function(v) { return v; } : L.bind(this._round, this),
			    v,
			    yards,
				data,
				pow10;

			if (this.options.units === 'imperial') {
				yards = d / 0.9144;
				if (yards >= 1000) {
					data = {
						value: round(d / 1609.344, sensitivity),
						unit: un.miles
					};
				} else {
					data = {
						value: round(yards, sensitivity),
						unit: un.yards
					};
				}
			} else {
				v = round(d, sensitivity);
				data = {
					value: v >= 1000 ? (v / 1000) : v,
					unit: v >= 1000 ? un.kilometers : un.meters
				};
			}

			if (simpleRounding) {
				data.value = data.value.toFixed(-sensitivity);
			}

			return L.Util.template(this.options.distanceTemplate, data);
		},

		_round: function(d, sensitivity) {
			var s = sensitivity || this.options.roundingSensitivity,
				pow10 = Math.pow(10, (Math.floor(d / s) + '').length - 1),
				r = Math.floor(d / pow10),
				p = (r > 5) ? pow10 : pow10 / 2;

			return Math.round(d / p) * p;
		},

		formatTime: function(t /* Number (seconds) */) {
			var un = this.options.unitNames || this._localization.localize('units');
			// More than 30 seconds precision looks ridiculous
			t = Math.round(t / 30) * 30;

			if (t > 86400) {
				return Math.round(t / 3600) + ' ' + un.hours;
			} else if (t > 3600) {
				return Math.floor(t / 3600) + ' ' + un.hours + ' ' +
					Math.round((t % 3600) / 60) + ' ' + un.minutes;
			} else if (t > 300) {
				return Math.round(t / 60) + ' ' + un.minutes;
			} else if (t > 60) {
				return Math.floor(t / 60) + ' ' + un.minutes +
					(t % 60 !== 0 ? ' ' + (t % 60) + ' ' + un.seconds : '');
			} else {
				return t + ' ' + un.seconds;
			}
		},

		formatInstruction: function(instr, i) {
			if (instr.text === undefined) {
				return this.capitalize(L.Util.template(this._getInstructionTemplate(instr, i),
					L.extend({}, instr, {
						exitStr: instr.exit ? this._localization.localize('formatOrder')(instr.exit) : '',
						dir: this._localization.localize(['directions', instr.direction]),
						modifier: this._localization.localize(['directions', instr.modifier])
					})));
			} else {
				return instr.text;
			}
		},

		getIconName: function(instr, i) {
			switch (instr.type) {
			case 'Head':
				if (i === 0) {
					return 'depart';
				}
				break;
			case 'WaypointReached':
				return 'via';
			case 'Roundabout':
				return 'enter-roundabout';
			case 'DestinationReached':
				return 'arrive';
			}

			switch (instr.modifier) {
			case 'Straight':
				return 'continue';
			case 'SlightRight':
				return 'bear-right';
			case 'Right':
				return 'turn-right';
			case 'SharpRight':
				return 'sharp-right';
			case 'TurnAround':
			case 'Uturn':
				return 'u-turn';
			case 'SharpLeft':
				return 'sharp-left';
			case 'Left':
				return 'turn-left';
			case 'SlightLeft':
				return 'bear-left';
			}
		},

		capitalize: function(s) {
			return s.charAt(0).toUpperCase() + s.substring(1);
		},

		_getInstructionTemplate: function(instr, i) {
			var type = instr.type === 'Straight' ? (i === 0 ? 'Head' : 'Continue') : instr.type,
				strings = this._localization.localize(['instructions', type]);

			if (!strings) {
				strings = [
					this._localization.localize(['directions', type]),
					' ' + this._localization.localize(['instructions', 'Onto'])
				];
			}

			return strings[0] + (strings.length > 1 && instr.road ? strings[1] : '');
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./localization":33}],28:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);
	var Autocomplete = _dereq_('./autocomplete');
	var Localization = _dereq_('./localization');

	function selectInputText(input) {
		if (input.setSelectionRange) {
			// On iOS, select() doesn't work
			input.setSelectionRange(0, 9999);
		} else {
			// On at least IE8, setSeleectionRange doesn't exist
			input.select();
		}
	}

	module.exports = L.Class.extend({
		includes: L.Mixin.Events,

		options: {
			createGeocoder: function(i, nWps, options) {
				var container = L.DomUtil.create('div', 'leaflet-routing-geocoder'),
					input = L.DomUtil.create('input', '', container),
					remove = options.addWaypoints ? L.DomUtil.create('span', 'leaflet-routing-remove-waypoint', container) : undefined;

				input.disabled = !options.addWaypoints;

				return {
					container: container,
					input: input,
					closeButton: remove
				};
			},
			geocoderPlaceholder: function(i, numberWaypoints, geocoderElement) {
				var l = new Localization(geocoderElement.options.language).localize('ui');
				return i === 0 ?
					l.startPlaceholder :
					(i < numberWaypoints - 1 ?
						L.Util.template(l.viaPlaceholder, {viaNumber: i}) :
						l.endPlaceholder);
			},

			geocoderClass: function() {
				return '';
			},

			waypointNameFallback: function(latLng) {
				var ns = latLng.lat < 0 ? 'S' : 'N',
					ew = latLng.lng < 0 ? 'W' : 'E',
					lat = (Math.round(Math.abs(latLng.lat) * 10000) / 10000).toString(),
					lng = (Math.round(Math.abs(latLng.lng) * 10000) / 10000).toString();
				return ns + lat + ', ' + ew + lng;
			},
			maxGeocoderTolerance: 200,
			autocompleteOptions: {},
			language: 'en',
		},

		initialize: function(wp, i, nWps, options) {
			L.setOptions(this, options);

			var g = this.options.createGeocoder(i, nWps, this.options),
				closeButton = g.closeButton,
				geocoderInput = g.input;
			geocoderInput.setAttribute('placeholder', this.options.geocoderPlaceholder(i, nWps, this));
			geocoderInput.className = this.options.geocoderClass(i, nWps);

			this._element = g;
			this._waypoint = wp;

			this.update();
			// This has to be here, or geocoder's value will not be properly
			// initialized.
			// TODO: look into why and make _updateWaypointName fix this.
			geocoderInput.value = wp.name;

			L.DomEvent.addListener(geocoderInput, 'click', function() {
				selectInputText(this);
			}, geocoderInput);

			if (closeButton) {
				L.DomEvent.addListener(closeButton, 'click', function() {
					this.fire('delete', { waypoint: this._waypoint });
				}, this);
			}

			new Autocomplete(geocoderInput, function(r) {
					geocoderInput.value = r.name;
					wp.name = r.name;
					wp.latLng = r.center;
					this.fire('geocoded', { waypoint: wp, value: r });
				}, this, L.extend({
					resultFn: this.options.geocoder.geocode,
					resultContext: this.options.geocoder,
					autocompleteFn: this.options.geocoder.suggest,
					autocompleteContext: this.options.geocoder
				}, this.options.autocompleteOptions));
		},

		getContainer: function() {
			return this._element.container;
		},

		setValue: function(v) {
			this._element.input.value = v;
		},

		update: function(force) {
			var wp = this._waypoint,
				wpCoords;

			wp.name = wp.name || '';

			if (wp.latLng && (force || !wp.name)) {
				wpCoords = this.options.waypointNameFallback(wp.latLng);
				if (this.options.geocoder && this.options.geocoder.reverse) {
					this.options.geocoder.reverse(wp.latLng, 67108864 /* zoom 18 */, function(rs) {
						if (rs.length > 0 && rs[0].center.distanceTo(wp.latLng) < this.options.maxGeocoderTolerance) {
							wp.name = rs[0].name;
						} else {
							wp.name = wpCoords;
						}
						this._update();
					}, this);
				} else {
					wp.name = wpCoords;
					this._update();
				}
			}
		},

		focus: function() {
			var input = this._element.input;
			input.focus();
			selectInputText(input);
		},

		_update: function() {
			var wp = this._waypoint,
			    value = wp && wp.name ? wp.name : '';
			this.setValue(value);
			this.fire('reversegeocoded', {waypoint: wp, value: value});
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./autocomplete":24,"./localization":33}],29:[function(_dereq_,module,exports){
(function (global){
var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null),
    Control = _dereq_('./control'),
    Itinerary = _dereq_('./itinerary'),
    Line = _dereq_('./line'),
    OSRMv1 = _dereq_('./osrm-v1'),
    Plan = _dereq_('./plan'),
    Waypoint = _dereq_('./waypoint'),
    Autocomplete = _dereq_('./autocomplete'),
    Formatter = _dereq_('./formatter'),
    GeocoderElement = _dereq_('./geocoder-element'),
    Localization = _dereq_('./localization'),
    ItineraryBuilder = _dereq_('./itinerary-builder'),
    Mapbox = _dereq_('./mapbox'),
    ErrorControl = _dereq_('./error-control');

L.routing = {
    control: function(options) { return new Control(options); },
    itinerary: function(options) {
        return Itinerary(options);
    },
    line: function(route, options) {
        return new Line(route, options);
    },
    plan: function(waypoints, options) {
        return new Plan(waypoints, options);
    },
    waypoint: function(latLng, name, options) {
        return new Waypoint(latLng, name, options);
    },
    osrmv1: function(options) {
        return new OSRMv1(options);
    },
    localization: function(options) {
        return new Localization(options);
    },
    formatter: function(options) {
        return new Formatter(options);
    },
    geocoderElement: function(wp, i, nWps, plan) {
        return new L.Routing.GeocoderElement(wp, i, nWps, plan);
    },
    itineraryBuilder: function(options) {
        return new ItineraryBuilder(options);
    },
    mapbox: function(accessToken, options) {
        return new Mapbox(accessToken, options);
    },
    errorControl: function(routingControl, options) {
        return new ErrorControl(routingControl, options);
    },
    autocomplete: function(elem, callback, context, options) {
        return new Autocomplete(elem, callback, context, options);
    }
};

module.exports = L.Routing = {
    Control: Control,
    Itinerary: Itinerary,
    Line: Line,
    OSRMv1: OSRMv1,
    Plan: Plan,
    Waypoint: Waypoint,
    Autocomplete: Autocomplete,
    Formatter: Formatter,
    GeocoderElement: GeocoderElement,
    Localization: Localization,
    Formatter: Formatter,
    ItineraryBuilder: ItineraryBuilder,

    // Legacy; remove these in next major release
    control: L.routing.control,
    itinerary: L.routing.itinerary,
    line: L.routing.line,
    plan: L.routing.plan,
    waypoint: L.routing.waypoint,
    osrmv1: L.routing.osrmv1,
    geocoderElement: L.routing.geocoderElement,
    mapbox: L.routing.mapbox,
    errorControl: L.routing.errorControl,
};

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./autocomplete":24,"./control":25,"./error-control":26,"./formatter":27,"./geocoder-element":28,"./itinerary":31,"./itinerary-builder":30,"./line":32,"./localization":33,"./mapbox":34,"./osrm-v1":35,"./plan":36,"./waypoint":37}],30:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);

	module.exports = L.Class.extend({
		options: {
			containerClassName: ''
		},

		initialize: function(options) {
			L.setOptions(this, options);
		},

		createContainer: function(className) {
			var table = L.DomUtil.create('table', className || ''),
				colgroup = L.DomUtil.create('colgroup', '', table);

			L.DomUtil.create('col', 'leaflet-routing-instruction-icon', colgroup);
			L.DomUtil.create('col', 'leaflet-routing-instruction-text', colgroup);
			L.DomUtil.create('col', 'leaflet-routing-instruction-distance', colgroup);

			return table;
		},

		createStepsContainer: function() {
			return L.DomUtil.create('tbody', '');
		},

		createStep: function(text, distance, icon, steps) {
			var row = L.DomUtil.create('tr', '', steps),
				span,
				td;
			td = L.DomUtil.create('td', '', row);
			span = L.DomUtil.create('span', 'leaflet-routing-icon leaflet-routing-icon-'+icon, td);
			td.appendChild(span);
			td = L.DomUtil.create('td', '', row);
			td.appendChild(document.createTextNode(text));
			td = L.DomUtil.create('td', '', row);
			td.appendChild(document.createTextNode(distance));
			return row;
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{}],31:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);
	var Formatter = _dereq_('./formatter');
	var ItineraryBuilder = _dereq_('./itinerary-builder');

	module.exports = L.Control.extend({
		includes: L.Mixin.Events,

		options: {
			pointMarkerStyle: {
				radius: 5,
				color: '#03f',
				fillColor: 'white',
				opacity: 1,
				fillOpacity: 0.7
			},
			summaryTemplate: '<h2>{name}</h2><h3>{distance}, {time}</h3>',
			timeTemplate: '{time}',
			containerClassName: '',
			alternativeClassName: '',
			minimizedClassName: '',
			itineraryClassName: '',
			totalDistanceRoundingSensitivity: -1,
			show: true,
			collapsible: undefined,
			collapseBtn: function(itinerary) {
				var collapseBtn = L.DomUtil.create('span', itinerary.options.collapseBtnClass);
				L.DomEvent.on(collapseBtn, 'click', itinerary._toggle, itinerary);
				itinerary._container.insertBefore(collapseBtn, itinerary._container.firstChild);
			},
			collapseBtnClass: 'leaflet-routing-collapse-btn'
		},

		initialize: function(options) {
			L.setOptions(this, options);
			this._formatter = this.options.formatter || new Formatter(this.options);
			this._itineraryBuilder = this.options.itineraryBuilder || new ItineraryBuilder({
				containerClassName: this.options.itineraryClassName
			});
		},

		onAdd: function(map) {
			var collapsible = this.options.collapsible;

			collapsible = collapsible || (collapsible === undefined && map.getSize().x <= 640);

			this._container = L.DomUtil.create('div', 'leaflet-routing-container leaflet-bar ' +
				(!this.options.show ? 'leaflet-routing-container-hide ' : '') +
				(collapsible ? 'leaflet-routing-collapsible ' : '') +
				this.options.containerClassName);
			this._altContainer = this.createAlternativesContainer();
			this._container.appendChild(this._altContainer);
			L.DomEvent.disableClickPropagation(this._container);
			L.DomEvent.addListener(this._container, 'mousewheel', function(e) {
				L.DomEvent.stopPropagation(e);
			});

			if (collapsible) {
				this.options.collapseBtn(this);
			}

			return this._container;
		},

		onRemove: function() {
		},

		createAlternativesContainer: function() {
			return L.DomUtil.create('div', 'leaflet-routing-alternatives-container');
		},

		setAlternatives: function(routes) {
			var i,
			    alt,
			    altDiv;

			this._clearAlts();

			this._routes = routes;

			for (i = 0; i < this._routes.length; i++) {
				alt = this._routes[i];
				altDiv = this._createAlternative(alt, i);
				this._altContainer.appendChild(altDiv);
				this._altElements.push(altDiv);
			}

			this._selectRoute({route: this._routes[0], alternatives: this._routes.slice(1)});

			return this;
		},

		show: function() {
			L.DomUtil.removeClass(this._container, 'leaflet-routing-container-hide');
		},

		hide: function() {
			L.DomUtil.addClass(this._container, 'leaflet-routing-container-hide');
		},

		_toggle: function() {
			var collapsed = L.DomUtil.hasClass(this._container, 'leaflet-routing-container-hide');
			this[collapsed ? 'show' : 'hide']();
		},

		_createAlternative: function(alt, i) {
			var altDiv = L.DomUtil.create('div', 'leaflet-routing-alt ' +
				this.options.alternativeClassName +
				(i > 0 ? ' leaflet-routing-alt-minimized ' + this.options.minimizedClassName : '')),
				template = this.options.summaryTemplate,
				data = L.extend({
					name: alt.name,
					distance: this._formatter.formatDistance(alt.summary.totalDistance, this.options.totalDistanceRoundingSensitivity),
					time: this._formatter.formatTime(alt.summary.totalTime)
				}, alt);
			altDiv.innerHTML = typeof(template) === 'function' ? template(data) : L.Util.template(template, data);
			L.DomEvent.addListener(altDiv, 'click', this._onAltClicked, this);
			this.on('routeselected', this._selectAlt, this);

			altDiv.appendChild(this._createItineraryContainer(alt));
			return altDiv;
		},

		_clearAlts: function() {
			var el = this._altContainer;
			while (el && el.firstChild) {
				el.removeChild(el.firstChild);
			}

			this._altElements = [];
		},

		_createItineraryContainer: function(r) {
			var container = this._itineraryBuilder.createContainer(),
			    steps = this._itineraryBuilder.createStepsContainer(),
			    i,
			    instr,
			    step,
			    distance,
			    text,
			    icon;

			container.appendChild(steps);

			for (i = 0; i < r.instructions.length; i++) {
				instr = r.instructions[i];
				text = this._formatter.formatInstruction(instr, i);
				distance = this._formatter.formatDistance(instr.distance);
				icon = this._formatter.getIconName(instr, i);
				step = this._itineraryBuilder.createStep(text, distance, icon, steps);

				if(instr.index) {
					this._addRowListeners(step, r.coordinates[instr.index]);
				}
			}

			return container;
		},

		_addRowListeners: function(row, coordinate) {
			L.DomEvent.addListener(row, 'mouseover', function() {
				this._marker = L.circleMarker(coordinate,
					this.options.pointMarkerStyle).addTo(this._map);
			}, this);
			L.DomEvent.addListener(row, 'mouseout', function() {
				if (this._marker) {
					this._map.removeLayer(this._marker);
					delete this._marker;
				}
			}, this);
			L.DomEvent.addListener(row, 'click', function(e) {
				this._map.panTo(coordinate);
				L.DomEvent.stopPropagation(e);
			}, this);
		},

		_onAltClicked: function(e) {
			var altElem = e.target || window.event.srcElement;
			while (!L.DomUtil.hasClass(altElem, 'leaflet-routing-alt')) {
				altElem = altElem.parentElement;
			}

			var j = this._altElements.indexOf(altElem);
			var alts = this._routes.slice();
			var route = alts.splice(j, 1)[0];

			this.fire('routeselected', {
				route: route,
				alternatives: alts
			});
		},

		_selectAlt: function(e) {
			var altElem,
			    j,
			    n,
			    classFn;

			altElem = this._altElements[e.route.routesIndex];

			if (L.DomUtil.hasClass(altElem, 'leaflet-routing-alt-minimized')) {
				for (j = 0; j < this._altElements.length; j++) {
					n = this._altElements[j];
					classFn = j === e.route.routesIndex ? 'removeClass' : 'addClass';
					L.DomUtil[classFn](n, 'leaflet-routing-alt-minimized');
					if (this.options.minimizedClassName) {
						L.DomUtil[classFn](n, this.options.minimizedClassName);
					}

					if (j !== e.route.routesIndex) n.scrollTop = 0;
				}
			}

			L.DomEvent.stop(e);
		},

		_selectRoute: function(routes) {
			if (this._marker) {
				this._map.removeLayer(this._marker);
				delete this._marker;
			}
			this.fire('routeselected', routes);
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./formatter":27,"./itinerary-builder":30}],32:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);
	
	module.exports = L.LayerGroup.extend({
		includes: L.Mixin.Events,

		options: {
			styles: [
				{color: 'black', opacity: 0.15, weight: 9},
				{color: 'white', opacity: 0.8, weight: 6},
				{color: 'red', opacity: 1, weight: 2}
			],
			missingRouteStyles: [
				{color: 'black', opacity: 0.15, weight: 7},
				{color: 'white', opacity: 0.6, weight: 4},
				{color: 'gray', opacity: 0.8, weight: 2, dashArray: '7,12'}
			],
			addWaypoints: true,
			extendToWaypoints: true,
			missingRouteTolerance: 10
		},

		initialize: function(route, options) {
			L.setOptions(this, options);
			L.LayerGroup.prototype.initialize.call(this, options);
			this._route = route;

			if (this.options.extendToWaypoints) {
				this._extendToWaypoints();
			}

			this._addSegment(
				route.coordinates,
				this.options.styles,
				this.options.addWaypoints);
		},
		
		getBounds: function() {
			return L.latLngBounds(this._route.coordinates);
		},

		_findWaypointIndices: function() {
			var wps = this._route.inputWaypoints,
			    indices = [],
			    i;
			for (i = 0; i < wps.length; i++) {
				indices.push(this._findClosestRoutePoint(wps[i].latLng));
			}

			return indices;
		},

		_findClosestRoutePoint: function(latlng) {
			var minDist = Number.MAX_VALUE,
				minIndex,
			    i,
			    d;

			for (i = this._route.coordinates.length - 1; i >= 0 ; i--) {
				// TODO: maybe do this in pixel space instead?
				d = latlng.distanceTo(this._route.coordinates[i]);
				if (d < minDist) {
					minIndex = i;
					minDist = d;
				}
			}

			return minIndex;
		},

		_extendToWaypoints: function() {
			var wps = this._route.inputWaypoints,
				wpIndices = this._getWaypointIndices(),
			    i,
			    wpLatLng,
			    routeCoord;

			for (i = 0; i < wps.length; i++) {
				wpLatLng = wps[i].latLng;
				routeCoord = L.latLng(this._route.coordinates[wpIndices[i]]);
				if (wpLatLng.distanceTo(routeCoord) >
					this.options.missingRouteTolerance) {
					this._addSegment([wpLatLng, routeCoord],
						this.options.missingRouteStyles);
				}
			}
		},

		_addSegment: function(coords, styles, mouselistener) {
			var i,
				pl;

			for (i = 0; i < styles.length; i++) {
				pl = L.polyline(coords, styles[i]);
				this.addLayer(pl);
				if (mouselistener) {
					pl.on('mousedown', this._onLineTouched, this);
				}
			}
		},

		_findNearestWpBefore: function(i) {
			var wpIndices = this._getWaypointIndices(),
				j = wpIndices.length - 1;
			while (j >= 0 && wpIndices[j] > i) {
				j--;
			}

			return j;
		},

		_onLineTouched: function(e) {
			var afterIndex = this._findNearestWpBefore(this._findClosestRoutePoint(e.latlng));
			this.fire('linetouched', {
				afterIndex: afterIndex,
				latlng: e.latlng
			});
		},

		_getWaypointIndices: function() {
			if (!this._wpIndices) {
				this._wpIndices = this._route.waypointIndices || this._findWaypointIndices();
			}

			return this._wpIndices;
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{}],33:[function(_dereq_,module,exports){
/* 
   NOTICE
   Since version 3.2.5, the functionality in this file is by
   default NOT used for localizing OSRM instructions.
   Instead, we rely on the module osrm-text-instructions (https://github.com/Project-OSRM/osrm-text-instructions/).
   
   This file can still be used for other routing backends, or if you specify the
   stepToText option in the OSRMv1 class.
*/

(function() {
	'use strict';

	var spanish = {
		directions: {
			N: 'norte',
			NE: 'noreste',
			E: 'este',
			SE: 'sureste',
			S: 'sur',
			SW: 'suroeste',
			W: 'oeste',
			NW: 'noroeste',
			SlightRight: 'leve giro a la derecha',
			Right: 'derecha',
			SharpRight: 'giro pronunciado a la derecha',
			SlightLeft: 'leve giro a la izquierda',
			Left: 'izquierda',
			SharpLeft: 'giro pronunciado a la izquierda',
			Uturn: 'media vuelta'
		},
		instructions: {
			// instruction, postfix if the road is named
			'Head':
				['Derecho {dir}', ' sobre {road}'],
			'Continue':
				['Continuar {dir}', ' en {road}'],
			'TurnAround':
				['Dar vuelta'],
			'WaypointReached':
				['Llegó a un punto del camino'],
			'Roundabout':
				['Tomar {exitStr} salida en la rotonda', ' en {road}'],
			'DestinationReached':
				['Llegada a destino'],
			'Fork': ['En el cruce gira a {modifier}', ' hacia {road}'],
			'Merge': ['Incorpórate {modifier}', ' hacia {road}'],
			'OnRamp': ['Gira {modifier} en la salida', ' hacia {road}'],
			'OffRamp': ['Toma la salida {modifier}', ' hacia {road}'],
			'EndOfRoad': ['Gira {modifier} al final de la carretera', ' hacia {road}'],
			'Onto': 'hacia {road}'
		},
		formatOrder: function(n) {
			return n + 'º';
		},
		ui: {
			startPlaceholder: 'Inicio',
			viaPlaceholder: 'Via {viaNumber}',
			endPlaceholder: 'Destino'
		},
		units: {
			meters: 'm',
			kilometers: 'km',
			yards: 'yd',
			miles: 'mi',
			hours: 'h',
			minutes: 'min',
			seconds: 's'
		}
	};

	L.Routing = L.Routing || {};

	var Localization = L.Class.extend({
		initialize: function(langs) {
			this._langs = L.Util.isArray(langs) ? langs : [langs, 'en'];

			for (var i = 0, l = this._langs.length; i < l; i++) {
				if (!Localization[this._langs[i]]) {
					throw new Error('No localization for language "' + this._langs[i] + '".');
				}
			}
		},

		localize: function(keys) {
			var dict,
				key,
				value;

			keys = L.Util.isArray(keys) ? keys : [keys];

			for (var i = 0, l = this._langs.length; i < l; i++) {
				dict = Localization[this._langs[i]];
				for (var j = 0, nKeys = keys.length; dict && j < nKeys; j++) {
					key = keys[j];
					value = dict[key];
					dict = value;
				}

				if (value) {
					return value;
				}
			}
		}
	});

	module.exports = L.extend(Localization, {
		'en': {
			directions: {
				N: 'north',
				NE: 'northeast',
				E: 'east',
				SE: 'southeast',
				S: 'south',
				SW: 'southwest',
				W: 'west',
				NW: 'northwest',
				SlightRight: 'slight right',
				Right: 'right',
				SharpRight: 'sharp right',
				SlightLeft: 'slight left',
				Left: 'left',
				SharpLeft: 'sharp left',
				Uturn: 'Turn around'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Head {dir}', ' on {road}'],
				'Continue':
					['Continue {dir}'],
				'TurnAround':
					['Turn around'],
				'WaypointReached':
					['Waypoint reached'],
				'Roundabout':
					['Take the {exitStr} exit in the roundabout', ' onto {road}'],
				'DestinationReached':
					['Destination reached'],
				'Fork': ['At the fork, turn {modifier}', ' onto {road}'],
				'Merge': ['Merge {modifier}', ' onto {road}'],
				'OnRamp': ['Turn {modifier} on the ramp', ' onto {road}'],
				'OffRamp': ['Take the ramp on the {modifier}', ' onto {road}'],
				'EndOfRoad': ['Turn {modifier} at the end of the road', ' onto {road}'],
				'Onto': 'onto {road}'
			},
			formatOrder: function(n) {
				var i = n % 10 - 1,
				suffix = ['st', 'nd', 'rd'];

				return suffix[i] ? n + suffix[i] : n + 'th';
			},
			ui: {
				startPlaceholder: 'Start',
				viaPlaceholder: 'Via {viaNumber}',
				endPlaceholder: 'End'
			},
			units: {
				meters: 'm',
				kilometers: 'km',
				yards: 'yd',
				miles: 'mi',
				hours: 'h',
				minutes: 'min',
				seconds: 's'
			}
		},

		'de': {
			directions: {
				N: 'Norden',
				NE: 'Nordosten',
				E: 'Osten',
				SE: 'Südosten',
				S: 'Süden',
				SW: 'Südwesten',
				W: 'Westen',
				NW: 'Nordwesten',
				SlightRight: 'leicht rechts',
				Right: 'rechts',
				SharpRight: 'scharf rechts',
				SlightLeft: 'leicht links',
				Left: 'links',
				SharpLeft: 'scharf links',
				Uturn: 'Wenden'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Richtung {dir}', ' auf {road}'],
				'Continue':
					['Geradeaus Richtung {dir}', ' auf {road}'],
				'SlightRight':
					['Leicht rechts abbiegen', ' auf {road}'],
				'Right':
					['Rechts abbiegen', ' auf {road}'],
				'SharpRight':
					['Scharf rechts abbiegen', ' auf {road}'],
				'TurnAround':
					['Wenden'],
				'SharpLeft':
					['Scharf links abbiegen', ' auf {road}'],
				'Left':
					['Links abbiegen', ' auf {road}'],
				'SlightLeft':
					['Leicht links abbiegen', ' auf {road}'],
				'WaypointReached':
					['Zwischenhalt erreicht'],
				'Roundabout':
					['Nehmen Sie die {exitStr} Ausfahrt im Kreisverkehr', ' auf {road}'],
				'DestinationReached':
					['Sie haben ihr Ziel erreicht'],
				'Fork': ['An der Kreuzung {modifier}', ' auf {road}'],
				'Merge': ['Fahren Sie {modifier} weiter', ' auf {road}'],
				'OnRamp': ['Fahren Sie {modifier} auf die Auffahrt', ' auf {road}'],
				'OffRamp': ['Nehmen Sie die Ausfahrt {modifier}', ' auf {road}'],
				'EndOfRoad': ['Fahren Sie {modifier} am Ende der Straße', ' auf {road}'],
				'Onto': 'auf {road}'
			},
			formatOrder: function(n) {
				return n + '.';
			},
			ui: {
				startPlaceholder: 'Start',
				viaPlaceholder: 'Via {viaNumber}',
				endPlaceholder: 'Ziel'
			}
		},

		'sv': {
			directions: {
				N: 'norr',
				NE: 'nordost',
				E: 'öst',
				SE: 'sydost',
				S: 'syd',
				SW: 'sydväst',
				W: 'väst',
				NW: 'nordväst',
				SlightRight: 'svagt höger',
				Right: 'höger',
				SharpRight: 'skarpt höger',
				SlightLeft: 'svagt vänster',
				Left: 'vänster',
				SharpLeft: 'skarpt vänster',
				Uturn: 'Vänd'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Åk åt {dir}', ' till {road}'],
				'Continue':
					['Fortsätt {dir}'],
				'SlightRight':
					['Svagt höger', ' till {road}'],
				'Right':
					['Sväng höger', ' till {road}'],
				'SharpRight':
					['Skarpt höger', ' till {road}'],
				'TurnAround':
					['Vänd'],
				'SharpLeft':
					['Skarpt vänster', ' till {road}'],
				'Left':
					['Sväng vänster', ' till {road}'],
				'SlightLeft':
					['Svagt vänster', ' till {road}'],
				'WaypointReached':
					['Viapunkt nådd'],
				'Roundabout':
					['Tag {exitStr} avfarten i rondellen', ' till {road}'],
				'DestinationReached':
					['Framme vid resans mål'],
				'Fork': ['Tag av {modifier}', ' till {road}'],
				'Merge': ['Anslut {modifier} ', ' till {road}'],
				'OnRamp': ['Tag påfarten {modifier}', ' till {road}'],
				'OffRamp': ['Tag avfarten {modifier}', ' till {road}'],
				'EndOfRoad': ['Sväng {modifier} vid vägens slut', ' till {road}'],
				'Onto': 'till {road}'
			},
			formatOrder: function(n) {
				return ['första', 'andra', 'tredje', 'fjärde', 'femte',
					'sjätte', 'sjunde', 'åttonde', 'nionde', 'tionde'
					/* Can't possibly be more than ten exits, can there? */][n - 1];
			},
			ui: {
				startPlaceholder: 'Från',
				viaPlaceholder: 'Via {viaNumber}',
				endPlaceholder: 'Till'
			}
		},

		'es': spanish,
		'sp': spanish,
		
		'nl': {
			directions: {
				N: 'noordelijke',
				NE: 'noordoostelijke',
				E: 'oostelijke',
				SE: 'zuidoostelijke',
				S: 'zuidelijke',
				SW: 'zuidewestelijke',
				W: 'westelijke',
				NW: 'noordwestelijke'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Vertrek in {dir} richting', ' de {road} op'],
				'Continue':
					['Ga in {dir} richting', ' de {road} op'],
				'SlightRight':
					['Volg de weg naar rechts', ' de {road} op'],
				'Right':
					['Ga rechtsaf', ' de {road} op'],
				'SharpRight':
					['Ga scherpe bocht naar rechts', ' de {road} op'],
				'TurnAround':
					['Keer om'],
				'SharpLeft':
					['Ga scherpe bocht naar links', ' de {road} op'],
				'Left':
					['Ga linksaf', ' de {road} op'],
				'SlightLeft':
					['Volg de weg naar links', ' de {road} op'],
				'WaypointReached':
					['Aangekomen bij tussenpunt'],
				'Roundabout':
					['Neem de {exitStr} afslag op de rotonde', ' de {road} op'],
				'DestinationReached':
					['Aangekomen op eindpunt'],
			},
			formatOrder: function(n) {
				if (n === 1 || n >= 20) {
					return n + 'ste';
				} else {
					return n + 'de';
				}
			},
			ui: {
				startPlaceholder: 'Vertrekpunt',
				viaPlaceholder: 'Via {viaNumber}',
				endPlaceholder: 'Bestemming'
			}
		},
		'fr': {
			directions: {
				N: 'nord',
				NE: 'nord-est',
				E: 'est',
				SE: 'sud-est',
				S: 'sud',
				SW: 'sud-ouest',
				W: 'ouest',
				NW: 'nord-ouest'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Tout droit au {dir}', ' sur {road}'],
				'Continue':
					['Continuer au {dir}', ' sur {road}'],
				'SlightRight':
					['Légèrement à droite', ' sur {road}'],
				'Right':
					['A droite', ' sur {road}'],
				'SharpRight':
					['Complètement à droite', ' sur {road}'],
				'TurnAround':
					['Faire demi-tour'],
				'SharpLeft':
					['Complètement à gauche', ' sur {road}'],
				'Left':
					['A gauche', ' sur {road}'],
				'SlightLeft':
					['Légèrement à gauche', ' sur {road}'],
				'WaypointReached':
					['Point d\'étape atteint'],
				'Roundabout':
					['Au rond-point, prenez la {exitStr} sortie', ' sur {road}'],
				'DestinationReached':
					['Destination atteinte'],
			},
			formatOrder: function(n) {
				return n + 'º';
			},
			ui: {
				startPlaceholder: 'Départ',
				viaPlaceholder: 'Intermédiaire {viaNumber}',
				endPlaceholder: 'Arrivée'
			}
		},
		'it': {
			directions: {
				N: 'nord',
				NE: 'nord-est',
				E: 'est',
				SE: 'sud-est',
				S: 'sud',
				SW: 'sud-ovest',
				W: 'ovest',
				NW: 'nord-ovest'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Dritto verso {dir}', ' su {road}'],
				'Continue':
					['Continuare verso {dir}', ' su {road}'],
				'SlightRight':
					['Mantenere la destra', ' su {road}'],
				'Right':
					['A destra', ' su {road}'],
				'SharpRight':
					['Strettamente a destra', ' su {road}'],
				'TurnAround':
					['Fare inversione di marcia'],
				'SharpLeft':
					['Strettamente a sinistra', ' su {road}'],
				'Left':
					['A sinistra', ' sur {road}'],
				'SlightLeft':
					['Mantenere la sinistra', ' su {road}'],
				'WaypointReached':
					['Punto di passaggio raggiunto'],
				'Roundabout':
					['Alla rotonda, prendere la {exitStr} uscita'],
				'DestinationReached':
					['Destinazione raggiunta'],
			},
			formatOrder: function(n) {
				return n + 'º';
			},
			ui: {
				startPlaceholder: 'Partenza',
				viaPlaceholder: 'Intermedia {viaNumber}',
				endPlaceholder: 'Destinazione'
			}
		},
		'pt': {
			directions: {
				N: 'norte',
				NE: 'nordeste',
				E: 'leste',
				SE: 'sudeste',
				S: 'sul',
				SW: 'sudoeste',
				W: 'oeste',
				NW: 'noroeste',
				SlightRight: 'curva ligeira a direita',
				Right: 'direita',
				SharpRight: 'curva fechada a direita',
				SlightLeft: 'ligeira a esquerda',
				Left: 'esquerda',
				SharpLeft: 'curva fechada a esquerda',
				Uturn: 'Meia volta'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Siga {dir}', ' na {road}'],
				'Continue':
					['Continue {dir}', ' na {road}'],
				'SlightRight':
					['Curva ligeira a direita', ' na {road}'],
				'Right':
					['Curva a direita', ' na {road}'],
				'SharpRight':
					['Curva fechada a direita', ' na {road}'],
				'TurnAround':
					['Retorne'],
				'SharpLeft':
					['Curva fechada a esquerda', ' na {road}'],
				'Left':
					['Curva a esquerda', ' na {road}'],
				'SlightLeft':
					['Curva ligueira a esquerda', ' na {road}'],
				'WaypointReached':
					['Ponto de interesse atingido'],
				'Roundabout':
					['Pegue a {exitStr} saída na rotatória', ' na {road}'],
				'DestinationReached':
					['Destino atingido'],
				'Fork': ['Na encruzilhada, vire a {modifier}', ' na {road}'],
				'Merge': ['Entre à {modifier}', ' na {road}'],
				'OnRamp': ['Vire {modifier} na rampa', ' na {road}'],
				'OffRamp': ['Entre na rampa na {modifier}', ' na {road}'],
				'EndOfRoad': ['Vire {modifier} no fim da rua', ' na {road}'],
				'Onto': 'na {road}'
			},
			formatOrder: function(n) {
				return n + 'º';
			},
			ui: {
				startPlaceholder: 'Origem',
				viaPlaceholder: 'Intermédio {viaNumber}',
				endPlaceholder: 'Destino'
			}
		},
		'sk': {
			directions: {
				N: 'sever',
				NE: 'serverovýchod',
				E: 'východ',
				SE: 'juhovýchod',
				S: 'juh',
				SW: 'juhozápad',
				W: 'západ',
				NW: 'serverozápad'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Mierte na {dir}', ' na {road}'],
				'Continue':
					['Pokračujte na {dir}', ' na {road}'],
				'SlightRight':
					['Mierne doprava', ' na {road}'],
				'Right':
					['Doprava', ' na {road}'],
				'SharpRight':
					['Prudko doprava', ' na {road}'],
				'TurnAround':
					['Otočte sa'],
				'SharpLeft':
					['Prudko doľava', ' na {road}'],
				'Left':
					['Doľava', ' na {road}'],
				'SlightLeft':
					['Mierne doľava', ' na {road}'],
				'WaypointReached':
					['Ste v prejazdovom bode.'],
				'Roundabout':
					['Odbočte na {exitStr} výjazde', ' na {road}'],
				'DestinationReached':
					['Prišli ste do cieľa.'],
			},
			formatOrder: function(n) {
				var i = n % 10 - 1,
				suffix = ['.', '.', '.'];

				return suffix[i] ? n + suffix[i] : n + '.';
			},
			ui: {
				startPlaceholder: 'Začiatok',
				viaPlaceholder: 'Cez {viaNumber}',
				endPlaceholder: 'Koniec'
			}
		},
		'el': {
			directions: {
				N: 'βόρεια',
				NE: 'βορειοανατολικά',
				E: 'ανατολικά',
				SE: 'νοτιοανατολικά',
				S: 'νότια',
				SW: 'νοτιοδυτικά',
				W: 'δυτικά',
				NW: 'βορειοδυτικά'
			},
			instructions: {
				// instruction, postfix if the road is named
				'Head':
					['Κατευθυνθείτε {dir}', ' στην {road}'],
				'Continue':
					['Συνεχίστε {dir}', ' στην {road}'],
				'SlightRight':
					['Ελαφρώς δεξιά', ' στην {road}'],
				'Right':
					['Δεξιά', ' στην {road}'],
				'SharpRight':
					['Απότομη δεξιά στροφή', ' στην {road}'],
				'TurnAround':
					['Κάντε αναστροφή'],
				'SharpLeft':
					['Απότομη αριστερή στροφή', ' στην {road}'],
				'Left':
					['Αριστερά', ' στην {road}'],
				'SlightLeft':
					['Ελαφρώς αριστερά', ' στην {road}'],
				'WaypointReached':
					['Φτάσατε στο σημείο αναφοράς'],
				'Roundabout':
					['Ακολουθήστε την {exitStr} έξοδο στο κυκλικό κόμβο', ' στην {road}'],
				'DestinationReached':
					['Φτάσατε στον προορισμό σας'],
			},
			formatOrder: function(n) {
				return n + 'º';
			},
			ui: {
				startPlaceholder: 'Αφετηρία',
				viaPlaceholder: 'μέσω {viaNumber}',
				endPlaceholder: 'Προορισμός'
			}
		},
		'ca': {
			directions: {
				N: 'nord',
				NE: 'nord-est',
				E: 'est',
				SE: 'sud-est',
				S: 'sud',
				SW: 'sud-oest',
				W: 'oest',
				NW: 'nord-oest',
				SlightRight: 'lleu gir a la dreta',
				Right: 'dreta',
				SharpRight: 'gir pronunciat a la dreta',
				SlightLeft: 'gir pronunciat a l\'esquerra',
				Left: 'esquerra',
				SharpLeft: 'lleu gir a l\'esquerra',
				Uturn: 'mitja volta'
			},
			instructions: {
				'Head':
					['Recte {dir}', ' sobre {road}'],
				'Continue':
					['Continuar {dir}'],
				'TurnAround':
					['Donar la volta'],
				'WaypointReached':
					['Ha arribat a un punt del camí'],
				'Roundabout':
					['Agafar {exitStr} sortida a la rotonda', ' a {road}'],
				'DestinationReached':
					['Arribada al destí'],
				'Fork': ['A la cruïlla gira a la {modifier}', ' cap a {road}'],
				'Merge': ['Incorpora\'t {modifier}', ' a {road}'],
				'OnRamp': ['Gira {modifier} a la sortida', ' cap a {road}'],
				'OffRamp': ['Pren la sortida {modifier}', ' cap a {road}'],
				'EndOfRoad': ['Gira {modifier} al final de la carretera', ' cap a {road}'],
				'Onto': 'cap a {road}'
			},
			formatOrder: function(n) {
				return n + 'º';
			},
			ui: {
				startPlaceholder: 'Origen',
				viaPlaceholder: 'Via {viaNumber}',
				endPlaceholder: 'Destí'
			},
			units: {
				meters: 'm',
				kilometers: 'km',
				yards: 'yd',
				miles: 'mi',
				hours: 'h',
				minutes: 'min',
				seconds: 's'
			}
		},
		'ru': {
			directions: {
				N: 'север',
				NE: 'северовосток',
				E: 'восток',
				SE: 'юговосток',
				S: 'юг',
				SW: 'югозапад',
				W: 'запад',
				NW: 'северозапад',
				SlightRight: 'плавно направо',
				Right: 'направо',
				SharpRight: 'резко направо',
				SlightLeft: 'плавно налево',
				Left: 'налево',
				SharpLeft: 'резко налево',
				Uturn: 'развернуться'
			},
			instructions: {
				'Head':
					['Начать движение на {dir}', ' по {road}'],
				'Continue':
					['Продолжать движение на {dir}', ' по {road}'],
				'SlightRight':
					['Плавный поворот направо', ' на {road}'],
				'Right':
					['Направо', ' на {road}'],
				'SharpRight':
					['Резкий поворот направо', ' на {road}'],
				'TurnAround':
					['Развернуться'],
				'SharpLeft':
					['Резкий поворот налево', ' на {road}'],
				'Left':
					['Поворот налево', ' на {road}'],
				'SlightLeft':
					['Плавный поворот налево', ' на {road}'],
				'WaypointReached':
					['Точка достигнута'],
				'Roundabout':
					['{exitStr} съезд с кольца', ' на {road}'],
				'DestinationReached':
					['Окончание маршрута'],
				'Fork': ['На развилке поверните {modifier}', ' на {road}'],
				'Merge': ['Перестройтесь {modifier}', ' на {road}'],
				'OnRamp': ['Поверните {modifier} на съезд', ' на {road}'],
				'OffRamp': ['Съезжайте на {modifier}', ' на {road}'],
				'EndOfRoad': ['Поверните {modifier} в конце дороги', ' на {road}'],
				'Onto': 'на {road}'
			},
			formatOrder: function(n) {
				return n + '-й';
			},
			ui: {
				startPlaceholder: 'Начало',
				viaPlaceholder: 'Через {viaNumber}',
				endPlaceholder: 'Конец'
			},
			units: {
				meters: 'м',
				kilometers: 'км',
				yards: 'ярд',
				miles: 'ми',
				hours: 'ч',
				minutes: 'м',
				seconds: 'с'
			}
		}
	});
})();

},{}],34:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);

	var OSRMv1 = _dereq_('./osrm-v1');

	/**
	 * Works against OSRM's new API in version 5.0; this has
	 * the API version v1.
	 */
	module.exports = OSRMv1.extend({
		options: {
			serviceUrl: 'https://api.mapbox.com/directions/v5',
			profile: 'mapbox/driving',
			useHints: false
		},

		initialize: function(accessToken, options) {
			L.Routing.OSRMv1.prototype.initialize.call(this, options);
			this.options.requestParameters = this.options.requestParameters || {};
			/* jshint camelcase: false */
			this.options.requestParameters.access_token = accessToken;
			/* jshint camelcase: true */
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./osrm-v1":35}],35:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null),
		corslite = _dereq_('@mapbox/corslite'),
		polyline = _dereq_('@mapbox/polyline'),
		osrmTextInstructions = _dereq_('osrm-text-instructions')('v5');

	// Ignore camelcase naming for this file, since OSRM's API uses
	// underscores.
	/* jshint camelcase: false */

	var Waypoint = _dereq_('./waypoint');

	/**
	 * Works against OSRM's new API in version 5.0; this has
	 * the API version v1.
	 */
	module.exports = L.Class.extend({
		options: {
			serviceUrl: 'https://router.project-osrm.org/route/v1',
			profile: 'driving',
			timeout: 30 * 1000,
			routingOptions: {
				alternatives: true,
				steps: true
			},
			polylinePrecision: 5,
			useHints: true,
			suppressDemoServerWarning: false,
			language: 'en'
		},

		initialize: function(options) {
			L.Util.setOptions(this, options);
			this._hints = {
				locations: {}
			};

			if (!this.options.suppressDemoServerWarning &&
				this.options.serviceUrl.indexOf('//router.project-osrm.org') >= 0) {
				console.warn('You are using OSRM\'s demo server. ' +
					'Please note that it is **NOT SUITABLE FOR PRODUCTION USE**.\n' +
					'Refer to the demo server\'s usage policy: ' +
					'https://github.com/Project-OSRM/osrm-backend/wiki/Api-usage-policy\n\n' +
					'To change, set the serviceUrl option.\n\n' +
					'Please do not report issues with this server to neither ' +
					'Leaflet Routing Machine or OSRM - it\'s for\n' +
					'demo only, and will sometimes not be available, or work in ' +
					'unexpected ways.\n\n' +
					'Please set up your own OSRM server, or use a paid service ' +
					'provider for production.');
			}
		},

		route: function(waypoints, callback, context, options) {
			var timedOut = false,
				wps = [],
				url,
				timer,
				wp,
				i,
				xhr;

			options = L.extend({}, this.options.routingOptions, options);
			url = this.buildRouteUrl(waypoints, options);
			if (this.options.requestParameters) {
				url += L.Util.getParamString(this.options.requestParameters, url);
			}

			timer = setTimeout(function() {
				timedOut = true;
				callback.call(context || callback, {
					status: -1,
					message: 'OSRM request timed out.'
				});
			}, this.options.timeout);

			// Create a copy of the waypoints, since they
			// might otherwise be asynchronously modified while
			// the request is being processed.
			for (i = 0; i < waypoints.length; i++) {
				wp = waypoints[i];
				wps.push(new Waypoint(wp.latLng, wp.name, wp.options));
			}

			return xhr = corslite(url, L.bind(function(err, resp) {
				var data,
					error =  {};

				clearTimeout(timer);
				if (!timedOut) {
					if (!err) {
						try {
							data = JSON.parse(resp.responseText);
							try {
								return this._routeDone(data, wps, options, callback, context);
							} catch (ex) {
								error.status = -3;
								error.message = ex.toString();
							}
						} catch (ex) {
							error.status = -2;
							error.message = 'Error parsing OSRM response: ' + ex.toString();
						}
					} else {
						error.message = 'HTTP request failed: ' + err.type +
							(err.target && err.target.status ? ' HTTP ' + err.target.status + ': ' + err.target.statusText : '');
						error.url = url;
						error.status = -1;
						error.target = err;
					}

					callback.call(context || callback, error);
				} else {
					xhr.abort();
				}
			}, this));
		},

		requiresMoreDetail: function(route, zoom, bounds) {
			if (!route.properties.isSimplified) {
				return false;
			}

			var waypoints = route.inputWaypoints,
				i;
			for (i = 0; i < waypoints.length; ++i) {
				if (!bounds.contains(waypoints[i].latLng)) {
					return true;
				}
			}

			return false;
		},

		_routeDone: function(response, inputWaypoints, options, callback, context) {
			var alts = [],
			    actualWaypoints,
			    i,
			    route;

			context = context || callback;
			if (response.code !== 'Ok') {
				callback.call(context, {
					status: response.code
				});
				return;
			}

			actualWaypoints = this._toWaypoints(inputWaypoints, response.waypoints);

			for (i = 0; i < response.routes.length; i++) {
				route = this._convertRoute(response.routes[i]);
				route.inputWaypoints = inputWaypoints;
				route.waypoints = actualWaypoints;
				route.properties = {isSimplified: !options || !options.geometryOnly || options.simplifyGeometry};
				alts.push(route);
			}

			this._saveHintData(response.waypoints, inputWaypoints);

			callback.call(context, null, alts);
		},

		_convertRoute: function(responseRoute) {
			var result = {
					name: '',
					coordinates: [],
					instructions: [],
					summary: {
						totalDistance: responseRoute.distance,
						totalTime: responseRoute.duration
					}
				},
				legNames = [],
				waypointIndices = [],
				index = 0,
				legCount = responseRoute.legs.length,
				hasSteps = responseRoute.legs[0].steps.length > 0,
				i,
				j,
				leg,
				step,
				geometry,
				type,
				modifier,
				text,
				stepToText;

			if (this.options.stepToText) {
				stepToText = this.options.stepToText;
			} else {
				stepToText = L.bind(osrmTextInstructions.compile, osrmTextInstructions, this.options.language);
			}

			for (i = 0; i < legCount; i++) {
				leg = responseRoute.legs[i];
				legNames.push(leg.summary && leg.summary.charAt(0).toUpperCase() + leg.summary.substring(1));
				for (j = 0; j < leg.steps.length; j++) {
					step = leg.steps[j];
					geometry = this._decodePolyline(step.geometry);
					result.coordinates.push.apply(result.coordinates, geometry);
					type = this._maneuverToInstructionType(step.maneuver, i === legCount - 1);
					modifier = this._maneuverToModifier(step.maneuver);
					text = stepToText(step, {legCount: legCount, legIndex: i});

					if (type) {
						if ((i == 0 && step.maneuver.type == 'depart') || step.maneuver.type == 'arrive') {
							waypointIndices.push(index);
						}

						result.instructions.push({
							type: type,
							distance: step.distance,
							time: step.duration,
							road: step.name,
							direction: this._bearingToDirection(step.maneuver.bearing_after),
							exit: step.maneuver.exit,
							index: index,
							mode: step.mode,
							modifier: modifier,
							text: text
						});
					}

					index += geometry.length;
				}
			}

			result.name = legNames.join(', ');
			if (!hasSteps) {
				result.coordinates = this._decodePolyline(responseRoute.geometry);
			} else {
				result.waypointIndices = waypointIndices;
			}

			return result;
		},

		_bearingToDirection: function(bearing) {
			var oct = Math.round(bearing / 45) % 8;
			return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][oct];
		},

		_maneuverToInstructionType: function(maneuver, lastLeg) {
			switch (maneuver.type) {
			case 'new name':
				return 'Continue';
			case 'depart':
				return 'Head';
			case 'arrive':
				return lastLeg ? 'DestinationReached' : 'WaypointReached';
			case 'roundabout':
			case 'rotary':
				return 'Roundabout';
			case 'merge':
			case 'fork':
			case 'on ramp':
			case 'off ramp':
			case 'end of road':
				return this._camelCase(maneuver.type);
			// These are all reduced to the same instruction in the current model
			//case 'turn':
			//case 'ramp': // deprecated in v5.1
			default:
				return this._camelCase(maneuver.modifier);
			}
		},

		_maneuverToModifier: function(maneuver) {
			var modifier = maneuver.modifier;

			switch (maneuver.type) {
			case 'merge':
			case 'fork':
			case 'on ramp':
			case 'off ramp':
			case 'end of road':
				modifier = this._leftOrRight(modifier);
			}

			return modifier && this._camelCase(modifier);
		},

		_camelCase: function(s) {
			var words = s.split(' '),
				result = '';
			for (var i = 0, l = words.length; i < l; i++) {
				result += words[i].charAt(0).toUpperCase() + words[i].substring(1);
			}

			return result;
		},

		_leftOrRight: function(d) {
			return d.indexOf('left') >= 0 ? 'Left' : 'Right';
		},

		_decodePolyline: function(routeGeometry) {
			var cs = polyline.decode(routeGeometry, this.options.polylinePrecision),
				result = new Array(cs.length),
				i;
			for (i = cs.length - 1; i >= 0; i--) {
				result[i] = L.latLng(cs[i]);
			}

			return result;
		},

		_toWaypoints: function(inputWaypoints, vias) {
			var wps = [],
			    i,
			    viaLoc;
			for (i = 0; i < vias.length; i++) {
				viaLoc = vias[i].location;
				wps.push(new Waypoint(L.latLng(viaLoc[1], viaLoc[0]),
				                            inputWaypoints[i].name,
											inputWaypoints[i].options));
			}

			return wps;
		},

		buildRouteUrl: function(waypoints, options) {
			var locs = [],
				hints = [],
				wp,
				latLng,
			    computeInstructions,
			    computeAlternative = true;

			for (var i = 0; i < waypoints.length; i++) {
				wp = waypoints[i];
				latLng = wp.latLng;
				locs.push(latLng.lng + ',' + latLng.lat);
				hints.push(this._hints.locations[this._locationKey(latLng)] || '');
			}

			computeInstructions =
				true;

			return this.options.serviceUrl + '/' + this.options.profile + '/' +
				locs.join(';') + '?' +
				(options.geometryOnly ? (options.simplifyGeometry ? '' : 'overview=full') : 'overview=false') +
				'&alternatives=' + computeAlternative.toString() +
				'&steps=' + computeInstructions.toString() +
				(this.options.useHints ? '&hints=' + hints.join(';') : '') +
				(options.allowUTurns ? '&continue_straight=' + !options.allowUTurns : '');
		},

		_locationKey: function(location) {
			return location.lat + ',' + location.lng;
		},

		_saveHintData: function(actualWaypoints, waypoints) {
			var loc;
			this._hints = {
				locations: {}
			};
			for (var i = actualWaypoints.length - 1; i >= 0; i--) {
				loc = waypoints[i].latLng;
				this._hints.locations[this._locationKey(loc)] = actualWaypoints[i].hint;
			}
		},
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./waypoint":37,"@mapbox/corslite":1,"@mapbox/polyline":2,"osrm-text-instructions":3}],36:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);
	var GeocoderElement = _dereq_('./geocoder-element');
	var Waypoint = _dereq_('./waypoint');

	module.exports = (L.Layer || L.Class).extend({
		includes: L.Mixin.Events,

		options: {
			dragStyles: [
				{color: 'black', opacity: 0.15, weight: 9},
				{color: 'white', opacity: 0.8, weight: 6},
				{color: 'red', opacity: 1, weight: 2, dashArray: '7,12'}
			],
			draggableWaypoints: true,
			routeWhileDragging: false,
			addWaypoints: true,
			reverseWaypoints: false,
			addButtonClassName: '',
			language: 'en',
			createGeocoderElement: function(wp, i, nWps, plan) {
				return new GeocoderElement(wp, i, nWps, plan);
			},
			createMarker: function(i, wp) {
				var options = {
						draggable: this.draggableWaypoints
					},
				    marker = L.marker(wp.latLng, options);

				return marker;
			},
			geocodersClassName: ''
		},

		initialize: function(waypoints, options) {
			L.Util.setOptions(this, options);
			this._waypoints = [];
			this.setWaypoints(waypoints);
		},

		isReady: function() {
			var i;
			for (i = 0; i < this._waypoints.length; i++) {
				if (!this._waypoints[i].latLng) {
					return false;
				}
			}

			return true;
		},

		getWaypoints: function() {
			var i,
				wps = [];

			for (i = 0; i < this._waypoints.length; i++) {
				wps.push(this._waypoints[i]);
			}

			return wps;
		},

		setWaypoints: function(waypoints) {
			var args = [0, this._waypoints.length].concat(waypoints);
			this.spliceWaypoints.apply(this, args);
			return this;
		},

		spliceWaypoints: function() {
			var args = [arguments[0], arguments[1]],
			    i;

			for (i = 2; i < arguments.length; i++) {
				args.push(arguments[i] && arguments[i].hasOwnProperty('latLng') ? arguments[i] : new Waypoint(arguments[i]));
			}

			[].splice.apply(this._waypoints, args);

			// Make sure there's always at least two waypoints
			while (this._waypoints.length < 2) {
				this.spliceWaypoints(this._waypoints.length, 0, null);
			}

			this._updateMarkers();
			this._fireChanged.apply(this, args);
		},

		onAdd: function(map) {
			this._map = map;
			this._updateMarkers();
		},

		onRemove: function() {
			var i;
			this._removeMarkers();

			if (this._newWp) {
				for (i = 0; i < this._newWp.lines.length; i++) {
					this._map.removeLayer(this._newWp.lines[i]);
				}
			}

			delete this._map;
		},

		createGeocoders: function() {
			var container = L.DomUtil.create('div', 'leaflet-routing-geocoders ' + this.options.geocodersClassName),
				waypoints = this._waypoints,
			    addWpBtn,
			    reverseBtn;

			this._geocoderContainer = container;
			this._geocoderElems = [];


			if (this.options.addWaypoints) {
				addWpBtn = L.DomUtil.create('button', 'leaflet-routing-add-waypoint ' + this.options.addButtonClassName, container);
				addWpBtn.setAttribute('type', 'button');
				L.DomEvent.addListener(addWpBtn, 'click', function() {
					this.spliceWaypoints(waypoints.length, 0, null);
				}, this);
			}

			if (this.options.reverseWaypoints) {
				reverseBtn = L.DomUtil.create('button', 'leaflet-routing-reverse-waypoints', container);
				reverseBtn.setAttribute('type', 'button');
				L.DomEvent.addListener(reverseBtn, 'click', function() {
					this._waypoints.reverse();
					this.setWaypoints(this._waypoints);
				}, this);
			}

			this._updateGeocoders();
			this.on('waypointsspliced', this._updateGeocoders);

			return container;
		},

		_createGeocoder: function(i) {
			var geocoder = this.options.createGeocoderElement(this._waypoints[i], i, this._waypoints.length, this.options);
			geocoder
			.on('delete', function() {
				if (i > 0 || this._waypoints.length > 2) {
					this.spliceWaypoints(i, 1);
				} else {
					this.spliceWaypoints(i, 1, new Waypoint());
				}
			}, this)
			.on('geocoded', function(e) {
				this._updateMarkers();
				this._fireChanged();
				this._focusGeocoder(i + 1);
				this.fire('waypointgeocoded', {
					waypointIndex: i,
					waypoint: e.waypoint
				});
			}, this)
			.on('reversegeocoded', function(e) {
				this.fire('waypointgeocoded', {
					waypointIndex: i,
					waypoint: e.waypoint
				});
			}, this);

			return geocoder;
		},

		_updateGeocoders: function() {
			var elems = [],
				i,
			    geocoderElem;

			for (i = 0; i < this._geocoderElems.length; i++) {
				this._geocoderContainer.removeChild(this._geocoderElems[i].getContainer());
			}

			for (i = this._waypoints.length - 1; i >= 0; i--) {
				geocoderElem = this._createGeocoder(i);
				this._geocoderContainer.insertBefore(geocoderElem.getContainer(), this._geocoderContainer.firstChild);
				elems.push(geocoderElem);
			}

			this._geocoderElems = elems.reverse();
		},

		_removeMarkers: function() {
			var i;
			if (this._markers) {
				for (i = 0; i < this._markers.length; i++) {
					if (this._markers[i]) {
						this._map.removeLayer(this._markers[i]);
					}
				}
			}
			this._markers = [];
		},

		_updateMarkers: function() {
			var i,
			    m;

			if (!this._map) {
				return;
			}

			this._removeMarkers();

			for (i = 0; i < this._waypoints.length; i++) {
				if (this._waypoints[i].latLng) {
					m = this.options.createMarker(i, this._waypoints[i], this._waypoints.length);
					if (m) {
						m.addTo(this._map);
						if (this.options.draggableWaypoints) {
							this._hookWaypointEvents(m, i);
						}
					}
				} else {
					m = null;
				}
				this._markers.push(m);
			}
		},

		_fireChanged: function() {
			this.fire('waypointschanged', {waypoints: this.getWaypoints()});

			if (arguments.length >= 2) {
				this.fire('waypointsspliced', {
					index: Array.prototype.shift.call(arguments),
					nRemoved: Array.prototype.shift.call(arguments),
					added: arguments
				});
			}
		},

		_hookWaypointEvents: function(m, i, trackMouseMove) {
			var eventLatLng = function(e) {
					return trackMouseMove ? e.latlng : e.target.getLatLng();
				},
				dragStart = L.bind(function(e) {
					this.fire('waypointdragstart', {index: i, latlng: eventLatLng(e)});
				}, this),
				drag = L.bind(function(e) {
					this._waypoints[i].latLng = eventLatLng(e);
					this.fire('waypointdrag', {index: i, latlng: eventLatLng(e)});
				}, this),
				dragEnd = L.bind(function(e) {
					this._waypoints[i].latLng = eventLatLng(e);
					this._waypoints[i].name = '';
					if (this._geocoderElems) {
						this._geocoderElems[i].update(true);
					}
					this.fire('waypointdragend', {index: i, latlng: eventLatLng(e)});
					this._fireChanged();
				}, this),
				mouseMove,
				mouseUp;

			if (trackMouseMove) {
				mouseMove = L.bind(function(e) {
					this._markers[i].setLatLng(e.latlng);
					drag(e);
				}, this);
				mouseUp = L.bind(function(e) {
					this._map.dragging.enable();
					this._map.off('mouseup', mouseUp);
					this._map.off('mousemove', mouseMove);
					dragEnd(e);
				}, this);
				this._map.dragging.disable();
				this._map.on('mousemove', mouseMove);
				this._map.on('mouseup', mouseUp);
				dragStart({latlng: this._waypoints[i].latLng});
			} else {
				m.on('dragstart', dragStart);
				m.on('drag', drag);
				m.on('dragend', dragEnd);
			}
		},

		dragNewWaypoint: function(e) {
			var newWpIndex = e.afterIndex + 1;
			if (this.options.routeWhileDragging) {
				this.spliceWaypoints(newWpIndex, 0, e.latlng);
				this._hookWaypointEvents(this._markers[newWpIndex], newWpIndex, true);
			} else {
				this._dragNewWaypoint(newWpIndex, e.latlng);
			}
		},

		_dragNewWaypoint: function(newWpIndex, initialLatLng) {
			var wp = new Waypoint(initialLatLng),
				prevWp = this._waypoints[newWpIndex - 1],
				nextWp = this._waypoints[newWpIndex],
				marker = this.options.createMarker(newWpIndex, wp, this._waypoints.length + 1),
				lines = [],
				draggingEnabled = this._map.dragging.enabled(),
				mouseMove = L.bind(function(e) {
					var i,
						latLngs;
					if (marker) {
						marker.setLatLng(e.latlng);
					}
					for (i = 0; i < lines.length; i++) {
						latLngs = lines[i].getLatLngs();
						latLngs.splice(1, 1, e.latlng);
						lines[i].setLatLngs(latLngs);
					}

					L.DomEvent.stop(e);
				}, this),
				mouseUp = L.bind(function(e) {
					var i;
					if (marker) {
						this._map.removeLayer(marker);
					}
					for (i = 0; i < lines.length; i++) {
						this._map.removeLayer(lines[i]);
					}
					this._map.off('mousemove', mouseMove);
					this._map.off('mouseup', mouseUp);
					this.spliceWaypoints(newWpIndex, 0, e.latlng);
					if (draggingEnabled) {
						this._map.dragging.enable();
					}
				}, this),
				i;

			if (marker) {
				marker.addTo(this._map);
			}

			for (i = 0; i < this.options.dragStyles.length; i++) {
				lines.push(L.polyline([prevWp.latLng, initialLatLng, nextWp.latLng],
					this.options.dragStyles[i]).addTo(this._map));
			}

			if (draggingEnabled) {
				this._map.dragging.disable();
			}

			this._map.on('mousemove', mouseMove);
			this._map.on('mouseup', mouseUp);
		},

		_focusGeocoder: function(i) {
			if (this._geocoderElems[i]) {
				this._geocoderElems[i].focus();
			} else {
				document.activeElement.blur();
			}
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{"./geocoder-element":28,"./waypoint":37}],37:[function(_dereq_,module,exports){
(function (global){
(function() {
	'use strict';

	var L = (typeof window !== "undefined" ? window['L'] : typeof global !== "undefined" ? global['L'] : null);

	module.exports = L.Class.extend({
		options: {
			allowUTurn: false,
		},
		initialize: function(latLng, name, options) {
			L.Util.setOptions(this, options);
			this.latLng = L.latLng(latLng);
			this.name = name;
		}
	});
})();

}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{}]},{},[29]);
