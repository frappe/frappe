var Chart = (function () {
'use strict';

function __$styleInject(css, ref) {
  if ( ref === void 0 ) ref = {};
  var insertAt = ref.insertAt;

  if (!css || typeof document === 'undefined') { return; }

  var head = document.head || document.getElementsByTagName('head')[0];
  var style = document.createElement('style');
  style.type = 'text/css';

  if (insertAt === 'top') {
    if (head.firstChild) {
      head.insertBefore(style, head.firstChild);
    } else {
      head.appendChild(style);
    }
  } else {
    head.appendChild(style);
  }

  if (style.styleSheet) {
    style.styleSheet.cssText = css;
  } else {
    style.appendChild(document.createTextNode(css));
  }
}

__$styleInject(".chart-container{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Oxygen,Ubuntu,Cantarell,Fira Sans,Droid Sans,Helvetica Neue,sans-serif}.chart-container .graph-focus-margin{margin:0 5%}.chart-container>.title{margin-top:25px;margin-left:25px;text-align:left;font-weight:400;font-size:12px;color:#6c7680}.chart-container .graphics{margin-top:10px;padding-top:10px;padding-bottom:10px;position:relative}.chart-container .graph-stats-group{display:-webkit-box;display:-ms-flexbox;display:flex;-ms-flex-pack:distribute;justify-content:space-around;-webkit-box-flex:1;-ms-flex:1;flex:1}.chart-container .graph-stats-container{display:-webkit-box;display:-ms-flexbox;display:flex;-webkit-box-pack:justify;-ms-flex-pack:justify;justify-content:space-between;padding:10px}.chart-container .graph-stats-container:after,.chart-container .graph-stats-container:before{content:\"\";display:block}.chart-container .graph-stats-container .stats{padding-bottom:15px}.chart-container .graph-stats-container .stats-title{color:#8d99a6}.chart-container .graph-stats-container .stats-value{font-size:20px;font-weight:300}.chart-container .graph-stats-container .stats-description{font-size:12px;color:#8d99a6}.chart-container .graph-stats-container .graph-data .stats-value{color:#98d85b}.chart-container .axis,.chart-container .chart-label{fill:#555b51}.chart-container .axis line,.chart-container .chart-label line{stroke:#dadada}.chart-container .percentage-graph .progress{margin-bottom:0}.chart-container .dataset-units circle{stroke:#fff;stroke-width:2}.chart-container .dataset-units path{fill:none;stroke-opacity:1;stroke-width:2px}.chart-container .dataset-path,.chart-container .multiaxis-chart .line-horizontal,.chart-container .multiaxis-chart .y-axis-guide{stroke-width:2px}.chart-container .path-group path{fill:none;stroke-opacity:1;stroke-width:2px}.chart-container line.dashed{stroke-dasharray:5,3}.chart-container .axis-line .specific-value{text-anchor:start}.chart-container .axis-line .y-line{text-anchor:end}.chart-container .axis-line .x-line{text-anchor:middle}.chart-container .progress{height:20px;margin-bottom:20px;overflow:hidden;background-color:#f5f5f5;border-radius:4px;-webkit-box-shadow:inset 0 1px 2px rgba(0,0,0,.1);box-shadow:inset 0 1px 2px rgba(0,0,0,.1)}.chart-container .progress-bar{float:left;width:0;height:100%;font-size:12px;line-height:20px;color:#fff;text-align:center;background-color:#36414c;-webkit-box-shadow:inset 0 -1px 0 rgba(0,0,0,.15);box-shadow:inset 0 -1px 0 rgba(0,0,0,.15);-webkit-transition:width .6s ease;transition:width .6s ease}.chart-container .graph-svg-tip{position:absolute;z-index:1;padding:10px;font-size:12px;color:#959da5;text-align:center;background:rgba(0,0,0,.8);border-radius:3px}.chart-container .graph-svg-tip ol,.chart-container .graph-svg-tip ul{padding-left:0;display:-webkit-box;display:-ms-flexbox;display:flex}.chart-container .graph-svg-tip ul.data-point-list li{min-width:90px;-webkit-box-flex:1;-ms-flex:1;flex:1;font-weight:600}.chart-container .graph-svg-tip strong{color:#dfe2e5;font-weight:600}.chart-container .graph-svg-tip .svg-pointer{position:absolute;height:5px;margin:0 0 0 -5px;content:\" \";border:5px solid transparent;border-top-color:rgba(0,0,0,.8)}.chart-container .graph-svg-tip.comparison{padding:0;text-align:left;pointer-events:none}.chart-container .graph-svg-tip.comparison .title{display:block;padding:10px;margin:0;font-weight:600;line-height:1;pointer-events:none}.chart-container .graph-svg-tip.comparison ul{margin:0;white-space:nowrap;list-style:none}.chart-container .graph-svg-tip.comparison li{display:inline-block;padding:5px 10px}.chart-container .indicator,.chart-container .indicator-right{background:none;font-size:12px;vertical-align:middle;font-weight:700;color:#6c7680}.chart-container .indicator i{content:\"\";display:inline-block;height:8px;width:8px;border-radius:8px}.chart-container .indicator:before,.chart-container .indicator i{margin:0 4px 0 0}.chart-container .indicator-right:after{margin:0 0 0 4px}", {});

var _typeof = typeof Symbol === "function" && typeof Symbol.iterator === "symbol" ? function (obj) {
  return typeof obj;
} : function (obj) {
  return obj && typeof Symbol === "function" && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj;
};





var asyncGenerator = function () {
  function AwaitValue(value) {
    this.value = value;
  }

  function AsyncGenerator(gen) {
    var front, back;

    function send(key, arg) {
      return new Promise(function (resolve, reject) {
        var request = {
          key: key,
          arg: arg,
          resolve: resolve,
          reject: reject,
          next: null
        };

        if (back) {
          back = back.next = request;
        } else {
          front = back = request;
          resume(key, arg);
        }
      });
    }

    function resume(key, arg) {
      try {
        var result = gen[key](arg);
        var value = result.value;

        if (value instanceof AwaitValue) {
          Promise.resolve(value.value).then(function (arg) {
            resume("next", arg);
          }, function (arg) {
            resume("throw", arg);
          });
        } else {
          settle(result.done ? "return" : "normal", result.value);
        }
      } catch (err) {
        settle("throw", err);
      }
    }

    function settle(type, value) {
      switch (type) {
        case "return":
          front.resolve({
            value: value,
            done: true
          });
          break;

        case "throw":
          front.reject(value);
          break;

        default:
          front.resolve({
            value: value,
            done: false
          });
          break;
      }

      front = front.next;

      if (front) {
        resume(front.key, front.arg);
      } else {
        back = null;
      }
    }

    this._invoke = send;

    if (typeof gen.return !== "function") {
      this.return = undefined;
    }
  }

  if (typeof Symbol === "function" && Symbol.asyncIterator) {
    AsyncGenerator.prototype[Symbol.asyncIterator] = function () {
      return this;
    };
  }

  AsyncGenerator.prototype.next = function (arg) {
    return this._invoke("next", arg);
  };

  AsyncGenerator.prototype.throw = function (arg) {
    return this._invoke("throw", arg);
  };

  AsyncGenerator.prototype.return = function (arg) {
    return this._invoke("return", arg);
  };

  return {
    wrap: function (fn) {
      return function () {
        return new AsyncGenerator(fn.apply(this, arguments));
      };
    },
    await: function (value) {
      return new AwaitValue(value);
    }
  };
}();





var classCallCheck = function (instance, Constructor) {
  if (!(instance instanceof Constructor)) {
    throw new TypeError("Cannot call a class as a function");
  }
};

var createClass = function () {
  function defineProperties(target, props) {
    for (var i = 0; i < props.length; i++) {
      var descriptor = props[i];
      descriptor.enumerable = descriptor.enumerable || false;
      descriptor.configurable = true;
      if ("value" in descriptor) descriptor.writable = true;
      Object.defineProperty(target, descriptor.key, descriptor);
    }
  }

  return function (Constructor, protoProps, staticProps) {
    if (protoProps) defineProperties(Constructor.prototype, protoProps);
    if (staticProps) defineProperties(Constructor, staticProps);
    return Constructor;
  };
}();







var get = function get(object, property, receiver) {
  if (object === null) object = Function.prototype;
  var desc = Object.getOwnPropertyDescriptor(object, property);

  if (desc === undefined) {
    var parent = Object.getPrototypeOf(object);

    if (parent === null) {
      return undefined;
    } else {
      return get(parent, property, receiver);
    }
  } else if ("value" in desc) {
    return desc.value;
  } else {
    var getter = desc.get;

    if (getter === undefined) {
      return undefined;
    }

    return getter.call(receiver);
  }
};

var inherits = function (subClass, superClass) {
  if (typeof superClass !== "function" && superClass !== null) {
    throw new TypeError("Super expression must either be null or a function, not " + typeof superClass);
  }

  subClass.prototype = Object.create(superClass && superClass.prototype, {
    constructor: {
      value: subClass,
      enumerable: false,
      writable: true,
      configurable: true
    }
  });
  if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass;
};











var possibleConstructorReturn = function (self, call) {
  if (!self) {
    throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
  }

  return call && (typeof call === "object" || typeof call === "function") ? call : self;
};





var slicedToArray = function () {
  function sliceIterator(arr, i) {
    var _arr = [];
    var _n = true;
    var _d = false;
    var _e = undefined;

    try {
      for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) {
        _arr.push(_s.value);

        if (i && _arr.length === i) break;
      }
    } catch (err) {
      _d = true;
      _e = err;
    } finally {
      try {
        if (!_n && _i["return"]) _i["return"]();
      } finally {
        if (_d) throw _e;
      }
    }

    return _arr;
  }

  return function (arr, i) {
    if (Array.isArray(arr)) {
      return arr;
    } else if (Symbol.iterator in Object(arr)) {
      return sliceIterator(arr, i);
    } else {
      throw new TypeError("Invalid attempt to destructure non-iterable instance");
    }
  };
}();













var toConsumableArray = function (arr) {
  if (Array.isArray(arr)) {
    for (var i = 0, arr2 = Array(arr.length); i < arr.length; i++) arr2[i] = arr[i];

    return arr2;
  } else {
    return Array.from(arr);
  }
};

function $(expr, con) {
	return typeof expr === "string" ? (con || document).querySelector(expr) : expr || null;
}



$.create = function (tag, o) {
	var element = document.createElement(tag);

	for (var i in o) {
		var val = o[i];

		if (i === "inside") {
			$(val).appendChild(element);
		} else if (i === "around") {
			var ref = $(val);
			ref.parentNode.insertBefore(element, ref);
			element.appendChild(ref);
		} else if (i === "styles") {
			if ((typeof val === "undefined" ? "undefined" : _typeof(val)) === "object") {
				Object.keys(val).map(function (prop) {
					element.style[prop] = val[prop];
				});
			}
		} else if (i in element) {
			element[i] = val;
		} else {
			element.setAttribute(i, val);
		}
	}

	return element;
};

function getOffset(element) {
	var rect = element.getBoundingClientRect();
	return {
		// https://stackoverflow.com/a/7436602/6495043
		// rect.top varies with scroll, so we add whatever has been
		// scrolled to it to get absolute distance from actual page top
		top: rect.top + (document.documentElement.scrollTop || document.body.scrollTop),
		left: rect.left + (document.documentElement.scrollLeft || document.body.scrollLeft)
	};
}

function isElementInViewport(el) {
	// Although straightforward: https://stackoverflow.com/a/7557433/6495043
	var rect = el.getBoundingClientRect();

	return rect.top >= 0 && rect.left >= 0 && rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) && /*or $(window).height() */
	rect.right <= (window.innerWidth || document.documentElement.clientWidth) /*or $(window).width() */
	;
}

function getElementContentWidth(element) {
	var styles = window.getComputedStyle(element);
	var padding = parseFloat(styles.paddingLeft) + parseFloat(styles.paddingRight);

	return element.clientWidth - padding;
}





function fire(target, type, properties) {
	var evt = document.createEvent("HTMLEvents");

	evt.initEvent(type, true, true);

	for (var j in properties) {
		evt[j] = properties[j];
	}

	return target.dispatchEvent(evt);
}

var SvgTip = function () {
	function SvgTip(_ref) {
		var _ref$parent = _ref.parent,
		    parent = _ref$parent === undefined ? null : _ref$parent,
		    _ref$colors = _ref.colors,
		    colors = _ref$colors === undefined ? [] : _ref$colors;
		classCallCheck(this, SvgTip);

		this.parent = parent;
		this.colors = colors;
		this.titleName = '';
		this.titleValue = '';
		this.listValues = [];
		this.titleValueFirst = 0;

		this.x = 0;
		this.y = 0;

		this.top = 0;
		this.left = 0;

		this.setup();
	}

	createClass(SvgTip, [{
		key: 'setup',
		value: function setup() {
			this.makeTooltip();
		}
	}, {
		key: 'refresh',
		value: function refresh() {
			this.fill();
			this.calcPosition();
			// this.showTip();
		}
	}, {
		key: 'makeTooltip',
		value: function makeTooltip() {
			var _this = this;

			this.container = $.create('div', {
				inside: this.parent,
				className: 'graph-svg-tip comparison',
				innerHTML: '<span class="title"></span>\n\t\t\t\t<ul class="data-point-list"></ul>\n\t\t\t\t<div class="svg-pointer"></div>'
			});
			this.hideTip();

			this.title = this.container.querySelector('.title');
			this.dataPointList = this.container.querySelector('.data-point-list');

			this.parent.addEventListener('mouseleave', function () {
				_this.hideTip();
			});
		}
	}, {
		key: 'fill',
		value: function fill() {
			var _this2 = this;

			var title = void 0;
			if (this.index) {
				this.container.setAttribute('data-point-index', this.index);
			}
			if (this.titleValueFirst) {
				title = '<strong>' + this.titleValue + '</strong>' + this.titleName;
			} else {
				title = this.titleName + '<strong>' + this.titleValue + '</strong>';
			}
			this.title.innerHTML = title;
			this.dataPointList.innerHTML = '';

			this.listValues.map(function (set$$1, i) {
				var color = _this2.colors[i] || 'black';

				var li = $.create('li', {
					styles: {
						'border-top': '3px solid ' + color
					},
					innerHTML: '<strong style="display: block;">' + (set$$1.value === 0 || set$$1.value ? set$$1.value : '') + '</strong>\n\t\t\t\t\t' + (set$$1.title ? set$$1.title : '')
				});

				_this2.dataPointList.appendChild(li);
			});
		}
	}, {
		key: 'calcPosition',
		value: function calcPosition() {
			var width = this.container.offsetWidth;

			this.top = this.y - this.container.offsetHeight;
			this.left = this.x - width / 2;
			var maxLeft = this.parent.offsetWidth - width;

			var pointer = this.container.querySelector('.svg-pointer');

			if (this.left < 0) {
				pointer.style.left = 'calc(50% - ' + -1 * this.left + 'px)';
				this.left = 0;
			} else if (this.left > maxLeft) {
				var delta = this.left - maxLeft;
				var pointerOffset = 'calc(50% + ' + delta + 'px)';
				pointer.style.left = pointerOffset;

				this.left = maxLeft;
			} else {
				pointer.style.left = '50%';
			}
		}
	}, {
		key: 'setValues',
		value: function setValues(x, y) {
			var title = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
			var listValues = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : [];
			var index = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : -1;

			this.titleName = title.name;
			this.titleValue = title.value;
			this.listValues = listValues;
			this.x = x;
			this.y = y;
			this.titleValueFirst = title.valueFirst || 0;
			this.index = index;
			this.refresh();
		}
	}, {
		key: 'hideTip',
		value: function hideTip() {
			this.container.style.top = '0px';
			this.container.style.left = '0px';
			this.container.style.opacity = '0';
		}
	}, {
		key: 'showTip',
		value: function showTip() {
			this.container.style.top = this.top + 'px';
			this.container.style.left = this.left + 'px';
			this.container.style.opacity = '1';
		}
	}]);
	return SvgTip;
}();

var VERT_SPACE_OUTSIDE_BASE_CHART = 50;
var TRANSLATE_Y_BASE_CHART = 20;
var LEFT_MARGIN_BASE_CHART = 60;
var RIGHT_MARGIN_BASE_CHART = 40;
var Y_AXIS_MARGIN = 60;

var INIT_CHART_UPDATE_TIMEOUT = 700;
var CHART_POST_ANIMATE_TIMEOUT = 400;

var DEFAULT_AXIS_CHART_TYPE = 'line';
var AXIS_DATASET_CHART_TYPES = ['line', 'bar'];

var BAR_CHART_SPACE_RATIO = 0.5;
var MIN_BAR_PERCENT_HEIGHT = 0.01;

var LINE_CHART_DOT_SIZE = 4;
var DOT_OVERLAY_SIZE_INCR = 4;

var DEFAULT_CHAR_WIDTH = 7;

// Universal constants
var ANGLE_RATIO = Math.PI / 180;
var FULL_ANGLE = 360;

/**
 * Returns the value of a number upto 2 decimal places.
 * @param {Number} d Any number
 */
function floatTwo(d) {
	return parseFloat(d.toFixed(2));
}

/**
 * Returns whether or not two given arrays are equal.
 * @param {Array} arr1 First array
 * @param {Array} arr2 Second array
 */


/**
 * Shuffles array in place. ES6 version
 * @param {Array} array An array containing the items.
 */


/**
 * Fill an array with extra points
 * @param {Array} array Array
 * @param {Number} count number of filler elements
 * @param {Object} element element to fill with
 * @param {Boolean} start fill at start?
 */
function fillArray(array, count, element) {
	var start = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : false;

	if (!element) {
		element = start ? array[0] : array[array.length - 1];
	}
	var fillerArray = new Array(Math.abs(count)).fill(element);
	array = start ? fillerArray.concat(array) : array.concat(fillerArray);
	return array;
}

/**
 * Returns pixel width of string.
 * @param {String} string
 * @param {Number} charWidth Width of single char in pixels
 */
function getStringWidth(string, charWidth) {
	return (string + "").length * charWidth;
}



function getPositionByAngle(angle, radius) {
	return {
		x: Math.sin(angle * ANGLE_RATIO) * radius,
		y: Math.cos(angle * ANGLE_RATIO) * radius
	};
}

function getBarHeightAndYAttr(yTop, zeroLine) {
	var height = void 0,
	    y = void 0;
	if (yTop <= zeroLine) {
		height = zeroLine - yTop;
		y = yTop;
	} else {
		height = yTop - zeroLine;
		y = zeroLine;
	}

	return [height, y];
}

function equilizeNoOfElements(array1, array2) {
	var extraCount = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : array2.length - array1.length;


	// Doesn't work if either has zero elements.
	if (extraCount > 0) {
		array1 = fillArray(array1, extraCount);
	} else {
		array2 = fillArray(array2, extraCount);
	}
	return [array1, array2];
}

var AXIS_TICK_LENGTH = 6;
var LABEL_MARGIN = 4;
var FONT_SIZE = 10;
var BASE_LINE_COLOR = '#dadada';

function $$1(expr, con) {
	return typeof expr === "string" ? (con || document).querySelector(expr) : expr || null;
}

function createSVG(tag, o) {
	var element = document.createElementNS("http://www.w3.org/2000/svg", tag);

	for (var i in o) {
		var val = o[i];

		if (i === "inside") {
			$$1(val).appendChild(element);
		} else if (i === "around") {
			var ref = $$1(val);
			ref.parentNode.insertBefore(element, ref);
			element.appendChild(ref);
		} else if (i === "styles") {
			if ((typeof val === 'undefined' ? 'undefined' : _typeof(val)) === "object") {
				Object.keys(val).map(function (prop) {
					element.style[prop] = val[prop];
				});
			}
		} else {
			if (i === "className") {
				i = "class";
			}
			if (i === "innerHTML") {
				element['textContent'] = val;
			} else {
				element.setAttribute(i, val);
			}
		}
	}

	return element;
}

function renderVerticalGradient(svgDefElem, gradientId) {
	return createSVG('linearGradient', {
		inside: svgDefElem,
		id: gradientId,
		x1: 0,
		x2: 0,
		y1: 0,
		y2: 1
	});
}

function setGradientStop(gradElem, offset, color, opacity) {
	return createSVG('stop', {
		'inside': gradElem,
		'style': 'stop-color: ' + color,
		'offset': offset,
		'stop-opacity': opacity
	});
}

function makeSVGContainer(parent, className, width, height) {
	return createSVG('svg', {
		className: className,
		inside: parent,
		width: width,
		height: height
	});
}

function makeSVGDefs(svgContainer) {
	return createSVG('defs', {
		inside: svgContainer
	});
}

function makeSVGGroup(parent, className) {
	var transform = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : '';

	return createSVG('g', {
		className: className,
		inside: parent,
		transform: transform
	});
}



function makePath(pathStr) {
	var className = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : '';
	var stroke = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : 'none';
	var fill = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : 'none';

	return createSVG('path', {
		className: className,
		d: pathStr,
		styles: {
			stroke: stroke,
			fill: fill
		}
	});
}

function makeArcPathStr(startPosition, endPosition, center, radius) {
	var clockWise = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : 1;
	var arcStartX = center.x + startPosition.x,
	    arcStartY = center.y + startPosition.y;
	var arcEndX = center.x + endPosition.x,
	    arcEndY = center.y + endPosition.y;


	return 'M' + center.x + ' ' + center.y + '\n\t\tL' + arcStartX + ' ' + arcStartY + '\n\t\tA ' + radius + ' ' + radius + ' 0 0 ' + (clockWise ? 1 : 0) + '\n\t\t' + arcEndX + ' ' + arcEndY + ' z';
}

function makeGradient(svgDefElem, color) {
	var lighter = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : false;

	var gradientId = 'path-fill-gradient' + '-' + color + '-' + (lighter ? 'lighter' : 'default');
	var gradientDef = renderVerticalGradient(svgDefElem, gradientId);
	var opacities = [1, 0.6, 0.2];
	if (lighter) {
		opacities = [0.4, 0.2, 0];
	}

	setGradientStop(gradientDef, "0%", color, opacities[0]);
	setGradientStop(gradientDef, "50%", color, opacities[1]);
	setGradientStop(gradientDef, "100%", color, opacities[2]);

	return gradientId;
}

function makeHeatSquare(className, x, y, size) {
	var fill = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : 'none';
	var data = arguments.length > 5 && arguments[5] !== undefined ? arguments[5] : {};

	var args = {
		className: className,
		x: x,
		y: y,
		width: size,
		height: size,
		fill: fill
	};

	Object.keys(data).map(function (key) {
		args[key] = data[key];
	});

	return createSVG("rect", args);
}

function makeText(className, x, y, content) {
	return createSVG('text', {
		className: className,
		x: x,
		y: y,
		dy: FONT_SIZE / 2 + 'px',
		'font-size': FONT_SIZE + 'px',
		innerHTML: content
	});
}

function makeVertLine(x, label, y1, y2) {
	var options = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : {};

	if (!options.stroke) options.stroke = BASE_LINE_COLOR;
	var l = createSVG('line', {
		className: 'line-vertical ' + options.className,
		x1: 0,
		x2: 0,
		y1: y1,
		y2: y2,
		styles: {
			stroke: options.stroke
		}
	});

	var text = createSVG('text', {
		x: 0,
		y: y1 > y2 ? y1 + LABEL_MARGIN : y1 - LABEL_MARGIN - FONT_SIZE,
		dy: FONT_SIZE + 'px',
		'font-size': FONT_SIZE + 'px',
		'text-anchor': 'middle',
		innerHTML: label + ""
	});

	var line = createSVG('g', {
		transform: 'translate(' + x + ', 0)'
	});

	line.appendChild(l);
	line.appendChild(text);

	return line;
}

function makeHoriLine(y, label, x1, x2) {
	var options = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : {};

	if (!options.stroke) options.stroke = BASE_LINE_COLOR;
	if (!options.lineType) options.lineType = '';
	var className = 'line-horizontal ' + options.className + (options.lineType === "dashed" ? "dashed" : "");

	var l = createSVG('line', {
		className: className,
		x1: x1,
		x2: x2,
		y1: 0,
		y2: 0,
		styles: {
			stroke: options.stroke
		}
	});

	var text = createSVG('text', {
		x: x1 < x2 ? x1 - LABEL_MARGIN : x1 + LABEL_MARGIN,
		y: 0,
		dy: FONT_SIZE / 2 - 2 + 'px',
		'font-size': FONT_SIZE + 'px',
		'text-anchor': x1 < x2 ? 'end' : 'start',
		innerHTML: label + ""
	});

	var line = createSVG('g', {
		transform: 'translate(0, ' + y + ')',
		'stroke-opacity': 1
	});

	if (text === 0 || text === '0') {
		line.style.stroke = "rgba(27, 31, 35, 0.6)";
	}

	line.appendChild(l);
	line.appendChild(text);

	return line;
}

function yLine(y, label, width) {
	var options = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {};

	if (!options.pos) options.pos = 'left';
	if (!options.offset) options.offset = 0;
	if (!options.mode) options.mode = 'span';
	if (!options.stroke) options.stroke = BASE_LINE_COLOR;
	if (!options.className) options.className = '';

	var x1 = -1 * AXIS_TICK_LENGTH;
	var x2 = options.mode === 'span' ? width + AXIS_TICK_LENGTH : 0;

	if (options.mode === 'tick' && options.pos === 'right') {
		x1 = width + AXIS_TICK_LENGTH;
		x2 = width;
	}

	// let offset = options.pos === 'left' ? -1 * options.offset : options.offset;

	x1 += options.offset;
	x2 += options.offset;

	return makeHoriLine(y, label, x1, x2, {
		stroke: options.stroke,
		className: options.className,
		lineType: options.lineType
	});
}

function xLine(x, label, height) {
	var options = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {};

	if (!options.pos) options.pos = 'bottom';
	if (!options.offset) options.offset = 0;
	if (!options.mode) options.mode = 'span';
	if (!options.stroke) options.stroke = BASE_LINE_COLOR;
	if (!options.className) options.className = '';

	// Draw X axis line in span/tick mode with optional label
	//                        	y2(span)
	// 						|
	// 						|
	//				x line	|
	//						|
	// 					   	|
	// ---------------------+-- y2(tick)
	//						|
	//							y1

	var y1 = height + AXIS_TICK_LENGTH;
	var y2 = options.mode === 'span' ? -1 * AXIS_TICK_LENGTH : height;

	if (options.mode === 'tick' && options.pos === 'top') {
		// top axis ticks
		y1 = -1 * AXIS_TICK_LENGTH;
		y2 = 0;
	}

	return makeVertLine(x, label, y1, y2, {
		stroke: options.stroke,
		className: options.className,
		lineType: options.lineType
	});
}

function yMarker(y, label, width) {
	var options = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {};

	var labelSvg = createSVG('text', {
		className: 'chart-label',
		x: width - getStringWidth(label, 5) - LABEL_MARGIN,
		y: 0,
		dy: FONT_SIZE / -2 + 'px',
		'font-size': FONT_SIZE + 'px',
		'text-anchor': 'start',
		innerHTML: label + ""
	});

	var line = makeHoriLine(y, '', 0, width, {
		stroke: options.stroke || BASE_LINE_COLOR,
		className: options.className || '',
		lineType: options.lineType
	});

	line.appendChild(labelSvg);

	return line;
}

function yRegion(y1, y2, width, label) {
	// return a group
	var height = y1 - y2;

	var rect = createSVG('rect', {
		className: 'bar mini', // remove class
		styles: {
			fill: 'rgba(228, 234, 239, 0.49)',
			stroke: BASE_LINE_COLOR,
			'stroke-dasharray': width + ', ' + height
		},
		// 'data-point-index': index,
		x: 0,
		y: 0,
		width: width,
		height: height
	});

	var labelSvg = createSVG('text', {
		className: 'chart-label',
		x: width - getStringWidth(label + "", 4.5) - LABEL_MARGIN,
		y: 0,
		dy: FONT_SIZE / -2 + 'px',
		'font-size': FONT_SIZE + 'px',
		'text-anchor': 'start',
		innerHTML: label + ""
	});

	var region = createSVG('g', {
		transform: 'translate(0, ' + y2 + ')'
	});

	region.appendChild(rect);
	region.appendChild(labelSvg);

	return region;
}

function datasetBar(x, yTop, width, color) {
	var label = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : '';
	var index = arguments.length > 5 && arguments[5] !== undefined ? arguments[5] : 0;
	var offset = arguments.length > 6 && arguments[6] !== undefined ? arguments[6] : 0;
	var meta = arguments.length > 7 && arguments[7] !== undefined ? arguments[7] : {};

	var _getBarHeightAndYAttr = getBarHeightAndYAttr(yTop, meta.zeroLine),
	    _getBarHeightAndYAttr2 = slicedToArray(_getBarHeightAndYAttr, 2),
	    height = _getBarHeightAndYAttr2[0],
	    y = _getBarHeightAndYAttr2[1];

	y -= offset;

	var rect = createSVG('rect', {
		className: 'bar mini',
		style: 'fill: ' + color,
		'data-point-index': index,
		x: x,
		y: y,
		width: width,
		height: height || meta.minHeight // TODO: correct y for positive min height
	});

	label += "";

	if (!label && !label.length) {
		return rect;
	} else {
		rect.setAttribute('y', 0);
		rect.setAttribute('x', 0);
		var text = createSVG('text', {
			className: 'data-point-value',
			x: width / 2,
			y: 0,
			dy: FONT_SIZE / 2 * -1 + 'px',
			'font-size': FONT_SIZE + 'px',
			'text-anchor': 'middle',
			innerHTML: label
		});

		var group = createSVG('g', {
			'data-point-index': index,
			transform: 'translate(' + x + ', ' + y + ')'
		});
		group.appendChild(rect);
		group.appendChild(text);

		return group;
	}
}

function datasetDot(x, y, radius, color) {
	var label = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : '';
	var index = arguments.length > 5 && arguments[5] !== undefined ? arguments[5] : 0;

	var dot = createSVG('circle', {
		style: 'fill: ' + color,
		'data-point-index': index,
		cx: x,
		cy: y,
		r: radius
	});

	label += "";

	if (!label && !label.length) {
		return dot;
	} else {
		dot.setAttribute('cy', 0);
		dot.setAttribute('cx', 0);

		var text = createSVG('text', {
			className: 'data-point-value',
			x: 0,
			y: 0,
			dy: FONT_SIZE / 2 * -1 - radius + 'px',
			'font-size': FONT_SIZE + 'px',
			'text-anchor': 'middle',
			innerHTML: label
		});

		var group = createSVG('g', {
			'data-point-index': index,
			transform: 'translate(' + x + ', ' + y + ')'
		});
		group.appendChild(dot);
		group.appendChild(text);

		return group;
	}
}

function getPaths(xList, yList, color) {
	var options = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {};
	var meta = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : {};

	var pointsList = yList.map(function (y, i) {
		return xList[i] + ',' + y;
	});
	var pointsStr = pointsList.join("L");
	var path = makePath("M" + pointsStr, 'line-graph-path', color);

	// HeatLine
	if (options.heatline) {
		var gradient_id = makeGradient(meta.svgDefs, color);
		path.style.stroke = 'url(#' + gradient_id + ')';
	}

	var paths = {
		path: path
	};

	// Region
	if (options.regionFill) {
		var gradient_id_region = makeGradient(meta.svgDefs, color, true);

		// TODO: use zeroLine OR minimum
		var pathStr = "M" + (xList[0] + ',' + meta.zeroLine + 'L') + pointsStr + ('L' + xList.slice(-1)[0] + ',' + meta.zeroLine);
		paths.region = makePath(pathStr, 'region-fill', 'none', 'url(#' + gradient_id_region + ')');
	}

	return paths;
}

var makeOverlay = {
	'bar': function bar(unit) {
		var transformValue = void 0;
		if (unit.nodeName !== 'rect') {
			transformValue = unit.getAttribute('transform');
			unit = unit.childNodes[0];
		}
		var overlay = unit.cloneNode();
		overlay.style.fill = '#000000';
		overlay.style.opacity = '0.4';

		if (transformValue) {
			overlay.setAttribute('transform', transformValue);
		}
		return overlay;
	},

	'dot': function dot(unit) {
		var transformValue = void 0;
		if (unit.nodeName !== 'circle') {
			transformValue = unit.getAttribute('transform');
			unit = unit.childNodes[0];
		}
		var overlay = unit.cloneNode();
		var radius = unit.getAttribute('r');
		var fill = unit.getAttribute('fill');
		overlay.setAttribute('r', parseInt(radius) + DOT_OVERLAY_SIZE_INCR);
		overlay.setAttribute('fill', fill);
		overlay.style.opacity = '0.6';

		if (transformValue) {
			overlay.setAttribute('transform', transformValue);
		}
		return overlay;
	}
};

var updateOverlay = {
	'bar': function bar(unit, overlay) {
		var transformValue = void 0;
		if (unit.nodeName !== 'rect') {
			transformValue = unit.getAttribute('transform');
			unit = unit.childNodes[0];
		}
		var attributes = ['x', 'y', 'width', 'height'];
		Object.values(unit.attributes).filter(function (attr) {
			return attributes.includes(attr.name) && attr.specified;
		}).map(function (attr) {
			overlay.setAttribute(attr.name, attr.nodeValue);
		});

		if (transformValue) {
			overlay.setAttribute('transform', transformValue);
		}
	},

	'dot': function dot(unit, overlay) {
		var transformValue = void 0;
		if (unit.nodeName !== 'circle') {
			transformValue = unit.getAttribute('transform');
			unit = unit.childNodes[0];
		}
		var attributes = ['cx', 'cy'];
		Object.values(unit.attributes).filter(function (attr) {
			return attributes.includes(attr.name) && attr.specified;
		}).map(function (attr) {
			overlay.setAttribute(attr.name, attr.nodeValue);
		});

		if (transformValue) {
			overlay.setAttribute('transform', transformValue);
		}
	}
};

var PRESET_COLOR_MAP = {
	'light-blue': '#7cd6fd',
	'blue': '#5e64ff',
	'violet': '#743ee2',
	'red': '#ff5858',
	'orange': '#ffa00a',
	'yellow': '#feef72',
	'green': '#28a745',
	'light-green': '#98d85b',
	'purple': '#b554ff',
	'magenta': '#ffa3ef',
	'black': '#36114C',
	'grey': '#bdd3e6',
	'light-grey': '#f0f4f7',
	'dark-grey': '#b8c2cc'
};

var DEFAULT_COLORS = ['light-blue', 'blue', 'violet', 'red', 'orange', 'yellow', 'green', 'light-green', 'purple', 'magenta', 'light-grey', 'dark-grey'];

function limitColor(r) {
	if (r > 255) return 255;else if (r < 0) return 0;
	return r;
}

function lightenDarkenColor(color, amt) {
	var col = getColor(color);
	var usePound = false;
	if (col[0] == "#") {
		col = col.slice(1);
		usePound = true;
	}
	var num = parseInt(col, 16);
	var r = limitColor((num >> 16) + amt);
	var b = limitColor((num >> 8 & 0x00FF) + amt);
	var g = limitColor((num & 0x0000FF) + amt);
	return (usePound ? "#" : "") + (g | b << 8 | r << 16).toString(16);
}

function isValidColor(string) {
	// https://stackoverflow.com/a/8027444/6495043
	return (/(^#[0-9A-F]{6}$)|(^#[0-9A-F]{3}$)/i.test(string)
	);
}

var getColor = function getColor(color) {
	return PRESET_COLOR_MAP[color] || color;
};

var ALL_CHART_TYPES = ['line', 'scatter', 'bar', 'percentage', 'heatmap', 'pie'];

var COMPATIBLE_CHARTS = {
	bar: ['line', 'scatter', 'percentage', 'pie'],
	line: ['scatter', 'bar', 'percentage', 'pie'],
	pie: ['line', 'scatter', 'percentage', 'bar'],
	scatter: ['line', 'bar', 'percentage', 'pie'],
	percentage: ['bar', 'line', 'scatter', 'pie'],
	heatmap: []
};

// Needs structure as per only labels/datasets
var COLOR_COMPATIBLE_CHARTS = {
	bar: ['line', 'scatter'],
	line: ['scatter', 'bar'],
	pie: ['percentage'],
	scatter: ['line', 'bar'],
	percentage: ['pie'],
	heatmap: []
};

function getDifferentChart(type, current_type, parent, args) {
	if (type === current_type) return;

	if (!ALL_CHART_TYPES.includes(type)) {
		console.error('\'' + type + '\' is not a valid chart type.');
	}

	if (!COMPATIBLE_CHARTS[current_type].includes(type)) {
		console.error('\'' + current_type + '\' chart cannot be converted to a \'' + type + '\' chart.');
	}

	// whether the new chart can use the existing colors
	var useColor = COLOR_COMPATIBLE_CHARTS[current_type].includes(type);

	// Okay, this is anticlimactic
	// this function will need to actually be 'changeChartType(type)'
	// that will update only the required elements, but for now ...

	args.type = type;
	args.colors = useColor ? args.colors : undefined;

	return new Chart(parent, args);
}

var UNIT_ANIM_DUR = 350;
var PATH_ANIM_DUR = 350;
var MARKER_LINE_ANIM_DUR = UNIT_ANIM_DUR;
var REPLACE_ALL_NEW_DUR = 250;

var STD_EASING = 'easein';

function translate(unit, oldCoord, newCoord, duration) {
	var old = typeof oldCoord === 'string' ? oldCoord : oldCoord.join(', ');
	return [unit, { transform: newCoord.join(', ') }, duration, STD_EASING, "translate", { transform: old }];
}

function translateVertLine(xLine, newX, oldX) {
	return translate(xLine, [oldX, 0], [newX, 0], MARKER_LINE_ANIM_DUR);
}

function translateHoriLine(yLine, newY, oldY) {
	return translate(yLine, [0, oldY], [0, newY], MARKER_LINE_ANIM_DUR);
}

function animateRegion(rectGroup, newY1, newY2, oldY2) {
	var newHeight = newY1 - newY2;
	var rect = rectGroup.childNodes[0];
	var width = rect.getAttribute("width");
	var rectAnim = [rect, { height: newHeight, 'stroke-dasharray': width + ', ' + newHeight }, MARKER_LINE_ANIM_DUR, STD_EASING];

	var groupAnim = translate(rectGroup, [0, oldY2], [0, newY2], MARKER_LINE_ANIM_DUR);
	return [rectAnim, groupAnim];
}

function animateBar(bar, x, yTop, width) {
	var offset = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : 0;
	var meta = arguments.length > 5 && arguments[5] !== undefined ? arguments[5] : {};

	var _getBarHeightAndYAttr = getBarHeightAndYAttr(yTop, meta.zeroLine),
	    _getBarHeightAndYAttr2 = slicedToArray(_getBarHeightAndYAttr, 2),
	    height = _getBarHeightAndYAttr2[0],
	    y = _getBarHeightAndYAttr2[1];

	y -= offset;
	if (bar.nodeName !== 'rect') {
		var rect = bar.childNodes[0];
		var rectAnim = [rect, { width: width, height: height }, UNIT_ANIM_DUR, STD_EASING];

		var oldCoordStr = bar.getAttribute("transform").split("(")[1].slice(0, -1);
		var groupAnim = translate(bar, oldCoordStr, [x, y], MARKER_LINE_ANIM_DUR);
		return [rectAnim, groupAnim];
	} else {
		return [[bar, { width: width, height: height, x: x, y: y }, UNIT_ANIM_DUR, STD_EASING]];
	}
	// bar.animate({height: args.newHeight, y: yTop}, UNIT_ANIM_DUR, mina.easein);
}

function animateDot(dot, x, y) {
	if (dot.nodeName !== 'circle') {
		var oldCoordStr = dot.getAttribute("transform").split("(")[1].slice(0, -1);
		var groupAnim = translate(dot, oldCoordStr, [x, y], MARKER_LINE_ANIM_DUR);
		return [groupAnim];
	} else {
		return [[dot, { cx: x, cy: y }, UNIT_ANIM_DUR, STD_EASING]];
	}
	// dot.animate({cy: yTop}, UNIT_ANIM_DUR, mina.easein);
}

function animatePath(paths, newXList, newYList, zeroLine) {
	var pathComponents = [];

	var pointsStr = newYList.map(function (y, i) {
		return newXList[i] + ',' + y;
	});
	var pathStr = pointsStr.join("L");

	var animPath = [paths.path, { d: "M" + pathStr }, PATH_ANIM_DUR, STD_EASING];
	pathComponents.push(animPath);

	if (paths.region) {
		var regStartPt = newXList[0] + ',' + zeroLine + 'L';
		var regEndPt = 'L' + newXList.slice(-1)[0] + ', ' + zeroLine;

		var animRegion = [paths.region, { d: "M" + regStartPt + pathStr + regEndPt }, PATH_ANIM_DUR, STD_EASING];
		pathComponents.push(animRegion);
	}

	return pathComponents;
}

function animatePathStr(oldPath, pathStr) {
	return [oldPath, { d: pathStr }, UNIT_ANIM_DUR, STD_EASING];
}

// Leveraging SMIL Animations

var EASING = {
	ease: "0.25 0.1 0.25 1",
	linear: "0 0 1 1",
	// easein: "0.42 0 1 1",
	easein: "0.1 0.8 0.2 1",
	easeout: "0 0 0.58 1",
	easeinout: "0.42 0 0.58 1"
};

function animateSVGElement(element, props, dur) {
	var easingType = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : "linear";
	var type = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : undefined;
	var oldValues = arguments.length > 5 && arguments[5] !== undefined ? arguments[5] : {};


	var animElement = element.cloneNode(true);
	var newElement = element.cloneNode(true);

	for (var attributeName in props) {
		var animateElement = void 0;
		if (attributeName === 'transform') {
			animateElement = document.createElementNS("http://www.w3.org/2000/svg", "animateTransform");
		} else {
			animateElement = document.createElementNS("http://www.w3.org/2000/svg", "animate");
		}
		var currentValue = oldValues[attributeName] || element.getAttribute(attributeName);
		var value = props[attributeName];

		var animAttr = {
			attributeName: attributeName,
			from: currentValue,
			to: value,
			begin: "0s",
			dur: dur / 1000 + "s",
			values: currentValue + ";" + value,
			keySplines: EASING[easingType],
			keyTimes: "0;1",
			calcMode: "spline",
			fill: 'freeze'
		};

		if (type) {
			animAttr["type"] = type;
		}

		for (var i in animAttr) {
			animateElement.setAttribute(i, animAttr[i]);
		}

		animElement.appendChild(animateElement);

		if (type) {
			newElement.setAttribute(attributeName, "translate(" + value + ")");
		} else {
			newElement.setAttribute(attributeName, value);
		}
	}

	return [animElement, newElement];
}

function transform(element, style) {
	// eslint-disable-line no-unused-vars
	element.style.transform = style;
	element.style.webkitTransform = style;
	element.style.msTransform = style;
	element.style.mozTransform = style;
	element.style.oTransform = style;
}

function animateSVG(svgContainer, elements) {
	var newElements = [];
	var animElements = [];

	elements.map(function (element) {
		var unit = element[0];
		var parent = unit.parentNode;

		var animElement = void 0,
		    newElement = void 0;

		element[0] = unit;

		var _animateSVGElement = animateSVGElement.apply(undefined, toConsumableArray(element));

		var _animateSVGElement2 = slicedToArray(_animateSVGElement, 2);

		animElement = _animateSVGElement2[0];
		newElement = _animateSVGElement2[1];


		newElements.push(newElement);
		animElements.push([animElement, parent]);

		parent.replaceChild(animElement, unit);
	});

	var animSvg = svgContainer.cloneNode(true);

	animElements.map(function (animElement, i) {
		animElement[1].replaceChild(newElements[i], animElement[0]);
		elements[i][0] = newElements[i];
	});

	return animSvg;
}

function runSMILAnimation(parent, svgElement, elementsToAnimate) {
	if (elementsToAnimate.length === 0) return;

	var animSvgElement = animateSVG(svgElement, elementsToAnimate);
	if (svgElement.parentNode == parent) {
		parent.removeChild(svgElement);
		parent.appendChild(animSvgElement);
	}

	// Replace the new svgElement (data has already been replaced)
	setTimeout(function () {
		if (animSvgElement.parentNode == parent) {
			parent.removeChild(animSvgElement);
			parent.appendChild(svgElement);
		}
	}, REPLACE_ALL_NEW_DUR);
}

var BaseChart = function () {
	function BaseChart(parent, options) {
		classCallCheck(this, BaseChart);

		this.rawChartArgs = options;

		this.parent = typeof parent === 'string' ? document.querySelector(parent) : parent;
		if (!(this.parent instanceof HTMLElement)) {
			throw new Error('No `parent` element to render on was provided.');
		}

		this.title = options.title || '';
		this.subtitle = options.subtitle || '';
		this.argHeight = options.height || 240;
		this.type = options.type || '';

		this.realData = this.prepareData(options.data);
		this.data = this.prepareFirstData(this.realData);
		this.colors = [];
		this.config = {
			showTooltip: 1, // calculate
			showLegend: options.showLegend || 1,
			isNavigable: options.isNavigable || 0,
			animate: 1
		};
		this.state = {};
		this.options = {};

		this.initTimeout = INIT_CHART_UPDATE_TIMEOUT;

		if (this.config.isNavigable) {
			this.overlays = [];
		}

		this.configure(options);
	}

	createClass(BaseChart, [{
		key: 'configure',
		value: function configure(args) {
			var _this = this;

			this.setColors(args);
			this.setMargins();

			// Bind window events
			window.addEventListener('resize', function () {
				return _this.draw(true);
			});
			window.addEventListener('orientationchange', function () {
				return _this.draw(true);
			});
		}
	}, {
		key: 'setColors',
		value: function setColors() {
			var args = this.rawChartArgs;

			// Needs structure as per only labels/datasets, from config
			var list = args.type === 'percentage' || args.type === 'pie' ? args.data.labels : args.data.datasets;

			if (!args.colors || list && args.colors.length < list.length) {
				this.colors = DEFAULT_COLORS;
			} else {
				this.colors = args.colors;
			}

			this.colors = this.colors.map(function (color) {
				return getColor(color);
			});
		}
	}, {
		key: 'setMargins',
		value: function setMargins() {
			var height = this.argHeight;
			this.baseHeight = height;
			this.height = height - VERT_SPACE_OUTSIDE_BASE_CHART;
			this.translateY = TRANSLATE_Y_BASE_CHART;

			// Horizontal margins
			this.leftMargin = LEFT_MARGIN_BASE_CHART;
			this.rightMargin = RIGHT_MARGIN_BASE_CHART;
		}
	}, {
		key: 'validate',
		value: function validate() {
			return true;
		}
	}, {
		key: 'setup',
		value: function setup() {
			if (this.validate()) {
				this._setup();
			}
		}
	}, {
		key: '_setup',
		value: function _setup() {
			this.makeContainer();
			this.makeTooltip();

			this.draw(false, true);
		}
	}, {
		key: 'setupComponents',
		value: function setupComponents() {
			this.components = new Map();
		}
	}, {
		key: 'makeContainer',
		value: function makeContainer() {
			this.container = $.create('div', {
				className: 'chart-container',
				innerHTML: '<h6 class="title">' + this.title + '</h6>\n\t\t\t\t<h6 class="sub-title uppercase">' + this.subtitle + '</h6>\n\t\t\t\t<div class="frappe-chart graphics"></div>\n\t\t\t\t<div class="graph-stats-container"></div>'
			});

			// Chart needs a dedicated parent element
			this.parent.innerHTML = '';
			this.parent.appendChild(this.container);

			this.chartWrapper = this.container.querySelector('.frappe-chart');
			this.statsWrapper = this.container.querySelector('.graph-stats-container');
		}
	}, {
		key: 'makeTooltip',
		value: function makeTooltip() {
			this.tip = new SvgTip({
				parent: this.chartWrapper,
				colors: this.colors
			});
			this.bindTooltip();
		}
	}, {
		key: 'bindTooltip',
		value: function bindTooltip() {}
	}, {
		key: 'draw',
		value: function draw() {
			var _this2 = this;

			var onlyWidthChange = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : false;
			var init = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;

			this.calcWidth();
			this.calc(onlyWidthChange);
			this.makeChartArea();
			this.setupComponents();

			this.components.forEach(function (c) {
				return c.setup(_this2.drawArea);
			});
			// this.components.forEach(c => c.make());
			this.render(this.components, false);

			if (init) {
				this.data = this.realData;
				setTimeout(function () {
					_this2.update();
				}, this.initTimeout);
			}

			if (!onlyWidthChange) {
				this.renderLegend();
			}

			this.setupNavigation(init);
		}
	}, {
		key: 'calcWidth',
		value: function calcWidth() {
			this.baseWidth = getElementContentWidth(this.parent);
			this.width = this.baseWidth - (this.leftMargin + this.rightMargin);
		}
	}, {
		key: 'update',
		value: function update() {
			var data = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.data;

			this.data = this.prepareData(data);
			this.calc(); // builds state
			this.render();
		}
	}, {
		key: 'prepareData',
		value: function prepareData() {
			var data = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.data;

			return data;
		}
	}, {
		key: 'prepareFirstData',
		value: function prepareFirstData() {
			var data = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.data;

			return data;
		}
	}, {
		key: 'calc',
		value: function calc() {} // builds state

	}, {
		key: 'render',
		value: function render() {
			var _this3 = this;

			var components = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.components;
			var animate = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : true;

			if (this.config.isNavigable) {
				// Remove all existing overlays
				this.overlays.map(function (o) {
					return o.parentNode.removeChild(o);
				});
				// ref.parentNode.insertBefore(element, ref);
			}
			var elementsToAnimate = [];
			// Can decouple to this.refreshComponents() first to save animation timeout
			components.forEach(function (c) {
				elementsToAnimate = elementsToAnimate.concat(c.update(animate));
			});
			if (elementsToAnimate.length > 0) {
				runSMILAnimation(this.chartWrapper, this.svg, elementsToAnimate);
				setTimeout(function () {
					components.forEach(function (c) {
						return c.make();
					});
					_this3.updateNav();
				}, CHART_POST_ANIMATE_TIMEOUT);
			} else {
				components.forEach(function (c) {
					return c.make();
				});
				this.updateNav();
			}
		}
	}, {
		key: 'updateNav',
		value: function updateNav() {
			if (this.config.isNavigable) {
				// if(!this.overlayGuides){
				this.makeOverlay();
				this.bindUnits();
				// } else {
				// 	this.updateOverlay();
				// }
			}
		}
	}, {
		key: 'makeChartArea',
		value: function makeChartArea() {
			if (this.svg) {
				this.chartWrapper.removeChild(this.svg);
			}
			this.svg = makeSVGContainer(this.chartWrapper, 'chart', this.baseWidth, this.baseHeight);
			this.svgDefs = makeSVGDefs(this.svg);

			// I WISH !!!
			// this.svg = makeSVGGroup(
			// 	svgContainer,
			// 	'flipped-coord-system',
			// 	`translate(0, ${this.baseHeight}) scale(1, -1)`
			// );

			this.drawArea = makeSVGGroup(this.svg, this.type + '-chart', 'translate(' + this.leftMargin + ', ' + this.translateY + ')');
		}
	}, {
		key: 'renderLegend',
		value: function renderLegend() {}
	}, {
		key: 'setupNavigation',
		value: function setupNavigation() {
			var _this4 = this;

			var init = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : false;

			if (!this.config.isNavigable) return;

			if (init) {
				this.bindOverlay();

				this.keyActions = {
					'13': this.onEnterKey.bind(this),
					'37': this.onLeftArrow.bind(this),
					'38': this.onUpArrow.bind(this),
					'39': this.onRightArrow.bind(this),
					'40': this.onDownArrow.bind(this)
				};

				document.addEventListener('keydown', function (e) {
					if (isElementInViewport(_this4.chartWrapper)) {
						e = e || window.event;
						if (_this4.keyActions[e.keyCode]) {
							_this4.keyActions[e.keyCode]();
						}
					}
				});
			}
		}
	}, {
		key: 'makeOverlay',
		value: function makeOverlay$$1() {}
	}, {
		key: 'updateOverlay',
		value: function updateOverlay$$1() {}
	}, {
		key: 'bindOverlay',
		value: function bindOverlay() {}
	}, {
		key: 'bindUnits',
		value: function bindUnits() {}
	}, {
		key: 'onLeftArrow',
		value: function onLeftArrow() {}
	}, {
		key: 'onRightArrow',
		value: function onRightArrow() {}
	}, {
		key: 'onUpArrow',
		value: function onUpArrow() {}
	}, {
		key: 'onDownArrow',
		value: function onDownArrow() {}
	}, {
		key: 'onEnterKey',
		value: function onEnterKey() {}
	}, {
		key: 'addDataPoint',
		value: function addDataPoint() {}
	}, {
		key: 'removeDataPoint',
		value: function removeDataPoint() {}
	}, {
		key: 'getDataPoint',
		value: function getDataPoint() {}
	}, {
		key: 'setCurrentDataPoint',
		value: function setCurrentDataPoint() {}
	}, {
		key: 'updateDataset',
		value: function updateDataset() {}
	}, {
		key: 'getDifferentChart',
		value: function getDifferentChart$$1(type) {
			return getDifferentChart(type, this.type, this.parent, this.rawChartArgs);
		}
	}]);
	return BaseChart;
}();

var AggregationChart = function (_BaseChart) {
	inherits(AggregationChart, _BaseChart);

	function AggregationChart(parent, args) {
		classCallCheck(this, AggregationChart);
		return possibleConstructorReturn(this, (AggregationChart.__proto__ || Object.getPrototypeOf(AggregationChart)).call(this, parent, args));
	}

	createClass(AggregationChart, [{
		key: 'configure',
		value: function configure(args) {
			get(AggregationChart.prototype.__proto__ || Object.getPrototypeOf(AggregationChart.prototype), 'configure', this).call(this, args);

			this.config.maxSlices = args.maxSlices || 20;
			this.config.maxLegendPoints = args.maxLegendPoints || 20;
		}
	}, {
		key: 'calc',
		value: function calc() {
			var _this2 = this;

			var s = this.state;
			var maxSlices = this.config.maxSlices;
			s.sliceTotals = [];

			var allTotals = this.data.labels.map(function (label, i) {
				var total = 0;
				_this2.data.datasets.map(function (e) {
					total += e.values[i];
				});
				return [total, label];
			}).filter(function (d) {
				return d[0] > 0;
			}); // keep only positive results

			var totals = allTotals;
			if (allTotals.length > maxSlices) {
				// Prune and keep a grey area for rest as per maxSlices
				allTotals.sort(function (a, b) {
					return b[0] - a[0];
				});

				totals = allTotals.slice(0, maxSlices - 1);
				var remaining = allTotals.slice(maxSlices - 1);

				var sumOfRemaining = 0;
				remaining.map(function (d) {
					sumOfRemaining += d[0];
				});
				totals.push([sumOfRemaining, 'Rest']);
				this.colors[maxSlices - 1] = 'grey';
			}

			s.labels = [];
			totals.map(function (d) {
				s.sliceTotals.push(d[0]);
				s.labels.push(d[1]);
			});
		}
	}, {
		key: 'renderLegend',
		value: function renderLegend() {
			var _this3 = this;

			var s = this.state;

			this.statsWrapper.textContent = '';

			this.legendTotals = s.sliceTotals.slice(0, this.config.maxLegendPoints);

			var xValues = s.labels;
			this.legendTotals.map(function (d, i) {
				if (d) {
					var stats = $.create('div', {
						className: 'stats',
						inside: _this3.statsWrapper
					});
					stats.innerHTML = '<span class="indicator">\n\t\t\t\t\t<i style="background: ' + _this3.colors[i] + '"></i>\n\t\t\t\t\t<span class="text-muted">' + xValues[i] + ':</span>\n\t\t\t\t\t' + d + '\n\t\t\t\t</span>';
				}
			});
		}
	}]);
	return AggregationChart;
}(BaseChart);

var PercentageChart = function (_AggregationChart) {
	inherits(PercentageChart, _AggregationChart);

	function PercentageChart(parent, args) {
		classCallCheck(this, PercentageChart);

		var _this = possibleConstructorReturn(this, (PercentageChart.__proto__ || Object.getPrototypeOf(PercentageChart)).call(this, parent, args));

		_this.type = 'percentage';

		_this.setup();
		return _this;
	}

	createClass(PercentageChart, [{
		key: 'makeChartArea',
		value: function makeChartArea() {
			this.chartWrapper.className += ' ' + 'graph-focus-margin';
			this.chartWrapper.style.marginTop = '45px';

			this.statsWrapper.className += ' ' + 'graph-focus-margin';
			this.statsWrapper.style.marginBottom = '30px';
			this.statsWrapper.style.paddingTop = '0px';

			this.svg = $.create('div', {
				className: 'div',
				inside: this.chartWrapper
			});

			this.chart = $.create('div', {
				className: 'progress-chart',
				inside: this.svg
			});

			this.percentageBar = $.create('div', {
				className: 'progress',
				inside: this.chart
			});
		}
	}, {
		key: 'render',
		value: function render() {
			var _this2 = this;

			var s = this.state;
			this.grandTotal = s.sliceTotals.reduce(function (a, b) {
				return a + b;
			}, 0);
			s.slices = [];
			s.sliceTotals.map(function (total, i) {
				var slice = $.create('div', {
					className: 'progress-bar',
					'data-index': i,
					inside: _this2.percentageBar,
					styles: {
						background: _this2.colors[i],
						width: total * 100 / _this2.grandTotal + "%"
					}
				});
				s.slices.push(slice);
			});
		}
	}, {
		key: 'bindTooltip',
		value: function bindTooltip() {
			var _this3 = this;

			var s = this.state;

			this.chartWrapper.addEventListener('mousemove', function (e) {
				var slice = e.target;
				if (slice.classList.contains('progress-bar')) {

					var i = slice.getAttribute('data-index');
					var gOff = getOffset(_this3.chartWrapper),
					    pOff = getOffset(slice);

					var x = pOff.left - gOff.left + slice.offsetWidth / 2;
					var y = pOff.top - gOff.top - 6;
					var title = (_this3.formattedLabels && _this3.formattedLabels.length > 0 ? _this3.formattedLabels[i] : _this3.state.labels[i]) + ': ';
					var percent = (s.sliceTotals[i] * 100 / _this3.grandTotal).toFixed(1);

					_this3.tip.setValues(x, y, { name: title, value: percent + "%" });
					_this3.tip.showTip();
				}
			});
		}
	}]);
	return PercentageChart;
}(AggregationChart);

var ChartComponent = function () {
	function ChartComponent(_ref) {
		var _ref$layerClass = _ref.layerClass,
		    layerClass = _ref$layerClass === undefined ? '' : _ref$layerClass,
		    _ref$layerTransform = _ref.layerTransform,
		    layerTransform = _ref$layerTransform === undefined ? '' : _ref$layerTransform,
		    constants = _ref.constants,
		    getData = _ref.getData,
		    makeElements = _ref.makeElements,
		    animateElements = _ref.animateElements;
		classCallCheck(this, ChartComponent);

		this.layerTransform = layerTransform;
		this.constants = constants;

		this.makeElements = makeElements;
		this.getData = getData;

		this.animateElements = animateElements;

		this.store = [];

		this.layerClass = layerClass;
		this.layerClass = typeof this.layerClass === 'function' ? this.layerClass() : this.layerClass;

		this.refresh();
	}

	createClass(ChartComponent, [{
		key: 'refresh',
		value: function refresh(data) {
			this.data = data || this.getData();
		}
	}, {
		key: 'setup',
		value: function setup(parent) {
			this.layer = makeSVGGroup(parent, this.layerClass, this.layerTransform);
		}
	}, {
		key: 'make',
		value: function make() {
			this.render(this.data);
			this.oldData = this.data;
		}
	}, {
		key: 'render',
		value: function render(data) {
			var _this = this;

			this.store = this.makeElements(data);

			this.layer.textContent = '';
			this.store.forEach(function (element) {
				_this.layer.appendChild(element);
			});
		}
	}, {
		key: 'update',
		value: function update() {
			var animate = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : true;

			this.refresh();
			var animateElements = [];
			if (animate) {
				animateElements = this.animateElements(this.data);
			}
			return animateElements;
		}
	}]);
	return ChartComponent;
}();

var componentConfigs = {
	pieSlices: {
		layerClass: 'pie-slices',
		makeElements: function makeElements(data) {
			return data.sliceStrings.map(function (s, i) {
				var slice = makePath(s, 'pie-path', 'none', data.colors[i]);
				slice.style.transition = 'transform .3s;';
				return slice;
			});
		},
		animateElements: function animateElements(newData) {
			return this.store.map(function (slice, i) {
				return animatePathStr(slice, newData.sliceStrings[i]);
			});
		}
	},
	yAxis: {
		layerClass: 'y axis',
		makeElements: function makeElements(data) {
			var _this2 = this;

			return data.positions.map(function (position, i) {
				return yLine(position, data.labels[i], _this2.constants.width, { mode: _this2.constants.mode, pos: _this2.constants.pos });
			});
		},
		animateElements: function animateElements(newData) {
			var newPos = newData.positions;
			var newLabels = newData.labels;
			var oldPos = this.oldData.positions;
			var oldLabels = this.oldData.labels;

			var _equilizeNoOfElements = equilizeNoOfElements(oldPos, newPos);

			var _equilizeNoOfElements2 = slicedToArray(_equilizeNoOfElements, 2);

			oldPos = _equilizeNoOfElements2[0];
			newPos = _equilizeNoOfElements2[1];

			var _equilizeNoOfElements3 = equilizeNoOfElements(oldLabels, newLabels);

			var _equilizeNoOfElements4 = slicedToArray(_equilizeNoOfElements3, 2);

			oldLabels = _equilizeNoOfElements4[0];
			newLabels = _equilizeNoOfElements4[1];


			this.render({
				positions: oldPos,
				labels: newLabels
			});

			return this.store.map(function (line, i) {
				return translateHoriLine(line, newPos[i], oldPos[i]);
			});
		}
	},

	xAxis: {
		layerClass: 'x axis',
		makeElements: function makeElements(data) {
			var _this3 = this;

			return data.positions.map(function (position, i) {
				return xLine(position, data.calcLabels[i], _this3.constants.height, { mode: _this3.constants.mode, pos: _this3.constants.pos });
			});
		},
		animateElements: function animateElements(newData) {
			var newPos = newData.positions;
			var newLabels = newData.calcLabels;
			var oldPos = this.oldData.positions;
			var oldLabels = this.oldData.calcLabels;

			var _equilizeNoOfElements5 = equilizeNoOfElements(oldPos, newPos);

			var _equilizeNoOfElements6 = slicedToArray(_equilizeNoOfElements5, 2);

			oldPos = _equilizeNoOfElements6[0];
			newPos = _equilizeNoOfElements6[1];

			var _equilizeNoOfElements7 = equilizeNoOfElements(oldLabels, newLabels);

			var _equilizeNoOfElements8 = slicedToArray(_equilizeNoOfElements7, 2);

			oldLabels = _equilizeNoOfElements8[0];
			newLabels = _equilizeNoOfElements8[1];


			this.render({
				positions: oldPos,
				calcLabels: newLabels
			});

			return this.store.map(function (line, i) {
				return translateVertLine(line, newPos[i], oldPos[i]);
			});
		}
	},

	yMarkers: {
		layerClass: 'y-markers',
		makeElements: function makeElements(data) {
			var _this4 = this;

			return data.map(function (marker) {
				return yMarker(marker.position, marker.label, _this4.constants.width, { pos: 'right', mode: 'span', lineType: 'dashed' });
			});
		},
		animateElements: function animateElements(newData) {
			var _equilizeNoOfElements9 = equilizeNoOfElements(this.oldData, newData);

			var _equilizeNoOfElements10 = slicedToArray(_equilizeNoOfElements9, 2);

			this.oldData = _equilizeNoOfElements10[0];
			newData = _equilizeNoOfElements10[1];


			var newPos = newData.map(function (d) {
				return d.position;
			});
			var newLabels = newData.map(function (d) {
				return d.label;
			});

			var oldPos = this.oldData.map(function (d) {
				return d.position;
			});

			this.render(oldPos.map(function (pos, i) {
				return {
					position: oldPos[i],
					label: newLabels[i]
				};
			}));

			return this.store.map(function (line, i) {
				return translateHoriLine(line, newPos[i], oldPos[i]);
			});
		}
	},

	yRegions: {
		layerClass: 'y-regions',
		makeElements: function makeElements(data) {
			var _this5 = this;

			return data.map(function (region) {
				return yRegion(region.startPos, region.endPos, _this5.constants.width, region.label);
			});
		},
		animateElements: function animateElements(newData) {
			var _equilizeNoOfElements11 = equilizeNoOfElements(this.oldData, newData);

			var _equilizeNoOfElements12 = slicedToArray(_equilizeNoOfElements11, 2);

			this.oldData = _equilizeNoOfElements12[0];
			newData = _equilizeNoOfElements12[1];


			var newPos = newData.map(function (d) {
				return d.endPos;
			});
			var newLabels = newData.map(function (d) {
				return d.label;
			});
			var newStarts = newData.map(function (d) {
				return d.startPos;
			});

			var oldPos = this.oldData.map(function (d) {
				return d.endPos;
			});
			var oldStarts = this.oldData.map(function (d) {
				return d.startPos;
			});

			this.render(oldPos.map(function (pos, i) {
				return {
					startPos: oldStarts[i],
					endPos: oldPos[i],
					label: newLabels[i]
				};
			}));

			var animateElements = [];

			this.store.map(function (rectGroup, i) {
				animateElements = animateElements.concat(animateRegion(rectGroup, newStarts[i], newPos[i], oldPos[i]));
			});

			return animateElements;
		}
	},

	barGraph: {
		layerClass: function layerClass() {
			return 'dataset-units dataset-bars dataset-' + this.constants.index;
		},
		makeElements: function makeElements(data) {
			var c = this.constants;
			this.unitType = 'bar';
			this.units = data.yPositions.map(function (y, j) {
				return datasetBar(data.xPositions[j], y, data.barWidth, c.color, data.labels[j], j, data.offsets[j], {
					zeroLine: data.zeroLine,
					barsWidth: data.barsWidth,
					minHeight: c.minHeight
				});
			});
			return this.units;
		},
		animateElements: function animateElements(newData) {
			var newXPos = newData.xPositions;
			var newYPos = newData.yPositions;
			var newOffsets = newData.offsets;
			var newLabels = newData.labels;

			var oldXPos = this.oldData.xPositions;
			var oldYPos = this.oldData.yPositions;
			var oldOffsets = this.oldData.offsets;
			var oldLabels = this.oldData.labels;

			var _equilizeNoOfElements13 = equilizeNoOfElements(oldXPos, newXPos);

			var _equilizeNoOfElements14 = slicedToArray(_equilizeNoOfElements13, 2);

			oldXPos = _equilizeNoOfElements14[0];
			newXPos = _equilizeNoOfElements14[1];

			var _equilizeNoOfElements15 = equilizeNoOfElements(oldYPos, newYPos);

			var _equilizeNoOfElements16 = slicedToArray(_equilizeNoOfElements15, 2);

			oldYPos = _equilizeNoOfElements16[0];
			newYPos = _equilizeNoOfElements16[1];

			var _equilizeNoOfElements17 = equilizeNoOfElements(oldOffsets, newOffsets);

			var _equilizeNoOfElements18 = slicedToArray(_equilizeNoOfElements17, 2);

			oldOffsets = _equilizeNoOfElements18[0];
			newOffsets = _equilizeNoOfElements18[1];

			var _equilizeNoOfElements19 = equilizeNoOfElements(oldLabels, newLabels);

			var _equilizeNoOfElements20 = slicedToArray(_equilizeNoOfElements19, 2);

			oldLabels = _equilizeNoOfElements20[0];
			newLabels = _equilizeNoOfElements20[1];


			this.render({
				xPositions: oldXPos,
				yPositions: oldYPos,
				offsets: oldOffsets,
				labels: newLabels,

				zeroLine: this.oldData.zeroLine,
				barsWidth: this.oldData.barsWidth,
				barWidth: this.oldData.barWidth
			});

			var animateElements = [];

			this.store.map(function (bar, i) {
				animateElements = animateElements.concat(animateBar(bar, newXPos[i], newYPos[i], newData.barWidth, newOffsets[i], { zeroLine: newData.zeroLine }));
			});

			return animateElements;
		}
	},

	lineGraph: {
		layerClass: function layerClass() {
			return 'dataset-units dataset-line dataset-' + this.constants.index;
		},
		makeElements: function makeElements(data) {
			var c = this.constants;
			this.unitType = 'dot';
			this.paths = {};
			if (!c.hideLine) {
				this.paths = getPaths(data.xPositions, data.yPositions, c.color, {
					heatline: c.heatline,
					regionFill: c.regionFill
				}, {
					svgDefs: c.svgDefs,
					zeroLine: data.zeroLine
				});
			}

			this.units = [];
			if (!c.hideDots) {
				this.units = data.yPositions.map(function (y, j) {
					return datasetDot(data.xPositions[j], y, data.radius, c.color, c.valuesOverPoints ? data.values[j] : '', j);
				});
			}

			return Object.values(this.paths).concat(this.units);
		},
		animateElements: function animateElements(newData) {
			var newXPos = newData.xPositions;
			var newYPos = newData.yPositions;
			var newValues = newData.values;

			var oldXPos = this.oldData.xPositions;
			var oldYPos = this.oldData.yPositions;
			var oldValues = this.oldData.values;

			var _equilizeNoOfElements21 = equilizeNoOfElements(oldXPos, newXPos);

			var _equilizeNoOfElements22 = slicedToArray(_equilizeNoOfElements21, 2);

			oldXPos = _equilizeNoOfElements22[0];
			newXPos = _equilizeNoOfElements22[1];

			var _equilizeNoOfElements23 = equilizeNoOfElements(oldYPos, newYPos);

			var _equilizeNoOfElements24 = slicedToArray(_equilizeNoOfElements23, 2);

			oldYPos = _equilizeNoOfElements24[0];
			newYPos = _equilizeNoOfElements24[1];

			var _equilizeNoOfElements25 = equilizeNoOfElements(oldValues, newValues);

			var _equilizeNoOfElements26 = slicedToArray(_equilizeNoOfElements25, 2);

			oldValues = _equilizeNoOfElements26[0];
			newValues = _equilizeNoOfElements26[1];


			this.render({
				xPositions: oldXPos,
				yPositions: oldYPos,
				values: newValues,

				zeroLine: this.oldData.zeroLine,
				radius: this.oldData.radius
			});

			var animateElements = [];

			if (Object.keys(this.paths).length) {
				animateElements = animateElements.concat(animatePath(this.paths, newXPos, newYPos, newData.zeroLine));
			}

			if (this.units.length) {
				this.units.map(function (dot, i) {
					animateElements = animateElements.concat(animateDot(dot, newXPos[i], newYPos[i]));
				});
			}

			return animateElements;
		}
	}
};

function getComponent(name, constants, getData) {
	var keys = Object.keys(componentConfigs).filter(function (k) {
		return name.includes(k);
	});
	var config = componentConfigs[keys[0]];
	Object.assign(config, {
		constants: constants,
		getData: getData
	});
	return new ChartComponent(config);
}

var PieChart = function (_AggregationChart) {
	inherits(PieChart, _AggregationChart);

	function PieChart(parent, args) {
		classCallCheck(this, PieChart);

		var _this = possibleConstructorReturn(this, (PieChart.__proto__ || Object.getPrototypeOf(PieChart)).call(this, parent, args));

		_this.type = 'pie';
		_this.initTimeout = 0;

		_this.setup();
		return _this;
	}

	createClass(PieChart, [{
		key: 'configure',
		value: function configure(args) {
			get(PieChart.prototype.__proto__ || Object.getPrototypeOf(PieChart.prototype), 'configure', this).call(this, args);
			this.mouseMove = this.mouseMove.bind(this);
			this.mouseLeave = this.mouseLeave.bind(this);

			this.hoverRadio = args.hoverRadio || 0.1;
			this.config.startAngle = args.startAngle || 0;

			this.clockWise = args.clockWise || false;
		}
	}, {
		key: 'prepareFirstData',
		value: function prepareFirstData() {
			var data = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.data;

			this.init = 1;
			return data;
		}
	}, {
		key: 'calc',
		value: function calc() {
			get(PieChart.prototype.__proto__ || Object.getPrototypeOf(PieChart.prototype), 'calc', this).call(this);
			var s = this.state;

			this.center = {
				x: this.width / 2,
				y: this.height / 2
			};
			this.radius = this.height > this.width ? this.center.x : this.center.y;

			s.grandTotal = s.sliceTotals.reduce(function (a, b) {
				return a + b;
			}, 0);

			this.calcSlices();
		}
	}, {
		key: 'calcSlices',
		value: function calcSlices() {
			var _this2 = this;

			var s = this.state;
			var radius = this.radius,
			    clockWise = this.clockWise;


			var prevSlicesProperties = s.slicesProperties || [];
			s.sliceStrings = [];
			s.slicesProperties = [];
			var curAngle = 180 - this.config.startAngle;

			s.sliceTotals.map(function (total, i) {
				var startAngle = curAngle;
				var originDiffAngle = total / s.grandTotal * FULL_ANGLE;
				var diffAngle = clockWise ? -originDiffAngle : originDiffAngle;
				var endAngle = curAngle = curAngle + diffAngle;
				var startPosition = getPositionByAngle(startAngle, radius);
				var endPosition = getPositionByAngle(endAngle, radius);

				var prevProperty = _this2.init && prevSlicesProperties[i];

				var curStart = void 0,
				    curEnd = void 0;
				if (_this2.init) {
					curStart = prevProperty ? prevProperty.startPosition : startPosition;
					curEnd = prevProperty ? prevProperty.endPosition : startPosition;
				} else {
					curStart = startPosition;
					curEnd = endPosition;
				}
				var curPath = makeArcPathStr(curStart, curEnd, _this2.center, _this2.radius, _this2.clockWise);

				s.sliceStrings.push(curPath);
				s.slicesProperties.push({
					startPosition: startPosition,
					endPosition: endPosition,
					value: total,
					total: s.grandTotal,
					startAngle: startAngle,
					endAngle: endAngle,
					angle: diffAngle
				});
			});
			this.init = 0;
		}
	}, {
		key: 'setupComponents',
		value: function setupComponents() {
			var s = this.state;

			var componentConfigs = [['pieSlices', {}, function () {
				return {
					sliceStrings: s.sliceStrings,
					colors: this.colors
				};
			}.bind(this)]];

			this.components = new Map(componentConfigs.map(function (args) {
				var component = getComponent.apply(undefined, toConsumableArray(args));
				return [args[0], component];
			}));
		}
	}, {
		key: 'calTranslateByAngle',
		value: function calTranslateByAngle(property) {
			var radius = this.radius,
			    hoverRadio = this.hoverRadio;

			var position = getPositionByAngle(property.startAngle + property.angle / 2, radius);
			return 'translate3d(' + position.x * hoverRadio + 'px,' + position.y * hoverRadio + 'px,0)';
		}
	}, {
		key: 'hoverSlice',
		value: function hoverSlice(path, i, flag, e) {
			if (!path) return;
			var color = this.colors[i];
			if (flag) {
				transform(path, this.calTranslateByAngle(this.state.slicesProperties[i]));
				path.style.fill = lightenDarkenColor(color, 50);
				var g_off = getOffset(this.svg);
				var x = e.pageX - g_off.left + 10;
				var y = e.pageY - g_off.top - 10;
				var title = (this.formatted_labels && this.formatted_labels.length > 0 ? this.formatted_labels[i] : this.state.labels[i]) + ': ';
				var percent = (this.state.sliceTotals[i] * 100 / this.state.grandTotal).toFixed(1);
				this.tip.setValues(x, y, { name: title, value: percent + "%" });
				this.tip.showTip();
			} else {
				transform(path, 'translate3d(0,0,0)');
				this.tip.hideTip();
				path.style.fill = color;
			}
		}
	}, {
		key: 'bindTooltip',
		value: function bindTooltip() {
			this.chartWrapper.addEventListener('mousemove', this.mouseMove);
			this.chartWrapper.addEventListener('mouseleave', this.mouseLeave);
		}
	}, {
		key: 'mouseMove',
		value: function mouseMove(e) {
			var target = e.target;
			var slices = this.components.get('pieSlices').store;
			var prevIndex = this.curActiveSliceIndex;
			var prevAcitve = this.curActiveSlice;
			if (slices.includes(target)) {
				var i = slices.indexOf(target);
				this.hoverSlice(prevAcitve, prevIndex, false);
				this.curActiveSlice = target;
				this.curActiveSliceIndex = i;
				this.hoverSlice(target, i, true, e);
			} else {
				this.mouseLeave();
			}
		}
	}, {
		key: 'mouseLeave',
		value: function mouseLeave() {
			this.hoverSlice(this.curActiveSlice, this.curActiveSliceIndex, false);
		}
	}]);
	return PieChart;
}(AggregationChart);

// Playing around with dates

// https://stackoverflow.com/a/11252167/6495043
function treatAsUtc(dateStr) {
	var result = new Date(dateStr);
	result.setMinutes(result.getMinutes() - result.getTimezoneOffset());
	return result;
}

function getDdMmYyyy(date) {
	var dd = date.getDate();
	var mm = date.getMonth() + 1; // getMonth() is zero-based
	return [(dd > 9 ? '' : '0') + dd, (mm > 9 ? '' : '0') + mm, date.getFullYear()].join('-');
}

function getWeeksBetween(startDateStr, endDateStr) {
	return Math.ceil(getDaysBetween(startDateStr, endDateStr) / 7);
}

function getDaysBetween(startDateStr, endDateStr) {
	var millisecondsPerDay = 24 * 60 * 60 * 1000;
	return (treatAsUtc(endDateStr) - treatAsUtc(startDateStr)) / millisecondsPerDay;
}

// mutates
function addDays(date, numberOfDays) {
	date.setDate(date.getDate() + numberOfDays);
}

function normalize(x) {
	// Calculates mantissa and exponent of a number
	// Returns normalized number and exponent
	// https://stackoverflow.com/q/9383593/6495043

	if (x === 0) {
		return [0, 0];
	}
	if (isNaN(x)) {
		return { mantissa: -6755399441055744, exponent: 972 };
	}
	var sig = x > 0 ? 1 : -1;
	if (!isFinite(x)) {
		return { mantissa: sig * 4503599627370496, exponent: 972 };
	}

	x = Math.abs(x);
	var exp = Math.floor(Math.log10(x));
	var man = x / Math.pow(10, exp);

	return [sig * man, exp];
}

function getChartRangeIntervals(max) {
	var min = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 0;

	var upperBound = Math.ceil(max);
	var lowerBound = Math.floor(min);
	var range = upperBound - lowerBound;

	var noOfParts = range;
	var partSize = 1;

	// To avoid too many partitions
	if (range > 5) {
		if (range % 2 !== 0) {
			upperBound++;
			// Recalc range
			range = upperBound - lowerBound;
		}
		noOfParts = range / 2;
		partSize = 2;
	}

	// Special case: 1 and 2
	if (range <= 2) {
		noOfParts = 4;
		partSize = range / noOfParts;
	}

	// Special case: 0
	if (range === 0) {
		noOfParts = 5;
		partSize = 1;
	}

	var intervals = [];
	for (var i = 0; i <= noOfParts; i++) {
		intervals.push(lowerBound + partSize * i);
	}
	return intervals;
}

function getChartIntervals(maxValue) {
	var minValue = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 0;

	var _normalize = normalize(maxValue),
	    _normalize2 = slicedToArray(_normalize, 2),
	    normalMaxValue = _normalize2[0],
	    exponent = _normalize2[1];

	var normalMinValue = minValue ? minValue / Math.pow(10, exponent) : 0;

	// Allow only 7 significant digits
	normalMaxValue = normalMaxValue.toFixed(6);

	var intervals = getChartRangeIntervals(normalMaxValue, normalMinValue);
	intervals = intervals.map(function (value) {
		return value * Math.pow(10, exponent);
	});
	return intervals;
}

function calcChartIntervals(values) {
	var withMinimum = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;

	//*** Where the magic happens ***

	// Calculates best-fit y intervals from given values
	// and returns the interval array

	var maxValue = Math.max.apply(Math, toConsumableArray(values));
	var minValue = Math.min.apply(Math, toConsumableArray(values));

	// Exponent to be used for pretty print
	var exponent = 0,
	    intervals = []; // eslint-disable-line no-unused-vars

	function getPositiveFirstIntervals(maxValue, absMinValue) {
		var intervals = getChartIntervals(maxValue);

		var intervalSize = intervals[1] - intervals[0];

		// Then unshift the negative values
		var value = 0;
		for (var i = 1; value < absMinValue; i++) {
			value += intervalSize;
			intervals.unshift(-1 * value);
		}
		return intervals;
	}

	// CASE I: Both non-negative

	if (maxValue >= 0 && minValue >= 0) {
		exponent = normalize(maxValue)[1];
		if (!withMinimum) {
			intervals = getChartIntervals(maxValue);
		} else {
			intervals = getChartIntervals(maxValue, minValue);
		}
	}

	// CASE II: Only minValue negative

	else if (maxValue > 0 && minValue < 0) {
			// `withMinimum` irrelevant in this case,
			// We'll be handling both sides of zero separately
			// (both starting from zero)
			// Because ceil() and floor() behave differently
			// in those two regions

			var absMinValue = Math.abs(minValue);

			if (maxValue >= absMinValue) {
				exponent = normalize(maxValue)[1];
				intervals = getPositiveFirstIntervals(maxValue, absMinValue);
			} else {
				// Mirror: maxValue => absMinValue, then change sign
				exponent = normalize(absMinValue)[1];
				var posIntervals = getPositiveFirstIntervals(absMinValue, maxValue);
				intervals = posIntervals.map(function (d) {
					return d * -1;
				});
			}
		}

		// CASE III: Both non-positive

		else if (maxValue <= 0 && minValue <= 0) {
				// Mirrored Case I:
				// Work with positives, then reverse the sign and array

				var pseudoMaxValue = Math.abs(minValue);
				var pseudoMinValue = Math.abs(maxValue);

				exponent = normalize(pseudoMaxValue)[1];
				if (!withMinimum) {
					intervals = getChartIntervals(pseudoMaxValue);
				} else {
					intervals = getChartIntervals(pseudoMaxValue, pseudoMinValue);
				}

				intervals = intervals.reverse().map(function (d) {
					return d * -1;
				});
			}

	return intervals;
}

function getZeroIndex(yPts) {
	var zeroIndex = void 0;
	var interval = getIntervalSize(yPts);
	if (yPts.indexOf(0) >= 0) {
		// the range has a given zero
		// zero-line on the chart
		zeroIndex = yPts.indexOf(0);
	} else if (yPts[0] > 0) {
		// Minimum value is positive
		// zero-line is off the chart: below
		var min = yPts[0];
		zeroIndex = -1 * min / interval;
	} else {
		// Maximum value is negative
		// zero-line is off the chart: above
		var max = yPts[yPts.length - 1];
		zeroIndex = -1 * max / interval + (yPts.length - 1);
	}
	return zeroIndex;
}



function getIntervalSize(orderedArray) {
	return orderedArray[1] - orderedArray[0];
}

function getValueRange(orderedArray) {
	return orderedArray[orderedArray.length - 1] - orderedArray[0];
}

function scale(val, yAxis) {
	return floatTwo(yAxis.zeroLine - val * yAxis.scaleMultiplier);
}

function calcDistribution(values, distributionSize) {
	// Assume non-negative values,
	// implying distribution minimum at zero
	if(!values.length) values = [0];

	var dataMaxValue = Math.max.apply(Math, toConsumableArray(values));

	var distributionStep = 1 / (distributionSize - 1);
	var distribution = [];

	for (var i = 0; i < distributionSize; i++) {
		var checkpoint = dataMaxValue * (distributionStep * i);
		distribution.push(checkpoint);
	}

	return distribution;
}

function getMaxCheckpoint(value, distribution) {
	return distribution.filter(function (d) {
		return d < value;
	}).length;
}

var Heatmap = function (_BaseChart) {
	inherits(Heatmap, _BaseChart);

	function Heatmap(parent, options) {
		classCallCheck(this, Heatmap);

		var _this = possibleConstructorReturn(this, (Heatmap.__proto__ || Object.getPrototypeOf(Heatmap)).call(this, parent, options));

		_this.type = 'heatmap';

		_this.domain = options.domain || '';
		_this.subdomain = options.subdomain || '';
		_this.data = options.data || {};
		_this.discreteDomains = options.discreteDomains === 0 ? 0 : 1;
		_this.countLabel = options.countLabel || '';

		var today = new Date();
		_this.start = options.start || addDays(today, 365);

		var legendColors = (options.legendColors || []).slice(0, 5);
		_this.legendColors = _this.validate_colors(legendColors) ? legendColors : ['#ebedf0', '#c6e48b', '#7bc96f', '#239a3b', '#196127'];

		// Fixed 5-color theme,
		// More colors are difficult to parse visually
		_this.distribution_size = 5;

		_this.translateX = 0;
		_this.setup();
		return _this;
	}

	createClass(Heatmap, [{
		key: 'setMargins',
		value: function setMargins() {
			get(Heatmap.prototype.__proto__ || Object.getPrototypeOf(Heatmap.prototype), 'setMargins', this).call(this);
			this.leftMargin = 10;
			this.translateY = 10;
		}
	}, {
		key: 'validate_colors',
		value: function validate_colors(colors) {
			if (colors.length < 5) return 0;

			var valid = 1;
			colors.forEach(function (string) {
				if (!isValidColor(string)) {
					valid = 0;
					console.warn('"' + string + '" is not a valid color.');
				}
			}, this);

			return valid;
		}
	}, {
		key: 'configure',
		value: function configure() {
			get(Heatmap.prototype.__proto__ || Object.getPrototypeOf(Heatmap.prototype), 'configure', this).call(this);
			this.today = new Date();

			if (!this.start) {
				this.start = new Date();
				this.start.setFullYear(this.start.getFullYear() - 1);
			}
			this.firstWeekStart = new Date(this.start.toDateString());
			this.lastWeekStart = new Date(this.today.toDateString());
			if (this.firstWeekStart.getDay() !== 7) {
				addDays(this.firstWeekStart, -1 * this.firstWeekStart.getDay());
			}
			if (this.lastWeekStart.getDay() !== 7) {
				addDays(this.lastWeekStart, -1 * this.lastWeekStart.getDay());
			}
			this.no_of_cols = getWeeksBetween(this.firstWeekStart + '', this.lastWeekStart + '') + 1;
		}
	}, {
		key: 'calcWidth',
		value: function calcWidth() {
			this.baseWidth = (this.no_of_cols + 3) * 12;

			if (this.discreteDomains) {
				this.baseWidth += 12 * 12;
			}
		}
	}, {
		key: 'makeChartArea',
		value: function makeChartArea() {
			get(Heatmap.prototype.__proto__ || Object.getPrototypeOf(Heatmap.prototype), 'makeChartArea', this).call(this);
			this.domainLabelGroup = makeSVGGroup(this.drawArea, 'domain-label-group chart-label');

			this.dataGroups = makeSVGGroup(this.drawArea, 'data-groups', 'translate(0, 20)');

			this.container.querySelector('.title').style.display = 'None';
			this.container.querySelector('.sub-title').style.display = 'None';
			this.container.querySelector('.graph-stats-container').style.display = 'None';
			this.chartWrapper.style.marginTop = '0px';
			this.chartWrapper.style.paddingTop = '0px';
		}
	}, {
		key: 'calc',
		value: function calc() {
			var _this2 = this;

			this.dataPoints = {};
			Object.keys(this.data).map(function (key) {
				var date = new Date(key * 1000);
				var ddmmyyyy = getDdMmYyyy(date);
				_this2.dataPoints[ddmmyyyy] = _this2.data[key];
			});

			var dataValues = Object.values(this.data);
			this.distribution = calcDistribution(dataValues, this.distribution_size);

			this.monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
		}
	}, {
		key: 'render',
		value: function render() {
			this.renderAllWeeksAndStoreXValues(this.no_of_cols);
		}
	}, {
		key: 'renderAllWeeksAndStoreXValues',
		value: function renderAllWeeksAndStoreXValues(no_of_weeks) {
			// renderAllWeeksAndStoreXValues
			this.domainLabelGroup.textContent = '';
			this.dataGroups.textContent = '';

			var currentWeekSunday = new Date(this.firstWeekStart);
			this.weekCol = 0;
			this.currentMonth = currentWeekSunday.getMonth();

			this.months = [this.currentMonth + ''];
			this.monthWeeks = {}, this.monthStartPoints = [];
			this.monthWeeks[this.currentMonth] = 0;
			this.monthStartPoints.push(13);

			for (var i = 0; i < no_of_weeks; i++) {
				var dataGroup = void 0,
				    monthChange = 0;
				var day = new Date(currentWeekSunday);

				var _get_week_squares_gro = this.get_week_squares_group(day, this.weekCol);

				var _get_week_squares_gro2 = slicedToArray(_get_week_squares_gro, 2);

				dataGroup = _get_week_squares_gro2[0];
				monthChange = _get_week_squares_gro2[1];

				this.dataGroups.appendChild(dataGroup);
				this.weekCol += 1 + parseInt(this.discreteDomains && monthChange);
				this.monthWeeks[this.currentMonth]++;
				if (monthChange) {
					this.currentMonth = (this.currentMonth + 1) % 12;
					this.months.push(this.currentMonth + '');
					this.monthWeeks[this.currentMonth] = 1;
				}
				addDays(currentWeekSunday, 7);
			}
			this.render_month_labels();
		}
	}, {
		key: 'get_week_squares_group',
		value: function get_week_squares_group(currentDate, index) {
			var noOfWeekdays = 7;
			var squareSide = 10;
			var cellPadding = 2;
			var step = 1;
			var todayTime = this.today.getTime();

			var monthChange = 0;
			var weekColChange = 0;

			var dataGroup = makeSVGGroup(this.dataGroups, 'data-group');

			for (var y = 0, i = 0; i < noOfWeekdays; i += step, y += squareSide + cellPadding) {
				var ddmmyyyy = getDdMmYyyy(currentDate);

				var dataValue = this.dataPoints[ddmmyyyy] ? this.dataPoints[ddmmyyyy] : 0;
				var colorIndex = getMaxCheckpoint(dataValue, this.distribution);
				var x = 13 + (index + weekColChange) * 12;

				var dataAttr = {
					'data-date': ddmmyyyy,
					'data-value': dataValue,
					'data-day': currentDate.getDay()
				};

				var heatSquare = makeHeatSquare('day', x, y, squareSide, this.legendColors[colorIndex], dataAttr);

				dataGroup.appendChild(heatSquare);

				var nextDate = new Date(currentDate);
				addDays(nextDate, 1);
				if (nextDate.getTime() > todayTime) break;

				if (nextDate.getMonth() - currentDate.getMonth()) {
					monthChange = 1;
					if (this.discreteDomains) {
						weekColChange = 1;
					}

					this.monthStartPoints.push(13 + (index + weekColChange) * 12);
				}
				currentDate = nextDate;
			}

			return [dataGroup, monthChange];
		}
	}, {
		key: 'render_month_labels',
		value: function render_month_labels() {
			var _this3 = this;

			// this.first_month_label = 1;
			// if (this.firstWeekStart.getDate() > 8) {
			// 	this.first_month_label = 0;
			// }
			// this.last_month_label = 1;

			// let first_month = this.months.shift();
			// let first_month_start = this.monthStartPoints.shift();
			// render first month if

			// let last_month = this.months.pop();
			// let last_month_start = this.monthStartPoints.pop();
			// render last month if

			this.months.shift();
			this.monthStartPoints.shift();
			this.months.pop();
			this.monthStartPoints.pop();

			this.monthStartPoints.map(function (start, i) {
				var month_name = _this3.monthNames[_this3.months[i]].substring(0, 3);
				var text = makeText('y-value-text', start + 12, 10, month_name);
				_this3.domainLabelGroup.appendChild(text);
			});
		}
	}, {
		key: 'bindTooltip',
		value: function bindTooltip() {
			var _this4 = this;

			Array.prototype.slice.call(document.querySelectorAll(".data-group .day")).map(function (el) {
				el.addEventListener('mouseenter', function (e) {
					var count = e.target.getAttribute('data-value');
					var dateParts = e.target.getAttribute('data-date').split('-');

					var month = _this4.monthNames[parseInt(dateParts[1]) - 1].substring(0, 3);

					var gOff = _this4.chartWrapper.getBoundingClientRect(),
					    pOff = e.target.getBoundingClientRect();

					var width = parseInt(e.target.getAttribute('width'));
					var x = pOff.left - gOff.left + (width + 2) / 2;
					var y = pOff.top - gOff.top - (width + 2) / 2;
					var value = count + ' ' + _this4.countLabel;
					var name = ' on ' + month + ' ' + dateParts[0] + ', ' + dateParts[2];

					_this4.tip.setValues(x, y, { name: name, value: value, valueFirst: 1 }, []);
					_this4.tip.showTip();
				});
			});
		}
	}, {
		key: 'update',
		value: function update(data) {
			this.data = this.prepareData(data);
			this.draw();
			this.bindTooltip();
		}
	}]);
	return Heatmap;
}(BaseChart);

function dataPrep(data, type) {
	data.labels = data.labels || [];

	var datasetLength = data.labels.length;

	// Datasets
	var datasets = data.datasets;
	var zeroArray = new Array(datasetLength).fill(0);
	if (!datasets) {
		// default
		datasets = [{
			values: zeroArray
		}];
	}

	datasets.map(function (d) {
		// Set values
		if (!d.values) {
			d.values = zeroArray;
		} else {
			// Check for non values
			var vals = d.values;
			vals = vals.map(function (val) {
				return !isNaN(val) ? val : 0;
			});

			// Trim or extend
			if (vals.length > datasetLength) {
				vals = vals.slice(0, datasetLength);
			} else {
				vals = fillArray(vals, datasetLength - vals.length, 0);
			}
		}

		// Set labels
		//

		// Set type
		if (!d.chartType) {
			if (!AXIS_DATASET_CHART_TYPES.includes(type)) type === DEFAULT_AXIS_CHART_TYPE;
			d.chartType = type;
		}
	});

	// Markers

	// Regions
	// data.yRegions = data.yRegions || [];
	if (data.yRegions) {
		data.yRegions.map(function (d) {
			if (d.end < d.start) {
				var _ref = [d.end, d.start];
				d.start = _ref[0];
				d.end = _ref[1];
			}
		});
	}

	return data;
}

function zeroDataPrep(realData) {
	var datasetLength = realData.labels.length;
	var zeroArray = new Array(datasetLength).fill(0);

	var zeroData = {
		labels: realData.labels.slice(0, -1),
		datasets: realData.datasets.map(function (d) {
			return {
				name: '',
				values: zeroArray.slice(0, -1),
				chartType: d.chartType
			};
		})
	};

	if (realData.yMarkers) {
		zeroData.yMarkers = [{
			value: 0,
			label: ''
		}];
	}

	if (realData.yRegions) {
		zeroData.yRegions = [{
			start: 0,
			end: 0,
			label: ''
		}];
	}

	return zeroData;
}

function getShortenedLabels(chartWidth) {
	var labels = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : [];
	var isSeries = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : true;

	var allowedSpace = chartWidth / labels.length;
	var allowedLetters = allowedSpace / DEFAULT_CHAR_WIDTH;

	var calcLabels = labels.map(function (label, i) {
		label += "";
		if (label.length > allowedLetters) {

			if (!isSeries) {
				if (allowedLetters - 3 > 0) {
					label = label.slice(0, allowedLetters - 3) + " ...";
				} else {
					label = label.slice(0, allowedLetters) + '..';
				}
			} else {
				var multiple = Math.ceil(label.length / allowedLetters);
				if (i % multiple !== 0) {
					label = "";
				}
			}
		}
		return label;
	});

	return calcLabels;
}

var AxisChart = function (_BaseChart) {
	inherits(AxisChart, _BaseChart);

	function AxisChart(parent, args) {
		classCallCheck(this, AxisChart);

		var _this = possibleConstructorReturn(this, (AxisChart.__proto__ || Object.getPrototypeOf(AxisChart)).call(this, parent, args));

		_this.barOptions = args.barOptions || {};
		_this.lineOptions = args.lineOptions || {};

		_this.type = args.type || 'line';
		_this.init = 1;

		_this.setup();
		return _this;
	}

	createClass(AxisChart, [{
		key: 'configure',
		value: function configure(args) {
			get(AxisChart.prototype.__proto__ || Object.getPrototypeOf(AxisChart.prototype), 'configure', this).call(this);

			args.axisOptions = args.axisOptions || {};
			args.tooltipOptions = args.tooltipOptions || {};

			this.config.xAxisMode = args.axisOptions.xAxisMode || 'span';
			this.config.yAxisMode = args.axisOptions.yAxisMode || 'span';
			this.config.xIsSeries = args.axisOptions.xIsSeries || 0;

			this.config.formatTooltipX = args.tooltipOptions.formatTooltipX;
			this.config.formatTooltipY = args.tooltipOptions.formatTooltipY;

			this.config.valuesOverPoints = args.valuesOverPoints;
		}
	}, {
		key: 'setMargins',
		value: function setMargins() {
			get(AxisChart.prototype.__proto__ || Object.getPrototypeOf(AxisChart.prototype), 'setMargins', this).call(this);
			this.leftMargin = Y_AXIS_MARGIN;
			this.rightMargin = Y_AXIS_MARGIN;
		}
	}, {
		key: 'prepareData',
		value: function prepareData() {
			var data = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.data;

			return dataPrep(data, this.type);
		}
	}, {
		key: 'prepareFirstData',
		value: function prepareFirstData() {
			var data = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.data;

			return zeroDataPrep(data);
		}
	}, {
		key: 'calc',
		value: function calc() {
			var onlyWidthChange = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : false;

			this.calcXPositions();
			if (onlyWidthChange) return;
			this.calcYAxisParameters(this.getAllYValues(), this.type === 'line');
		}
	}, {
		key: 'calcXPositions',
		value: function calcXPositions() {
			var s = this.state;
			var labels = this.data.labels;
			s.datasetLength = labels.length;

			s.unitWidth = this.width / s.datasetLength;
			// Default, as per bar, and mixed. Only line will be a special case
			s.xOffset = s.unitWidth / 2;

			// // For a pure Line Chart
			// s.unitWidth = this.width/(s.datasetLength - 1);
			// s.xOffset = 0;

			s.xAxis = {
				labels: labels,
				positions: labels.map(function (d, i) {
					return floatTwo(s.xOffset + i * s.unitWidth);
				})
			};
		}
	}, {
		key: 'calcYAxisParameters',
		value: function calcYAxisParameters(dataValues) {
			var withMinimum = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 'false';

			var yPts = calcChartIntervals(dataValues, withMinimum);
			var scaleMultiplier = this.height / getValueRange(yPts);
			var intervalHeight = getIntervalSize(yPts) * scaleMultiplier;
			var zeroLine = this.height - getZeroIndex(yPts) * intervalHeight;

			this.state.yAxis = {
				labels: yPts,
				positions: yPts.map(function (d) {
					return zeroLine - d * scaleMultiplier;
				}),
				scaleMultiplier: scaleMultiplier,
				zeroLine: zeroLine
			};

			// Dependent if above changes
			this.calcDatasetPoints();
			this.calcYExtremes();
			this.calcYRegions();
		}
	}, {
		key: 'calcDatasetPoints',
		value: function calcDatasetPoints() {
			var s = this.state;
			var scaleAll = function scaleAll(values) {
				return values.map(function (val) {
					return scale(val, s.yAxis);
				});
			};

			s.datasets = this.data.datasets.map(function (d, i) {
				var values = d.values;
				var cumulativeYs = d.cumulativeYs || [];
				return {
					name: d.name,
					index: i,
					chartType: d.chartType,

					values: values,
					yPositions: scaleAll(values),

					cumulativeYs: cumulativeYs,
					cumulativeYPos: scaleAll(cumulativeYs)
				};
			});
		}
	}, {
		key: 'calcYExtremes',
		value: function calcYExtremes() {
			var s = this.state;
			if (this.barOptions.stacked) {
				s.yExtremes = s.datasets[s.datasets.length - 1].cumulativeYPos;
				return;
			}
			s.yExtremes = new Array(s.datasetLength).fill(9999);
			s.datasets.map(function (d) {
				d.yPositions.map(function (pos, j) {
					if (pos < s.yExtremes[j]) {
						s.yExtremes[j] = pos;
					}
				});
			});
		}
	}, {
		key: 'calcYRegions',
		value: function calcYRegions() {
			var s = this.state;
			if (this.data.yMarkers) {
				this.state.yMarkers = this.data.yMarkers.map(function (d) {
					d.position = scale(d.value, s.yAxis);
					// if(!d.label.includes(':')) {
					// 	d.label += ': ' + d.value;
					// }
					return d;
				});
			}
			if (this.data.yRegions) {
				this.state.yRegions = this.data.yRegions.map(function (d) {
					d.startPos = scale(d.start, s.yAxis);
					d.endPos = scale(d.end, s.yAxis);
					return d;
				});
			}
		}
	}, {
		key: 'getAllYValues',
		value: function getAllYValues() {
			var _this2 = this,
			    _ref;

			// TODO: yMarkers, regions, sums, every Y value ever
			var key = 'values';

			if (this.barOptions.stacked) {
				key = 'cumulativeYs';
				var cumulative = new Array(this.state.datasetLength).fill(0);
				this.data.datasets.map(function (d, i) {
					var values = _this2.data.datasets[i].values;
					d[key] = cumulative = cumulative.map(function (c, i) {
						return c + values[i];
					});
				});
			}

			var allValueLists = this.data.datasets.map(function (d) {
				return d[key];
			});
			if (this.data.yMarkers) {
				allValueLists.push(this.data.yMarkers.map(function (d) {
					return d.value;
				}));
			}
			if (this.data.yRegions) {
				this.data.yRegions.map(function (d) {
					allValueLists.push([d.end, d.start]);
				});
			}

			return (_ref = []).concat.apply(_ref, toConsumableArray(allValueLists));
		}
	}, {
		key: 'setupComponents',
		value: function setupComponents() {
			var _this3 = this;

			var componentConfigs = [['yAxis', {
				mode: this.config.yAxisMode,
				width: this.width
				// pos: 'right'
			}, function () {
				return this.state.yAxis;
			}.bind(this)], ['xAxis', {
				mode: this.config.xAxisMode,
				height: this.height
				// pos: 'right'
			}, function () {
				var s = this.state;
				s.xAxis.calcLabels = getShortenedLabels(this.width, s.xAxis.labels, this.config.xIsSeries);

				return s.xAxis;
			}.bind(this)], ['yRegions', {
				width: this.width,
				pos: 'right'
			}, function () {
				return this.state.yRegions;
			}.bind(this)]];

			var barDatasets = this.state.datasets.filter(function (d) {
				return d.chartType === 'bar';
			});
			var lineDatasets = this.state.datasets.filter(function (d) {
				return d.chartType === 'line';
			});

			var barsConfigs = barDatasets.map(function (d) {
				var index = d.index;
				return ['barGraph' + '-' + d.index, {
					index: index,
					color: _this3.colors[index],
					stacked: _this3.barOptions.stacked,

					// same for all datasets
					valuesOverPoints: _this3.config.valuesOverPoints,
					minHeight: _this3.height * MIN_BAR_PERCENT_HEIGHT
				}, function () {
					var s = this.state;
					var d = s.datasets[index];
					var stacked = this.barOptions.stacked;

					var spaceRatio = this.barOptions.spaceRatio || BAR_CHART_SPACE_RATIO;
					var barsWidth = s.unitWidth * (1 - spaceRatio);
					var barWidth = barsWidth / (stacked ? 1 : barDatasets.length);

					var xPositions = s.xAxis.positions.map(function (x) {
						return x - barsWidth / 2;
					});
					if (!stacked) {
						xPositions = xPositions.map(function (p) {
							return p + barWidth * index;
						});
					}

					var labels = new Array(s.datasetLength).fill('');
					if (this.config.valuesOverPoints) {
						if (stacked && d.index === s.datasets.length - 1) {
							labels = d.cumulativeYs;
						} else {
							labels = d.values;
						}
					}

					var offsets = new Array(s.datasetLength).fill(0);
					if (stacked) {
						offsets = d.yPositions.map(function (y, j) {
							return y - d.cumulativeYPos[j];
						});
					}

					return {
						xPositions: xPositions,
						yPositions: d.yPositions,
						offsets: offsets,
						// values: d.values,
						labels: labels,

						zeroLine: s.yAxis.zeroLine,
						barsWidth: barsWidth,
						barWidth: barWidth
					};
				}.bind(_this3)];
			});

			var lineConfigs = lineDatasets.map(function (d) {
				var index = d.index;
				return ['lineGraph' + '-' + d.index, {
					index: index,
					color: _this3.colors[index],
					svgDefs: _this3.svgDefs,
					heatline: _this3.lineOptions.heatline,
					regionFill: _this3.lineOptions.regionFill,
					hideDots: _this3.lineOptions.hideDots,
					hideLine: _this3.lineOptions.hideLine,

					// same for all datasets
					valuesOverPoints: _this3.config.valuesOverPoints
				}, function () {
					var s = this.state;
					var d = s.datasets[index];

					return {
						xPositions: s.xAxis.positions,
						yPositions: d.yPositions,

						values: d.values,

						zeroLine: s.yAxis.zeroLine,
						radius: this.lineOptions.dotSize || LINE_CHART_DOT_SIZE
					};
				}.bind(_this3)];
			});

			var markerConfigs = [['yMarkers', {
				width: this.width,
				pos: 'right'
			}, function () {
				return this.state.yMarkers;
			}.bind(this)]];

			componentConfigs = componentConfigs.concat(barsConfigs, lineConfigs, markerConfigs);

			var optionals = ['yMarkers', 'yRegions'];
			this.dataUnitComponents = [];

			this.components = new Map(componentConfigs.filter(function (args) {
				return !optionals.includes(args[0]) || _this3.state[args[0]];
			}).map(function (args) {
				var component = getComponent.apply(undefined, toConsumableArray(args));
				if (args[0].includes('lineGraph') || args[0].includes('barGraph')) {
					_this3.dataUnitComponents.push(component);
				}
				return [args[0], component];
			}));
		}
	}, {
		key: 'bindTooltip',
		value: function bindTooltip() {
			var _this4 = this;

			// NOTE: could be in tooltip itself, as it is a given functionality for its parent
			this.chartWrapper.addEventListener('mousemove', function (e) {
				var o = getOffset(_this4.chartWrapper);
				var relX = e.pageX - o.left - _this4.leftMargin;
				var relY = e.pageY - o.top - _this4.translateY;

				if (relY < _this4.height + _this4.translateY * 2) {
					_this4.mapTooltipXPosition(relX);
				} else {
					_this4.tip.hideTip();
				}
			});
		}
	}, {
		key: 'mapTooltipXPosition',
		value: function mapTooltipXPosition(relX) {
			var _this5 = this;

			var s = this.state;
			if (!s.yExtremes) return;

			var formatY = this.config.formatTooltipY;
			var formatX = this.config.formatTooltipX;

			var titles = s.xAxis.labels;
			if (formatX && formatX(titles[0])) {
				titles = titles.map(function (d) {
					return formatX(d);
				});
			}

			formatY = formatY && formatY(s.yAxis.labels[0]) ? formatY : 0;

			for (var i = s.datasetLength - 1; i >= 0; i--) {
				var xVal = s.xAxis.positions[i];
				// let delta = i === 0 ? s.unitWidth : xVal - s.xAxis.positions[i-1];
				if (relX > xVal - s.unitWidth / 2) {
					var x = xVal + this.leftMargin;
					var y = s.yExtremes[i] + this.translateY;

					var values = this.data.datasets.map(function (set$$1, j) {
						return {
							title: set$$1.name,
							value: formatY ? formatY(set$$1.values[i]) : set$$1.values[i],
							color: _this5.colors[j]
						};
					});

					this.tip.setValues(x, y, { name: titles[i], value: '' }, values, i);
					this.tip.showTip();
					break;
				}
			}
		}
	}, {
		key: 'renderLegend',
		value: function renderLegend() {
			var _this6 = this;

			var s = this.data;
			this.statsWrapper.textContent = '';

			if (s.datasets.length > 1) {
				s.datasets.map(function (d, i) {
					var stats = $.create('div', {
						className: 'stats',
						inside: _this6.statsWrapper
					});
					stats.innerHTML = '<span class="indicator">\n\t\t\t\t\t<i style="background: ' + _this6.colors[i] + '"></i>\n\t\t\t\t\t' + d.name + '\n\t\t\t\t</span>';
				});
			}
		}
	}, {
		key: 'makeOverlay',
		value: function makeOverlay$$1() {
			var _this7 = this;

			if (this.init) {
				this.init = 0;
				return;
			}
			if (this.overlayGuides) {
				this.overlayGuides.forEach(function (g) {
					var o = g.overlay;
					o.parentNode.removeChild(o);
				});
			}

			this.overlayGuides = this.dataUnitComponents.map(function (c) {
				return {
					type: c.unitType,
					overlay: undefined,
					units: c.units
				};
			});

			if (this.state.currentIndex === undefined) {
				this.state.currentIndex = this.state.datasetLength - 1;
			}

			// Render overlays
			this.overlayGuides.map(function (d) {
				var currentUnit = d.units[_this7.state.currentIndex];

				d.overlay = makeOverlay[d.type](currentUnit);
				_this7.drawArea.appendChild(d.overlay);
			});
		}
	}, {
		key: 'updateOverlayGuides',
		value: function updateOverlayGuides() {
			if (this.overlayGuides) {
				this.overlayGuides.forEach(function (g) {
					var o = g.overlay;
					o.parentNode.removeChild(o);
				});
			}
		}
	}, {
		key: 'bindOverlay',
		value: function bindOverlay() {
			var _this8 = this;

			this.parent.addEventListener('data-select', function () {
				_this8.updateOverlay();
			});
		}
	}, {
		key: 'bindUnits',
		value: function bindUnits() {
			var _this9 = this;

			this.dataUnitComponents.map(function (c) {
				c.units.map(function (unit) {
					unit.addEventListener('click', function () {
						var index = unit.getAttribute('data-point-index');
						_this9.setCurrentDataPoint(index);
					});
				});
			});

			// Note: Doesn't work as tooltip is absolutely positioned
			this.tip.container.addEventListener('click', function () {
				var index = _this9.tip.container.getAttribute('data-point-index');
				_this9.setCurrentDataPoint(index);
			});
		}
	}, {
		key: 'updateOverlay',
		value: function updateOverlay$$1() {
			var _this10 = this;

			this.overlayGuides.map(function (d) {
				var currentUnit = d.units[_this10.state.currentIndex];
				updateOverlay[d.type](currentUnit, d.overlay);
			});
		}
	}, {
		key: 'onLeftArrow',
		value: function onLeftArrow() {
			this.setCurrentDataPoint(this.state.currentIndex - 1);
		}
	}, {
		key: 'onRightArrow',
		value: function onRightArrow() {
			this.setCurrentDataPoint(this.state.currentIndex + 1);
		}
	}, {
		key: 'getDataPoint',
		value: function getDataPoint() {
			var index = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.state.currentIndex;

			var s = this.state;
			var data_point = {
				index: index,
				label: s.xAxis.labels[index],
				values: s.datasets.map(function (d) {
					return d.values[index];
				})
			};
			return data_point;
		}
	}, {
		key: 'setCurrentDataPoint',
		value: function setCurrentDataPoint(index) {
			var s = this.state;
			index = parseInt(index);
			if (index < 0) index = 0;
			if (index >= s.xAxis.labels.length) index = s.xAxis.labels.length - 1;
			if (index === s.currentIndex) return;
			s.currentIndex = index;
			fire(this.parent, "data-select", this.getDataPoint());
		}

		// API

	}, {
		key: 'addDataPoint',
		value: function addDataPoint(label, datasetValues) {
			var index = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : this.state.datasetLength;

			get(AxisChart.prototype.__proto__ || Object.getPrototypeOf(AxisChart.prototype), 'addDataPoint', this).call(this, label, datasetValues, index);
			this.data.labels.splice(index, 0, label);
			this.data.datasets.map(function (d, i) {
				d.values.splice(index, 0, datasetValues[i]);
			});
			this.update(this.data);
		}
	}, {
		key: 'removeDataPoint',
		value: function removeDataPoint() {
			var index = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.state.datasetLength - 1;

			if (this.data.labels.length <= 1) {
				return;
			}
			get(AxisChart.prototype.__proto__ || Object.getPrototypeOf(AxisChart.prototype), 'removeDataPoint', this).call(this, index);
			this.data.labels.splice(index, 1);
			this.data.datasets.map(function (d) {
				d.values.splice(index, 1);
			});
			this.update(this.data);
		}
	}, {
		key: 'updateDataset',
		value: function updateDataset(datasetValues) {
			var index = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 0;

			this.data.datasets[index].values = datasetValues;
			this.update(this.data);
		}
		// addDataset(dataset, index) {}
		// removeDataset(index = 0) {}

	}, {
		key: 'updateDatasets',
		value: function updateDatasets(datasets) {
			this.data.datasets.map(function (d, i) {
				if (datasets[i]) {
					d.values = datasets[i];
				}
			});
			this.update(this.data);
		}

		// updateDataPoint(dataPoint, index = 0) {}
		// addDataPoint(dataPoint, index = 0) {}
		// removeDataPoint(index = 0) {}

	}]);
	return AxisChart;
}(BaseChart);

// import MultiAxisChart from './charts/MultiAxisChart';
var chartTypes = {
	// multiaxis: MultiAxisChart,
	percentage: PercentageChart,
	heatmap: Heatmap,
	pie: PieChart
};

function getChartByType() {
	var chartType = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : 'line';
	var parent = arguments[1];
	var options = arguments[2];

	if (chartType === 'line') {
		options.type = 'line';
		return new AxisChart(parent, options);
	} else if (chartType === 'bar') {
		options.type = 'bar';
		return new AxisChart(parent, options);
	} else if (chartType === 'axis-mixed') {
		options.type = 'line';
		return new AxisChart(parent, options);
	}

	if (!chartTypes[chartType]) {
		console.error("Undefined chart type: " + chartType);
		return;
	}

	return new chartTypes[chartType](parent, options);
}

var Chart = function Chart(parent, options) {
	classCallCheck(this, Chart);

	return getChartByType(options.type, parent, options);
};

return Chart;

}());
//# sourceMappingURL=frappe-charts.min.iife.js.map
