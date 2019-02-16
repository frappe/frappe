(function webpackUniversalModuleDefinition(root, factory) {
	if(typeof exports === 'object' && typeof module === 'object')
		module.exports = factory(require("sortablejs"), require("clusterize.js"));
	else if(typeof define === 'function' && define.amd)
		define("DataTable", [, ], factory);
	else if(typeof exports === 'object')
		exports["DataTable"] = factory(require("sortablejs"), require("clusterize.js"));
	else
		root["DataTable"] = factory(root["Sortable"], root["Clusterize"]);
})(typeof self !== 'undefined' ? self : this, function(__WEBPACK_EXTERNAL_MODULE_8__, __WEBPACK_EXTERNAL_MODULE_11__) {
return /******/ (function(modules) { // webpackBootstrap
/******/ 	// The module cache
/******/ 	var installedModules = {};
/******/
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/
/******/ 		// Check if module is in cache
/******/ 		if(installedModules[moduleId]) {
/******/ 			return installedModules[moduleId].exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = installedModules[moduleId] = {
/******/ 			i: moduleId,
/******/ 			l: false,
/******/ 			exports: {}
/******/ 		};
/******/
/******/ 		// Execute the module function
/******/ 		modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/
/******/ 		// Flag the module as loaded
/******/ 		module.l = true;
/******/
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/
/******/
/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = modules;
/******/
/******/ 	// expose the module cache
/******/ 	__webpack_require__.c = installedModules;
/******/
/******/ 	// define getter function for harmony exports
/******/ 	__webpack_require__.d = function(exports, name, getter) {
/******/ 		if(!__webpack_require__.o(exports, name)) {
/******/ 			Object.defineProperty(exports, name, {
/******/ 				configurable: false,
/******/ 				enumerable: true,
/******/ 				get: getter
/******/ 			});
/******/ 		}
/******/ 	};
/******/
/******/ 	// getDefaultExport function for compatibility with non-harmony modules
/******/ 	__webpack_require__.n = function(module) {
/******/ 		var getter = module && module.__esModule ?
/******/ 			function getDefault() { return module['default']; } :
/******/ 			function getModuleExports() { return module; };
/******/ 		__webpack_require__.d(getter, 'a', getter);
/******/ 		return getter;
/******/ 	};
/******/
/******/ 	// Object.prototype.hasOwnProperty.call
/******/ 	__webpack_require__.o = function(object, property) { return Object.prototype.hasOwnProperty.call(object, property); };
/******/
/******/ 	// __webpack_public_path__
/******/ 	__webpack_require__.p = "";
/******/
/******/ 	// Load entry module and return exports
/******/ 	return __webpack_require__(__webpack_require__.s = 4);
/******/ })
/************************************************************************/
/******/ ([
/* 0 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _typeof = typeof Symbol === "function" && typeof Symbol.iterator === "symbol" ? function (obj) { return typeof obj; } : function (obj) { return obj && typeof Symbol === "function" && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; };

exports.default = $;
function $(expr, con) {
  return typeof expr === 'string' ? (con || document).querySelector(expr) : expr || null;
}

$.each = function (expr, con) {
  return typeof expr === 'string' ? Array.from((con || document).querySelectorAll(expr)) : expr || null;
};

$.create = function (tag, o) {
  var element = document.createElement(tag);

  var _loop = function _loop(i) {
    var val = o[i];

    if (i === 'inside') {
      $(val).appendChild(element);
    } else if (i === 'around') {
      var ref = $(val);
      ref.parentNode.insertBefore(element, ref);
      element.appendChild(ref);
    } else if (i === 'styles') {
      if ((typeof val === 'undefined' ? 'undefined' : _typeof(val)) === 'object') {
        Object.keys(val).map(function (prop) {
          element.style[prop] = val[prop];
        });
      }
    } else if (i in element) {
      element[i] = val;
    } else {
      element.setAttribute(i, val);
    }
  };

  for (var i in o) {
    _loop(i);
  }

  return element;
};

$.on = function (element, event, selector, callback) {
  if (!callback) {
    callback = selector;
    $.bind(element, event, callback);
  } else {
    $.delegate(element, event, selector, callback);
  }
};

$.off = function (element, event, handler) {
  element.removeEventListener(event, handler);
};

$.bind = function (element, event, callback) {
  event.split(/\s+/).forEach(function (event) {
    element.addEventListener(event, callback);
  });
};

$.delegate = function (element, event, selector, callback) {
  element.addEventListener(event, function (e) {
    var delegatedTarget = e.target.closest(selector);
    if (delegatedTarget) {
      e.delegatedTarget = delegatedTarget;
      callback.call(this, e, delegatedTarget);
    }
  });
};

$.unbind = function (element, o) {
  if (element) {
    var _loop2 = function _loop2(event) {
      var callback = o[event];

      event.split(/\s+/).forEach(function (event) {
        element.removeEventListener(event, callback);
      });
    };

    for (var event in o) {
      _loop2(event);
    }
  }
};

$.fire = function (target, type, properties) {
  var evt = document.createEvent('HTMLEvents');

  evt.initEvent(type, true, true);

  for (var j in properties) {
    evt[j] = properties[j];
  }

  return target.dispatchEvent(evt);
};

$.data = function (element, attrs) {
  // eslint-disable-line
  if (!attrs) {
    return element.dataset;
  }

  for (var attr in attrs) {
    element.dataset[attr] = attrs[attr];
  }
};

$.style = function (elements, styleMap) {
  // eslint-disable-line

  if (typeof styleMap === 'string') {
    return $.getStyle(elements, styleMap);
  }

  if (!Array.isArray(elements)) {
    elements = [elements];
  }

  elements.map(function (element) {
    for (var prop in styleMap) {
      element.style[prop] = styleMap[prop];
    }
  });
};

$.removeStyle = function (elements, styleProps) {
  if (!Array.isArray(elements)) {
    elements = [elements];
  }

  if (!Array.isArray(styleProps)) {
    styleProps = [styleProps];
  }

  elements.map(function (element) {
    var _iteratorNormalCompletion = true;
    var _didIteratorError = false;
    var _iteratorError = undefined;

    try {
      for (var _iterator = styleProps[Symbol.iterator](), _step; !(_iteratorNormalCompletion = (_step = _iterator.next()).done); _iteratorNormalCompletion = true) {
        var prop = _step.value;

        element.style[prop] = '';
      }
    } catch (err) {
      _didIteratorError = true;
      _iteratorError = err;
    } finally {
      try {
        if (!_iteratorNormalCompletion && _iterator.return) {
          _iterator.return();
        }
      } finally {
        if (_didIteratorError) {
          throw _iteratorError;
        }
      }
    }
  });
};

$.getStyle = function (element, prop) {
  var val = getComputedStyle(element)[prop];

  if (['width', 'height'].includes(prop)) {
    val = parseFloat(val);
  }

  return val;
};

$.closest = function (selector, element) {
  if (!element) return null;

  if (element.matches(selector)) {
    return element;
  }

  return $.closest(selector, element.parentNode);
};

$.inViewport = function (el, parentEl) {
  var _el$getBoundingClient = el.getBoundingClientRect(),
      top = _el$getBoundingClient.top,
      left = _el$getBoundingClient.left,
      bottom = _el$getBoundingClient.bottom,
      right = _el$getBoundingClient.right;

  var _parentEl$getBounding = parentEl.getBoundingClientRect(),
      pTop = _parentEl$getBounding.top,
      pLeft = _parentEl$getBounding.left,
      pBottom = _parentEl$getBounding.bottom,
      pRight = _parentEl$getBounding.right;

  return top >= pTop && left >= pLeft && bottom <= pBottom && right <= pRight;
};

$.scrollTop = function scrollTop(element, pixels) {
  requestAnimationFrame(function () {
    element.scrollTop = pixels;
  });
};
module.exports = exports['default'];

/***/ }),
/* 1 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.camelCaseToDash = camelCaseToDash;
exports.makeDataAttributeString = makeDataAttributeString;
exports.getDefault = getDefault;
exports.escapeRegExp = escapeRegExp;
exports.getCSSString = getCSSString;
exports.getCSSRuleBlock = getCSSRuleBlock;
exports.buildCSSRule = buildCSSRule;
exports.removeCSSRule = removeCSSRule;
exports.copyTextToClipboard = copyTextToClipboard;
exports.isNumeric = isNumeric;
exports.throttle = throttle;
exports.promisify = promisify;
exports.chainPromises = chainPromises;
function camelCaseToDash(str) {
  return str.replace(/([A-Z])/g, function (g) {
    return '-' + g[0].toLowerCase();
  });
}

function makeDataAttributeString(props) {
  var keys = Object.keys(props);

  return keys.map(function (key) {
    var _key = camelCaseToDash(key);
    var val = props[key];

    if (val === undefined) return '';
    return 'data-' + _key + '="' + val + '" ';
  }).join('').trim();
}

function getDefault(a, b) {
  return a !== undefined ? a : b;
}

function escapeRegExp(str) {
  // https://stackoverflow.com/a/6969486
  return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');
}

function getCSSString(styleMap) {
  var style = '';

  for (var prop in styleMap) {
    if (styleMap.hasOwnProperty(prop)) {
      style += prop + ': ' + styleMap[prop] + '; ';
    }
  }

  return style.trim();
}

function getCSSRuleBlock(rule, styleMap) {
  return rule + ' { ' + getCSSString(styleMap) + ' }';
}

function buildCSSRule(rule, styleMap) {
  var cssRulesString = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : '';

  // build css rules efficiently,
  // append new rule if doesnt exist,
  // update existing ones

  var rulePatternStr = escapeRegExp(rule) + ' {([^}]*)}';
  var rulePattern = new RegExp(rulePatternStr, 'g');

  if (cssRulesString && cssRulesString.match(rulePattern)) {
    var _loop = function _loop(property) {
      var value = styleMap[property];
      var propPattern = new RegExp(escapeRegExp(property) + ':([^;]*);');

      cssRulesString = cssRulesString.replace(rulePattern, function (match, propertyStr) {
        if (propertyStr.match(propPattern)) {
          // property exists, replace value with new value
          propertyStr = propertyStr.replace(propPattern, function (match, valueStr) {
            return property + ': ' + value + ';';
          });
        }
        propertyStr = propertyStr.trim();

        var replacer = rule + ' { ' + propertyStr + ' }';

        return replacer;
      });
    };

    for (var property in styleMap) {
      _loop(property);
    }

    return cssRulesString;
  }
  // no match, append new rule block
  return '' + cssRulesString + getCSSRuleBlock(rule, styleMap);
}

function removeCSSRule(rule) {
  var cssRulesString = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : '';

  var rulePatternStr = escapeRegExp(rule) + ' {([^}]*)}';
  var rulePattern = new RegExp(rulePatternStr, 'g');
  var output = cssRulesString;

  if (cssRulesString && cssRulesString.match(rulePattern)) {
    output = cssRulesString.replace(rulePattern, '');
  }

  return output.trim();
}

function copyTextToClipboard(text) {
  // https://stackoverflow.com/a/30810322/5353542
  var textArea = document.createElement('textarea');

  //
  // *** This styling is an extra step which is likely not required. ***
  //
  // Why is it here? To ensure:
  // 1. the element is able to have focus and selection.
  // 2. if element was to flash render it has minimal visual impact.
  // 3. less flakyness with selection and copying which **might** occur if
  //    the textarea element is not visible.
  //
  // The likelihood is the element won't even render, not even a flash,
  // so some of these are just precautions. However in IE the element
  // is visible whilst the popup box asking the user for permission for
  // the web page to copy to the clipboard.
  //

  // Place in top-left corner of screen regardless of scroll position.
  textArea.style.position = 'fixed';
  textArea.style.top = 0;
  textArea.style.left = 0;

  // Ensure it has a small width and height. Setting to 1px / 1em
  // doesn't work as this gives a negative w/h on some browsers.
  textArea.style.width = '2em';
  textArea.style.height = '2em';

  // We don't need padding, reducing the size if it does flash render.
  textArea.style.padding = 0;

  // Clean up any borders.
  textArea.style.border = 'none';
  textArea.style.outline = 'none';
  textArea.style.boxShadow = 'none';

  // Avoid flash of white box if rendered for any reason.
  textArea.style.background = 'transparent';

  textArea.value = text;

  document.body.appendChild(textArea);

  textArea.select();

  try {
    document.execCommand('copy');
  } catch (err) {
    console.log('Oops, unable to copy');
  }

  document.body.removeChild(textArea);
}

function isNumeric(val) {
  return !isNaN(val);
}

// https://stackoverflow.com/a/27078401
function throttle(func, wait, options) {
  var context, args, result;
  var timeout = null;
  var previous = 0;
  if (!options) options = {};

  var later = function later() {
    previous = options.leading === false ? 0 : Date.now();
    timeout = null;
    result = func.apply(context, args);
    if (!timeout) context = args = null;
  };

  return function () {
    var now = Date.now();
    if (!previous && options.leading === false) previous = now;
    var remaining = wait - (now - previous);
    context = this;
    args = arguments;
    if (remaining <= 0 || remaining > wait) {
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
      previous = now;
      result = func.apply(context, args);
      if (!timeout) context = args = null;
    } else if (!timeout && options.trailing !== false) {
      timeout = setTimeout(later, remaining);
    }
    return result;
  };
};

function promisify(fn) {
  var context = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : null;

  return function () {
    for (var _len = arguments.length, args = Array(_len), _key2 = 0; _key2 < _len; _key2++) {
      args[_key2] = arguments[_key2];
    }

    return new Promise(function (resolve) {
      setTimeout(function () {
        fn.apply(context, args);
        resolve('done', fn.name);
      }, 0);
    });
  };
};

function chainPromises(promises) {
  return promises.reduce(function (prev, cur) {
    return prev.then(cur);
  }, Promise.resolve());
};

/***/ }),
/* 2 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _dom = __webpack_require__(0);

var _dom2 = _interopRequireDefault(_dom);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var KEYCODES = {
  13: 'enter',
  91: 'meta',
  16: 'shift',
  17: 'ctrl',
  18: 'alt',
  37: 'left',
  38: 'up',
  39: 'right',
  40: 'down',
  9: 'tab',
  27: 'esc',
  67: 'c'
};

var initDone = false;
var handlers = {};

function bind(dom) {
  if (initDone) return;
  _dom2.default.on(dom, 'keydown', handler);
  initDone = true;
}

function handler(e) {
  var key = KEYCODES[e.keyCode];

  if (e.shiftKey && key !== 'shift') {
    key = 'shift+' + key;
  }

  if (e.ctrlKey && key !== 'ctrl' || e.metaKey && key !== 'meta') {
    key = 'ctrl+' + key;
  }

  var _handlers = handlers[key];

  if (_handlers && _handlers.length > 0) {
    _handlers.map(function (handler) {
      var preventBubbling = handler();

      if (preventBubbling === undefined || preventBubbling === true) {
        e.preventDefault();
      }
    });
  }
}

exports.default = {
  init: function init(dom) {
    bind(dom);
  },
  on: function on(key, handler) {
    var keys = key.split(',').map(function (k) {
      return k.trim();
    });

    keys.map(function (key) {
      handlers[key] = handlers[key] || [];
      handlers[key].push(handler);
    });
  }
};
module.exports = exports['default'];

/***/ }),
/* 3 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getDropdownHTML = undefined;

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _dom = __webpack_require__(0);

var _dom2 = _interopRequireDefault(_dom);

var _sortablejs = __webpack_require__(8);

var _sortablejs2 = _interopRequireDefault(_sortablejs);

var _utils = __webpack_require__(1);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var ColumnManager = function () {
  function ColumnManager(instance) {
    _classCallCheck(this, ColumnManager);

    this.instance = instance;
    this.options = this.instance.options;
    this.fireEvent = this.instance.fireEvent;
    this.header = this.instance.header;
    this.datamanager = this.instance.datamanager;
    this.style = this.instance.style;
    this.wrapper = this.instance.wrapper;
    this.rowmanager = this.instance.rowmanager;

    this.bindEvents();
    exports.getDropdownHTML = getDropdownHTML = getDropdownHTML.bind(this, this.options.dropdownButton);
  }

  _createClass(ColumnManager, [{
    key: 'renderHeader',
    value: function renderHeader() {
      this.header.innerHTML = '<thead></thead>';
      this.refreshHeader();
    }
  }, {
    key: 'refreshHeader',
    value: function refreshHeader() {
      var _this = this;

      var columns = this.datamanager.getColumns();

      if (!(0, _dom2.default)('.data-table-col', this.header)) {
        // insert html
        (0, _dom2.default)('thead', this.header).innerHTML = this.rowmanager.getRowHTML(columns, { isHeader: 1 });
      } else {
        // refresh dom state
        var $cols = _dom2.default.each('.data-table-col', this.header);
        if (columns.length < $cols.length) {
          // deleted column
          (0, _dom2.default)('thead', this.header).innerHTML = this.rowmanager.getRowHTML(columns, { isHeader: 1 });
          return;
        }

        $cols.map(function ($col, i) {
          var column = columns[i];
          // column sorted or order changed
          // update colIndex of each header cell
          _dom2.default.data($col, {
            colIndex: column.colIndex
          });

          // refresh sort indicator
          var sortIndicator = (0, _dom2.default)('.sort-indicator', $col);
          if (sortIndicator) {
            sortIndicator.innerHTML = _this.options.sortIndicator[column.sortOrder];
          }
        });
      }
      // reset columnMap
      this.$columnMap = [];
    }
  }, {
    key: 'bindEvents',
    value: function bindEvents() {
      this.bindDropdown();
      this.bindResizeColumn();
      this.bindMoveColumn();
    }
  }, {
    key: 'bindDropdown',
    value: function bindDropdown() {
      var _this2 = this;

      var $activeDropdown = void 0;
      _dom2.default.on(this.header, 'click', '.data-table-dropdown-toggle', function (e, $button) {
        var $dropdown = _dom2.default.closest('.data-table-dropdown', $button);

        if (!$dropdown.classList.contains('is-active')) {
          deactivateDropdown();
          $dropdown.classList.add('is-active');
          $activeDropdown = $dropdown;
        } else {
          deactivateDropdown();
        }
      });

      _dom2.default.on(document.body, 'click', function (e) {
        if (e.target.matches('.data-table-dropdown-toggle')) return;
        deactivateDropdown();
      });

      var dropdownItems = this.options.headerDropdown;

      _dom2.default.on(this.header, 'click', '.data-table-dropdown-list > div', function (e, $item) {
        var $col = _dom2.default.closest('.data-table-col', $item);

        var _$$data = _dom2.default.data($item),
            index = _$$data.index;

        var _$$data2 = _dom2.default.data($col),
            colIndex = _$$data2.colIndex;

        var callback = dropdownItems[index].action;

        callback && callback.call(_this2.instance, _this2.getColumn(colIndex));
      });

      function deactivateDropdown(e) {
        $activeDropdown && $activeDropdown.classList.remove('is-active');
        $activeDropdown = null;
      }
    }
  }, {
    key: 'bindResizeColumn',
    value: function bindResizeColumn() {
      var _this3 = this;

      var isDragging = false;
      var $resizingCell = void 0,
          startWidth = void 0,
          startX = void 0;

      _dom2.default.on(this.header, 'mousedown', '.data-table-col .column-resizer', function (e, $handle) {
        document.body.classList.add('data-table-resize');
        var $cell = $handle.parentNode.parentNode;
        $resizingCell = $cell;

        var _$$data3 = _dom2.default.data($resizingCell),
            colIndex = _$$data3.colIndex;

        var col = _this3.getColumn(colIndex);

        if (col && col.resizable === false) {
          return;
        }

        isDragging = true;
        startWidth = _dom2.default.style((0, _dom2.default)('.content', $resizingCell), 'width');
        startX = e.pageX;
      });

      _dom2.default.on(document.body, 'mouseup', function (e) {
        document.body.classList.remove('data-table-resize');
        if (!$resizingCell) return;
        isDragging = false;

        var _$$data4 = _dom2.default.data($resizingCell),
            colIndex = _$$data4.colIndex;

        _this3.setColumnWidth(colIndex);
        _this3.instance.setBodyWidth();
        $resizingCell = null;
      });

      _dom2.default.on(document.body, 'mousemove', function (e) {
        if (!isDragging) return;
        var finalWidth = startWidth + (e.pageX - startX);

        var _$$data5 = _dom2.default.data($resizingCell),
            colIndex = _$$data5.colIndex;

        if (_this3.getColumnMinWidth(colIndex) > finalWidth) {
          // don't resize past minWidth
          return;
        }
        _this3.datamanager.updateColumn(colIndex, { width: finalWidth });
        _this3.setColumnHeaderWidth(colIndex);
      });
    }
  }, {
    key: 'bindMoveColumn',
    value: function bindMoveColumn() {
      var _this4 = this;

      var initialized = void 0;

      var initialize = function initialize() {
        if (initialized) {
          _dom2.default.off(document.body, 'mousemove', initialize);
          return;
        }
        var ready = (0, _dom2.default)('.data-table-col', _this4.header);
        if (!ready) return;

        var $parent = (0, _dom2.default)('.data-table-row', _this4.header);

        _this4.sortable = _sortablejs2.default.create($parent, {
          onEnd: function onEnd(e) {
            var oldIndex = e.oldIndex,
                newIndex = e.newIndex;

            var $draggedCell = e.item;

            var _$$data6 = _dom2.default.data($draggedCell),
                colIndex = _$$data6.colIndex;

            if (+colIndex === newIndex) return;

            _this4.switchColumn(oldIndex, newIndex);
          },
          preventOnFilter: false,
          filter: '.column-resizer, .data-table-dropdown',
          animation: 150
        });
      };

      _dom2.default.on(document.body, 'mousemove', initialize);
    }
  }, {
    key: 'bindSortColumn',
    value: function bindSortColumn() {
      var _this5 = this;

      _dom2.default.on(this.header, 'click', '.data-table-col .column-title', function (e, span) {
        var $cell = span.closest('.data-table-col');

        var _$$data7 = _dom2.default.data($cell),
            colIndex = _$$data7.colIndex,
            sortOrder = _$$data7.sortOrder;

        sortOrder = (0, _utils.getDefault)(sortOrder, 'none');
        var col = _this5.getColumn(colIndex);

        if (col && col.sortable === false) {
          return;
        }

        // reset sort indicator
        (0, _dom2.default)('.sort-indicator', _this5.header).textContent = '';
        _dom2.default.each('.data-table-col', _this5.header).map(function ($cell) {
          _dom2.default.data($cell, {
            sortOrder: 'none'
          });
        });

        var nextSortOrder = void 0,
            textContent = void 0;
        if (sortOrder === 'none') {
          nextSortOrder = 'asc';
          textContent = '▲';
        } else if (sortOrder === 'asc') {
          nextSortOrder = 'desc';
          textContent = '▼';
        } else if (sortOrder === 'desc') {
          nextSortOrder = 'none';
          textContent = '';
        }

        _dom2.default.data($cell, {
          sortOrder: nextSortOrder
        });
        (0, _dom2.default)('.sort-indicator', $cell).textContent = textContent;

        _this5.sortColumn(colIndex, nextSortOrder);
      });
    }
  }, {
    key: 'sortColumn',
    value: function sortColumn(colIndex, nextSortOrder) {
      var _this6 = this;

      this.instance.freeze();
      this.sortRows(colIndex, nextSortOrder).then(function () {
        _this6.refreshHeader();
        return _this6.rowmanager.refreshRows();
      }).then(function () {
        return _this6.instance.unfreeze();
      }).then(function () {
        _this6.fireEvent('onSortColumn', _this6.getColumn(colIndex));
      });
    }
  }, {
    key: 'removeColumn',
    value: function removeColumn(colIndex) {
      var _this7 = this;

      var removedCol = this.getColumn(colIndex);
      this.instance.freeze();
      this.datamanager.removeColumn(colIndex).then(function () {
        _this7.refreshHeader();
        return _this7.rowmanager.refreshRows();
      }).then(function () {
        return _this7.instance.unfreeze();
      }).then(function () {
        _this7.fireEvent('onRemoveColumn', removedCol);
      });
    }
  }, {
    key: 'switchColumn',
    value: function switchColumn(oldIndex, newIndex) {
      var _this8 = this;

      this.instance.freeze();
      this.datamanager.switchColumn(oldIndex, newIndex).then(function () {
        _this8.refreshHeader();
        return _this8.rowmanager.refreshRows();
      }).then(function () {
        _this8.setColumnWidth(oldIndex);
        _this8.setColumnWidth(newIndex);
        _this8.instance.unfreeze();
      }).then(function () {
        _this8.fireEvent('onSwitchColumn', _this8.getColumn(oldIndex), _this8.getColumn(newIndex));
      });
    }
  }, {
    key: 'setDimensions',
    value: function setDimensions() {
      this.setHeaderStyle();
      this.setupMinWidth();
      this.setupNaturalColumnWidth();
      this.distributeRemainingWidth();
      this.setColumnStyle();
      this.setDefaultCellHeight();
    }
  }, {
    key: 'setHeaderStyle',
    value: function setHeaderStyle() {
      if (!this.options.takeAvailableSpace) {
        // setting width as 0 will ensure that the
        // header doesn't take the available space
        _dom2.default.style(this.header, {
          width: 0
        });
      }

      _dom2.default.style(this.header, {
        margin: 0
      });

      // don't show resize cursor on nonResizable columns
      var nonResizableColumnsSelector = this.datamanager.getColumns().filter(function (col) {
        return col.resizable === false;
      }).map(function (col) {
        return col.colIndex;
      }).map(function (i) {
        return '.data-table-header [data-col-index="' + i + '"]';
      }).join();

      this.style.setStyle(nonResizableColumnsSelector, {
        cursor: 'pointer'
      });
    }
  }, {
    key: 'setupMinWidth',
    value: function setupMinWidth() {
      var _this9 = this;

      _dom2.default.each('.data-table-col', this.header).map(function (col) {
        var width = _dom2.default.style((0, _dom2.default)('.content', col), 'width');

        var _$$data8 = _dom2.default.data(col),
            colIndex = _$$data8.colIndex;

        var column = _this9.getColumn(colIndex);

        if (!column.minWidth) {
          // only set this once
          _this9.datamanager.updateColumn(colIndex, { minWidth: width });
        }
      });
    }
  }, {
    key: 'setupNaturalColumnWidth',
    value: function setupNaturalColumnWidth() {
      var _this10 = this;

      // set initial width as naturally calculated by table's first row
      _dom2.default.each('.data-table-row[data-row-index="0"] .data-table-col', this.bodyScrollable).map(function ($cell) {
        var _$$data9 = _dom2.default.data($cell),
            colIndex = _$$data9.colIndex;

        if (_this10.getColumn(colIndex).width > 0) {
          // already set
          return;
        }

        var width = _dom2.default.style((0, _dom2.default)('.content', $cell), 'width');
        var minWidth = _this10.getColumnMinWidth(colIndex);

        if (width < minWidth) {
          width = minWidth;
        }
        _this10.datamanager.updateColumn(colIndex, { width: width });
      });
    }
  }, {
    key: 'distributeRemainingWidth',
    value: function distributeRemainingWidth() {
      var _this11 = this;

      if (!this.options.takeAvailableSpace) return;

      var wrapperWidth = _dom2.default.style(this.instance.datatableWrapper, 'width');
      var headerWidth = _dom2.default.style(this.header, 'width');

      if (headerWidth >= wrapperWidth) {
        // don't resize, horizontal scroll takes place
        return;
      }

      var resizableColumns = this.datamanager.getColumns().filter(function (col) {
        return col.resizable === undefined || col.resizable;
      });

      var deltaWidth = (wrapperWidth - headerWidth) / resizableColumns.length;

      resizableColumns.map(function (col) {
        var width = _dom2.default.style(_this11.getColumnHeaderElement(col.colIndex), 'width');
        var finalWidth = Math.min(width + deltaWidth) - 2;

        _this11.datamanager.updateColumn(col.colIndex, { width: finalWidth });
      });
    }
  }, {
    key: 'setDefaultCellHeight',
    value: function setDefaultCellHeight() {
      if (this.__cellHeightSet) return;
      var height = _dom2.default.style((0, _dom2.default)('.data-table-col', this.instance.datatableWrapper), 'height');
      if (height) {
        this.setCellHeight(height);
        this.__cellHeightSet = true;
      }
    }
  }, {
    key: 'setCellHeight',
    value: function setCellHeight(height) {
      this.style.setStyle('.data-table-col .content', {
        height: height + 'px'
      });
      this.style.setStyle('.data-table-col .edit-cell', {
        height: height + 'px'
      });
    }
  }, {
    key: 'setColumnStyle',
    value: function setColumnStyle() {
      var _this12 = this;

      // align columns
      this.getColumns().map(function (column) {
        // alignment
        if (['left', 'center', 'right'].includes(column.align)) {
          _this12.style.setStyle('[data-col-index="' + column.colIndex + '"]', {
            'text-align': column.align
          });
        }
        // width
        _this12.setColumnHeaderWidth(column.colIndex);
        _this12.setColumnWidth(column.colIndex);
      });
      this.instance.setBodyWidth();
    }
  }, {
    key: 'sortRows',
    value: function sortRows(colIndex, sortOrder) {
      return this.datamanager.sortRows(colIndex, sortOrder);
    }
  }, {
    key: 'getColumn',
    value: function getColumn(colIndex) {
      return this.datamanager.getColumn(colIndex);
    }
  }, {
    key: 'getColumns',
    value: function getColumns() {
      return this.datamanager.getColumns();
    }
  }, {
    key: 'setColumnWidth',
    value: function setColumnWidth(colIndex) {
      colIndex = +colIndex;
      this._columnWidthMap = this._columnWidthMap || [];

      var _getColumn = this.getColumn(colIndex),
          width = _getColumn.width;

      var index = this._columnWidthMap[colIndex];
      var selector = '[data-col-index="' + colIndex + '"] .content, [data-col-index="' + colIndex + '"] .edit-cell';
      var styles = {
        width: width + 'px'
      };

      index = this.style.setStyle(selector, styles, index);
      this._columnWidthMap[colIndex] = index;
    }
  }, {
    key: 'setColumnHeaderWidth',
    value: function setColumnHeaderWidth(colIndex) {
      colIndex = +colIndex;
      this.$columnMap = this.$columnMap || [];
      var selector = '[data-col-index="' + colIndex + '"][data-is-header] .content';

      var _getColumn2 = this.getColumn(colIndex),
          width = _getColumn2.width;

      var $column = this.$columnMap[colIndex];
      if (!$column) {
        $column = this.header.querySelector(selector);
        this.$columnMap[colIndex] = $column;
      }

      $column.style.width = width + 'px';
    }
  }, {
    key: 'getColumnMinWidth',
    value: function getColumnMinWidth(colIndex) {
      colIndex = +colIndex;
      return this.getColumn(colIndex).minWidth || 24;
    }
  }, {
    key: 'getFirstColumnIndex',
    value: function getFirstColumnIndex() {
      if (this.options.addCheckboxColumn && this.options.addSerialNoColumn) {
        return 2;
      }

      if (this.options.addCheckboxColumn || this.options.addSerialNoColumn) {
        return 1;
      }

      return 0;
    }
  }, {
    key: 'getHeaderCell$',
    value: function getHeaderCell$(colIndex) {
      return (0, _dom2.default)('.data-table-col[data-col-index="' + colIndex + '"]', this.header);
    }
  }, {
    key: 'getLastColumnIndex',
    value: function getLastColumnIndex() {
      return this.datamanager.getColumnCount() - 1;
    }
  }, {
    key: 'getColumnHeaderElement',
    value: function getColumnHeaderElement(colIndex) {
      colIndex = +colIndex;
      if (colIndex < 0) return null;
      return (0, _dom2.default)('.data-table-col[data-is-header][data-col-index="' + colIndex + '"]', this.wrapper);
    }
  }, {
    key: 'getSerialColumnIndex',
    value: function getSerialColumnIndex() {
      var columns = this.datamanager.getColumns();

      return columns.findIndex(function (column) {
        return column.content.includes('Sr. No');
      });
    }
  }]);

  return ColumnManager;
}();

// eslint-disable-next-line


exports.default = ColumnManager;
var getDropdownHTML = function getDropdownHTML() {
  var dropdownButton = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : 'v';

  // add dropdown buttons
  var dropdownItems = this.options.headerDropdown;

  return '<div class="data-table-dropdown-toggle">' + dropdownButton + '</div>\n    <div class="data-table-dropdown-list">\n      ' + dropdownItems.map(function (d, i) {
    return '<div data-index="' + i + '">' + d.label + '</div>';
  }).join('') + '\n    </div>\n  ';
};

exports.getDropdownHTML = getDropdownHTML;

/***/ }),
/* 4 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _datatable = __webpack_require__(5);

var _datatable2 = _interopRequireDefault(_datatable);

var _package = __webpack_require__(19);

var _package2 = _interopRequireDefault(_package);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

_datatable2.default.__version__ = _package2.default.version;

exports.default = _datatable2.default;
module.exports = exports['default'];

/***/ }),
/* 5 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _dom = __webpack_require__(0);

var _dom2 = _interopRequireDefault(_dom);

var _datamanager = __webpack_require__(6);

var _datamanager2 = _interopRequireDefault(_datamanager);

var _cellmanager = __webpack_require__(7);

var _cellmanager2 = _interopRequireDefault(_cellmanager);

var _columnmanager = __webpack_require__(3);

var _columnmanager2 = _interopRequireDefault(_columnmanager);

var _rowmanager = __webpack_require__(9);

var _rowmanager2 = _interopRequireDefault(_rowmanager);

var _bodyRenderer = __webpack_require__(10);

var _bodyRenderer2 = _interopRequireDefault(_bodyRenderer);

var _style = __webpack_require__(12);

var _style2 = _interopRequireDefault(_style);

var _keyboard = __webpack_require__(2);

var _keyboard2 = _interopRequireDefault(_keyboard);

var _defaults = __webpack_require__(13);

var _defaults2 = _interopRequireDefault(_defaults);

__webpack_require__(14);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var DataTable = function () {
  function DataTable(wrapper, options) {
    _classCallCheck(this, DataTable);

    DataTable.instances++;

    if (typeof wrapper === 'string') {
      // css selector
      wrapper = document.querySelector(wrapper);
    }
    this.wrapper = wrapper;
    if (!(this.wrapper instanceof HTMLElement)) {
      throw new Error('Invalid argument given for `wrapper`');
    }

    this.options = Object.assign({}, _defaults2.default, options);
    this.options.headerDropdown = _defaults2.default.headerDropdown.concat(options.headerDropdown || []);
    // custom user events
    this.events = Object.assign({}, _defaults2.default.events, options.events || {});
    this.fireEvent = this.fireEvent.bind(this);

    this.prepare();

    this.style = new _style2.default(this);
    this.datamanager = new _datamanager2.default(this.options);
    this.rowmanager = new _rowmanager2.default(this);
    this.columnmanager = new _columnmanager2.default(this);
    this.cellmanager = new _cellmanager2.default(this);
    this.bodyRenderer = new _bodyRenderer2.default(this);

    _keyboard2.default.init(this.wrapper);

    if (this.options.data) {
      this.refresh();
    }
  }

  _createClass(DataTable, [{
    key: 'prepare',
    value: function prepare() {
      this.prepareDom();
      this.unfreeze();
    }
  }, {
    key: 'prepareDom',
    value: function prepareDom() {
      this.wrapper.innerHTML = '\n      <div class="data-table">\n        <table class="data-table-header">\n        </table>\n        <div class="body-scrollable">\n        </div>\n        <div class="freeze-container">\n          <span>' + this.options.freezeMessage + '</span>\n        </div>\n        <div class="data-table-footer">\n        </div>\n      </div>\n    ';

      this.datatableWrapper = (0, _dom2.default)('.data-table', this.wrapper);
      this.header = (0, _dom2.default)('.data-table-header', this.wrapper);
      this.bodyScrollable = (0, _dom2.default)('.body-scrollable', this.wrapper);
      this.freezeContainer = (0, _dom2.default)('.freeze-container', this.wrapper);
    }
  }, {
    key: 'refresh',
    value: function refresh(data) {
      this.datamanager.init(data);
      this.render();
      this.setDimensions();
    }
  }, {
    key: 'destroy',
    value: function destroy() {
      this.wrapper.innerHTML = '';
      this.style.destroy();
    }
  }, {
    key: 'appendRows',
    value: function appendRows(rows) {
      this.datamanager.appendRows(rows);
      this.rowmanager.refreshRows();
    }
  }, {
    key: 'refreshRow',
    value: function refreshRow(row, rowIndex) {
      this.rowmanager.refreshRow(row, rowIndex);
    }
  }, {
    key: 'render',
    value: function render() {
      this.renderHeader();
      this.renderBody();
    }
  }, {
    key: 'renderHeader',
    value: function renderHeader() {
      this.columnmanager.renderHeader();
    }
  }, {
    key: 'renderBody',
    value: function renderBody() {
      this.bodyRenderer.render();
    }
  }, {
    key: 'setDimensions',
    value: function setDimensions() {
      this.columnmanager.setDimensions();

      this.setBodyWidth();

      _dom2.default.style(this.bodyScrollable, {
        marginTop: _dom2.default.style(this.header, 'height') + 'px'
      });

      _dom2.default.style((0, _dom2.default)('table', this.bodyScrollable), {
        margin: 0
      });
    }
  }, {
    key: 'setBodyWidth',
    value: function setBodyWidth() {
      var width = _dom2.default.style(this.header, 'width');

      _dom2.default.style(this.bodyScrollable, { width: width + 'px' });
    }
  }, {
    key: 'getColumn',
    value: function getColumn(colIndex) {
      return this.datamanager.getColumn(colIndex);
    }
  }, {
    key: 'getCell',
    value: function getCell(colIndex, rowIndex) {
      return this.datamanager.getCell(colIndex, rowIndex);
    }
  }, {
    key: 'getColumnHeaderElement',
    value: function getColumnHeaderElement(colIndex) {
      return this.columnmanager.getColumnHeaderElement(colIndex);
    }
  }, {
    key: 'getViewportHeight',
    value: function getViewportHeight() {
      if (!this.viewportHeight) {
        this.viewportHeight = _dom2.default.style(this.bodyScrollable, 'height');
      }

      return this.viewportHeight;
    }
  }, {
    key: 'sortColumn',
    value: function sortColumn(colIndex, sortOrder) {
      this.columnmanager.sortColumn(colIndex, sortOrder);
    }
  }, {
    key: 'removeColumn',
    value: function removeColumn(colIndex) {
      this.columnmanager.removeColumn(colIndex);
    }
  }, {
    key: 'scrollToLastColumn',
    value: function scrollToLastColumn() {
      this.datatableWrapper.scrollLeft = 9999;
    }
  }, {
    key: 'freeze',
    value: function freeze() {
      _dom2.default.style(this.freezeContainer, {
        display: ''
      });
    }
  }, {
    key: 'unfreeze',
    value: function unfreeze() {
      _dom2.default.style(this.freezeContainer, {
        display: 'none'
      });
    }
  }, {
    key: 'fireEvent',
    value: function fireEvent(eventName) {
      for (var _len = arguments.length, args = Array(_len > 1 ? _len - 1 : 0), _key = 1; _key < _len; _key++) {
        args[_key - 1] = arguments[_key];
      }

      this.events[eventName].apply(this, args);
    }
  }, {
    key: 'log',
    value: function log() {
      if (this.options.enableLogs) {
        console.log.apply(console, arguments);
      }
    }
  }]);

  return DataTable;
}();

DataTable.instances = 0;

exports.default = DataTable;
module.exports = exports['default'];

/***/ }),
/* 6 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.DataError = undefined;

var _typeof = typeof Symbol === "function" && typeof Symbol.iterator === "symbol" ? function (obj) { return typeof obj; } : function (obj) { return obj && typeof Symbol === "function" && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; };

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _utils = __webpack_require__(1);

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

function _extendableBuiltin(cls) {
  function ExtendableBuiltin() {
    var instance = Reflect.construct(cls, Array.from(arguments));
    Object.setPrototypeOf(instance, Object.getPrototypeOf(this));
    return instance;
  }

  ExtendableBuiltin.prototype = Object.create(cls.prototype, {
    constructor: {
      value: cls,
      enumerable: false,
      writable: true,
      configurable: true
    }
  });

  if (Object.setPrototypeOf) {
    Object.setPrototypeOf(ExtendableBuiltin, cls);
  } else {
    ExtendableBuiltin.__proto__ = cls;
  }

  return ExtendableBuiltin;
}

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var DataManager = function () {
  function DataManager(options) {
    _classCallCheck(this, DataManager);

    this.options = options;
    this.sortRows = (0, _utils.promisify)(this.sortRows, this);
    this.switchColumn = (0, _utils.promisify)(this.switchColumn, this);
    this.removeColumn = (0, _utils.promisify)(this.removeColumn, this);
  }

  _createClass(DataManager, [{
    key: 'init',
    value: function init(data) {
      if (!data) {
        data = this.options.data;
      }

      this.data = data;

      this.rowCount = 0;
      this.columns = [];
      this.rows = [];

      this.prepareColumns();
      this.prepareRows();

      this.prepareNumericColumns();
    }

    // computed property

  }, {
    key: 'prepareColumns',
    value: function prepareColumns() {
      this.columns = [];
      this.validateColumns();
      this.prepareDefaultColumns();
      this.prepareHeader();
    }
  }, {
    key: 'prepareDefaultColumns',
    value: function prepareDefaultColumns() {
      if (this.options.addCheckboxColumn && !this.hasColumnById('_checkbox')) {
        var cell = {
          id: '_checkbox',
          content: this.getCheckboxHTML(),
          editable: false,
          resizable: false,
          sortable: false,
          focusable: false,
          dropdown: false,
          width: 25
        };
        this.columns.push(cell);
      }

      if (this.options.addSerialNoColumn && !this.hasColumnById('_rowIndex')) {
        var _cell = {
          id: '_rowIndex',
          content: '',
          align: 'center',
          editable: false,
          resizable: false,
          focusable: false,
          dropdown: false,
          width: 30
        };

        this.columns.push(_cell);
      }
    }
  }, {
    key: 'prepareRow',
    value: function prepareRow(row, i) {
      var _this = this;

      var baseRowCell = {
        rowIndex: i
      };

      return row.map(function (cell, i) {
        return _this.prepareCell(cell, i);
      }).map(function (cell) {
        return Object.assign({}, baseRowCell, cell);
      });
    }
  }, {
    key: 'prepareHeader',
    value: function prepareHeader() {
      var _this2 = this;

      var columns = this.columns.concat(this.options.columns);
      var baseCell = {
        isHeader: 1,
        editable: true,
        sortable: true,
        resizable: true,
        focusable: true,
        dropdown: true,
        format: function format(value) {
          if (value === null || value === undefined) {
            return '';
          }
          return value + '';
        }
      };

      this.columns = columns.map(function (cell, i) {
        return _this2.prepareCell(cell, i);
      }).map(function (col) {
        return Object.assign({}, baseCell, col);
      }).map(function (col) {
        col.id = col.id || col.content;
        return col;
      });
    }
  }, {
    key: 'prepareCell',
    value: function prepareCell(content, i) {
      var cell = {
        content: '',
        align: 'left',
        sortOrder: 'none',
        colIndex: i,
        column: this.columns[i],
        width: 0
      };

      if (content !== null && (typeof content === 'undefined' ? 'undefined' : _typeof(content)) === 'object') {
        // passed as column/header
        Object.assign(cell, content);
      } else {
        cell.content = content;
      }

      return cell;
    }
  }, {
    key: 'prepareNumericColumns',
    value: function prepareNumericColumns() {
      var row0 = this.getRow(0);
      if (!row0) return;
      this.columns = this.columns.map(function (column, i) {

        var cellValue = row0[i].content;
        if (!column.align && cellValue && (0, _utils.isNumeric)(cellValue)) {
          column.align = 'right';
        }

        return column;
      });
    }
  }, {
    key: 'prepareRows',
    value: function prepareRows() {
      var _this3 = this;

      this.validateData(this.data);

      this.rows = this.data.map(function (d, i) {
        var index = _this3._getNextRowCount();

        var row = [];

        if (Array.isArray(d)) {
          // row is an array
          if (_this3.options.addCheckboxColumn) {
            row.push(_this3.getCheckboxHTML());
          }
          if (_this3.options.addSerialNoColumn) {
            row.push(index + 1 + '');
          }
          row = row.concat(d);
        } else {
          // row is a dict
          var _iteratorNormalCompletion = true;
          var _didIteratorError = false;
          var _iteratorError = undefined;

          try {
            for (var _iterator = _this3.columns[Symbol.iterator](), _step; !(_iteratorNormalCompletion = (_step = _iterator.next()).done); _iteratorNormalCompletion = true) {
              var col = _step.value;

              if (col.id === '_checkbox') {
                row.push(_this3.getCheckboxHTML());
              } else if (col.id === '_rowIndex') {
                row.push(index + 1 + '');
              } else {
                row.push(col.format(d[col.id]));
              }
            }
          } catch (err) {
            _didIteratorError = true;
            _iteratorError = err;
          } finally {
            try {
              if (!_iteratorNormalCompletion && _iterator.return) {
                _iterator.return();
              }
            } finally {
              if (_didIteratorError) {
                throw _iteratorError;
              }
            }
          }
        }

        return _this3.prepareRow(row, index);
      });
    }
  }, {
    key: 'validateColumns',
    value: function validateColumns() {
      var columns = this.options.columns;
      if (!Array.isArray(columns)) {
        throw new DataError('`columns` must be an array');
      }

      columns.forEach(function (column, i) {
        if (typeof column !== 'string' && (typeof column === 'undefined' ? 'undefined' : _typeof(column)) !== 'object') {
          throw new DataError('column "' + i + '" must be a string or an object');
        }
      });
    }
  }, {
    key: 'validateData',
    value: function validateData(data) {
      if (Array.isArray(data) && (data.length === 0 || Array.isArray(data[0]) || _typeof(data[0]) === 'object')) {
        return true;
      }
      throw new DataError('`data` must be an array of arrays or objects');
    }
  }, {
    key: 'appendRows',
    value: function appendRows(rows) {
      this.validateData(rows);

      this.rows = this.rows.concat(this.prepareRows(rows));
    }
  }, {
    key: 'sortRows',
    value: function sortRows(colIndex) {
      var sortOrder = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 'none';

      colIndex = +colIndex;

      // reset sortOrder and update for colIndex
      this.getColumns().map(function (col) {
        if (col.colIndex === colIndex) {
          col.sortOrder = sortOrder;
        } else {
          col.sortOrder = 'none';
        }
      });

      this._sortRows(colIndex, sortOrder);
    }
  }, {
    key: '_sortRows',
    value: function _sortRows(colIndex, sortOrder) {

      if (this.currentSort.colIndex === colIndex) {
        // reverse the array if only sortOrder changed
        if (this.currentSort.sortOrder === 'asc' && sortOrder === 'desc' || this.currentSort.sortOrder === 'desc' && sortOrder === 'asc') {
          this.reverseArray(this.rows);
          this.currentSort.sortOrder = sortOrder;
          return;
        }
      }

      this.rows.sort(function (a, b) {
        var _aIndex = a[0].rowIndex;
        var _bIndex = b[0].rowIndex;
        var _a = a[colIndex].content;
        var _b = b[colIndex].content;

        if (sortOrder === 'none') {
          return _aIndex - _bIndex;
        } else if (sortOrder === 'asc') {
          if (_a < _b) return -1;
          if (_a > _b) return 1;
          if (_a === _b) return 0;
        } else if (sortOrder === 'desc') {
          if (_a < _b) return 1;
          if (_a > _b) return -1;
          if (_a === _b) return 0;
        }
        return 0;
      });

      if (this.hasColumnById('_rowIndex')) {
        // update row index
        var srNoColIndex = this.getColumnIndexById('_rowIndex');
        this.rows = this.rows.map(function (row, index) {
          return row.map(function (cell) {
            if (cell.colIndex === srNoColIndex) {
              cell.content = index + 1 + '';
            }
            return cell;
          });
        });
      }
    }
  }, {
    key: 'reverseArray',
    value: function reverseArray(array) {
      var left = null;
      var right = null;
      var length = array.length;

      for (left = 0, right = length - 1; left < right; left += 1, right -= 1) {
        var temporary = array[left];

        array[left] = array[right];
        array[right] = temporary;
      }
    }
  }, {
    key: 'switchColumn',
    value: function switchColumn(index1, index2) {
      // update columns
      var temp = this.columns[index1];
      this.columns[index1] = this.columns[index2];
      this.columns[index2] = temp;

      this.columns[index1].colIndex = index1;
      this.columns[index2].colIndex = index2;

      // update rows
      this.rows = this.rows.map(function (row) {
        var newCell1 = Object.assign({}, row[index1], { colIndex: index2 });
        var newCell2 = Object.assign({}, row[index2], { colIndex: index1 });

        var newRow = row.map(function (cell) {
          // make object copy
          return Object.assign({}, cell);
        });

        newRow[index2] = newCell1;
        newRow[index1] = newCell2;

        return newRow;
      });
    }
  }, {
    key: 'removeColumn',
    value: function removeColumn(index) {
      index = +index;
      var filter = function filter(cell) {
        return cell.colIndex !== index;
      };
      var map = function map(cell, i) {
        return Object.assign({}, cell, { colIndex: i });
      };
      // update columns
      this.columns = this.columns.filter(filter).map(map);

      // update rows
      this.rows = this.rows.map(function (row) {
        var newRow = row.filter(filter).map(map);

        return newRow;
      });
    }
  }, {
    key: 'updateRow',
    value: function updateRow(row, rowIndex) {
      if (row.length < this.columns.length) {
        if (this.hasColumnById('_rowIndex')) {
          var val = rowIndex + 1 + '';

          row = [val].concat(row);
        }

        if (this.hasColumnById('_checkbox')) {
          var _val = '<input type="checkbox" />';

          row = [_val].concat(row);
        }
      }

      var _row = this.prepareRow(row, rowIndex);
      var index = this.rows.findIndex(function (row) {
        return row[0].rowIndex === rowIndex;
      });
      this.rows[index] = _row;

      return _row;
    }
  }, {
    key: 'updateCell',
    value: function updateCell(colIndex, rowIndex, options) {
      var cell = void 0;
      if ((typeof colIndex === 'undefined' ? 'undefined' : _typeof(colIndex)) === 'object') {
        // cell object was passed,
        // must have colIndex, rowIndex
        cell = colIndex;
        colIndex = cell.colIndex;
        rowIndex = cell.rowIndex;
        // the object passed must be merged with original cell
        options = cell;
      }
      cell = this.getCell(colIndex, rowIndex);

      // mutate object directly
      for (var key in options) {
        var newVal = options[key];
        if (newVal !== undefined) {
          cell[key] = newVal;
        }
      }

      return cell;
    }
  }, {
    key: 'updateColumn',
    value: function updateColumn(colIndex, keyValPairs) {
      var column = this.getColumn(colIndex);
      for (var key in keyValPairs) {
        var newVal = keyValPairs[key];
        if (newVal !== undefined) {
          column[key] = newVal;
        }
      }
      return column;
    }
  }, {
    key: 'getRowCount',
    value: function getRowCount() {
      return this.rowCount;
    }
  }, {
    key: '_getNextRowCount',
    value: function _getNextRowCount() {
      var val = this.rowCount;

      this.rowCount++;
      return val;
    }
  }, {
    key: 'getRows',
    value: function getRows(start, end) {
      return this.rows.slice(start, end);
    }
  }, {
    key: 'getColumns',
    value: function getColumns(skipStandardColumns) {
      var columns = this.columns;

      if (skipStandardColumns) {
        columns = columns.slice(this.getStandardColumnCount());
      }

      return columns;
    }
  }, {
    key: 'getStandardColumnCount',
    value: function getStandardColumnCount() {
      if (this.options.addCheckboxColumn && this.options.addSerialNoColumn) {
        return 2;
      }

      if (this.options.addCheckboxColumn || this.options.addSerialNoColumn) {
        return 1;
      }

      return 0;
    }
  }, {
    key: 'getColumnCount',
    value: function getColumnCount(skipStandardColumns) {
      var val = this.columns.length;

      if (skipStandardColumns) {
        val = val - this.getStandardColumnCount();
      }

      return val;
    }
  }, {
    key: 'getColumn',
    value: function getColumn(colIndex) {
      colIndex = +colIndex;
      return this.columns.find(function (col) {
        return col.colIndex === colIndex;
      });
    }
  }, {
    key: 'getRow',
    value: function getRow(rowIndex) {
      rowIndex = +rowIndex;
      return this.rows.find(function (row) {
        return row[0].rowIndex === rowIndex;
      });
    }
  }, {
    key: 'getCell',
    value: function getCell(colIndex, rowIndex) {
      rowIndex = +rowIndex;
      colIndex = +colIndex;
      return this.rows.find(function (row) {
        return row[0].rowIndex === rowIndex;
      })[colIndex];
    }
  }, {
    key: 'get',
    value: function get() {
      return {
        columns: this.columns,
        rows: this.rows
      };
    }
  }, {
    key: 'hasColumn',
    value: function hasColumn(name) {
      return Boolean(this.columns.find(function (col) {
        return col.content === name;
      }));
    }
  }, {
    key: 'hasColumnById',
    value: function hasColumnById(id) {
      return Boolean(this.columns.find(function (col) {
        return col.id === id;
      }));
    }
  }, {
    key: 'getColumnIndex',
    value: function getColumnIndex(name) {
      return this.columns.findIndex(function (col) {
        return col.content === name;
      });
    }
  }, {
    key: 'getColumnIndexById',
    value: function getColumnIndexById(id) {
      return this.columns.findIndex(function (col) {
        return col.id === id;
      });
    }
  }, {
    key: 'getCheckboxHTML',
    value: function getCheckboxHTML() {
      return '<input type="checkbox" />';
    }
  }, {
    key: 'currentSort',
    get: function get() {
      var col = this.columns.find(function (col) {
        return col.sortOrder !== 'none';
      });
      return col || {
        colIndex: -1,
        sortOrder: 'none'
      };
    }
  }]);

  return DataManager;
}();

// Custom Errors


exports.default = DataManager;

var DataError = exports.DataError = function (_extendableBuiltin2) {
  _inherits(DataError, _extendableBuiltin2);

  function DataError() {
    _classCallCheck(this, DataError);

    return _possibleConstructorReturn(this, (DataError.__proto__ || Object.getPrototypeOf(DataError)).apply(this, arguments));
  }

  return DataError;
}(_extendableBuiltin(TypeError));

;

/***/ }),
/* 7 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _typeof = typeof Symbol === "function" && typeof Symbol.iterator === "symbol" ? function (obj) { return typeof obj; } : function (obj) { return obj && typeof Symbol === "function" && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; };

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _utils = __webpack_require__(1);

var _keyboard = __webpack_require__(2);

var _keyboard2 = _interopRequireDefault(_keyboard);

var _dom = __webpack_require__(0);

var _dom2 = _interopRequireDefault(_dom);

var _columnmanager = __webpack_require__(3);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _toConsumableArray(arr) { if (Array.isArray(arr)) { for (var i = 0, arr2 = Array(arr.length); i < arr.length; i++) { arr2[i] = arr[i]; } return arr2; } else { return Array.from(arr); } }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var CellManager = function () {
  function CellManager(instance) {
    _classCallCheck(this, CellManager);

    this.instance = instance;
    this.wrapper = this.instance.wrapper;
    this.options = this.instance.options;
    this.style = this.instance.style;
    this.bodyScrollable = this.instance.bodyScrollable;
    this.columnmanager = this.instance.columnmanager;
    this.rowmanager = this.instance.rowmanager;
    this.datamanager = this.instance.datamanager;

    this.bindEvents();
  }

  _createClass(CellManager, [{
    key: 'bindEvents',
    value: function bindEvents() {
      this.bindFocusCell();
      this.bindEditCell();
      this.bindKeyboardSelection();
      this.bindCopyCellContents();
      this.bindMouseEvents();
    }
  }, {
    key: 'bindFocusCell',
    value: function bindFocusCell() {
      this.bindKeyboardNav();
    }
  }, {
    key: 'bindEditCell',
    value: function bindEditCell() {
      var _this = this;

      this.$editingCell = null;

      _dom2.default.on(this.bodyScrollable, 'dblclick', '.data-table-col', function (e, cell) {
        _this.activateEditing(cell);
      });

      _keyboard2.default.on('enter', function (e) {
        if (_this.$focusedCell && !_this.$editingCell) {
          // enter keypress on focused cell
          _this.activateEditing(_this.$focusedCell);
        } else if (_this.$editingCell) {
          // enter keypress on editing cell
          _this.submitEditing();
          _this.deactivateEditing();
        }
      });
    }
  }, {
    key: 'bindKeyboardNav',
    value: function bindKeyboardNav() {
      var _this2 = this;

      var focusCell = function focusCell(direction) {
        if (!_this2.$focusedCell || _this2.$editingCell) {
          return false;
        }

        var $cell = _this2.$focusedCell;

        if (direction === 'left') {
          $cell = _this2.getLeftCell$($cell);
        } else if (direction === 'right' || direction === 'tab') {
          $cell = _this2.getRightCell$($cell);
        } else if (direction === 'up') {
          $cell = _this2.getAboveCell$($cell);
        } else if (direction === 'down') {
          $cell = _this2.getBelowCell$($cell);
        }

        _this2.focusCell($cell);
        return true;
      };

      var focusLastCell = function focusLastCell(direction) {
        if (!_this2.$focusedCell || _this2.$editingCell) {
          return false;
        }

        var $cell = _this2.$focusedCell;

        var _$$data = _dom2.default.data($cell),
            rowIndex = _$$data.rowIndex,
            colIndex = _$$data.colIndex;

        if (direction === 'left') {
          $cell = _this2.getLeftMostCell$(rowIndex);
        } else if (direction === 'right') {
          $cell = _this2.getRightMostCell$(rowIndex);
        } else if (direction === 'up') {
          $cell = _this2.getTopMostCell$(colIndex);
        } else if (direction === 'down') {
          $cell = _this2.getBottomMostCell$(colIndex);
        }

        _this2.focusCell($cell);
        return true;
      };

      ['left', 'right', 'up', 'down', 'tab'].map(function (direction) {
        return _keyboard2.default.on(direction, function () {
          return focusCell(direction);
        });
      });

      ['left', 'right', 'up', 'down'].map(function (direction) {
        return _keyboard2.default.on('ctrl+' + direction, function () {
          return focusLastCell(direction);
        });
      });

      _keyboard2.default.on('esc', function () {
        _this2.deactivateEditing();
      });
    }
  }, {
    key: 'bindKeyboardSelection',
    value: function bindKeyboardSelection() {
      var _this3 = this;

      var getNextSelectionCursor = function getNextSelectionCursor(direction) {
        var $selectionCursor = _this3.getSelectionCursor();

        if (direction === 'left') {
          $selectionCursor = _this3.getLeftCell$($selectionCursor);
        } else if (direction === 'right') {
          $selectionCursor = _this3.getRightCell$($selectionCursor);
        } else if (direction === 'up') {
          $selectionCursor = _this3.getAboveCell$($selectionCursor);
        } else if (direction === 'down') {
          $selectionCursor = _this3.getBelowCell$($selectionCursor);
        }

        return $selectionCursor;
      };

      ['left', 'right', 'up', 'down'].map(function (direction) {
        return _keyboard2.default.on('shift+' + direction, function () {
          return _this3.selectArea(getNextSelectionCursor(direction));
        });
      });
    }
  }, {
    key: 'bindCopyCellContents',
    value: function bindCopyCellContents() {
      var _this4 = this;

      _keyboard2.default.on('ctrl+c', function () {
        _this4.copyCellContents(_this4.$focusedCell, _this4.$selectionCursor);
      });
    }
  }, {
    key: 'bindMouseEvents',
    value: function bindMouseEvents() {
      var _this5 = this;

      var mouseDown = null;

      _dom2.default.on(this.bodyScrollable, 'mousedown', '.data-table-col', function (e) {
        mouseDown = true;
        _this5.focusCell((0, _dom2.default)(e.delegatedTarget));
      });

      _dom2.default.on(this.bodyScrollable, 'mouseup', function () {
        mouseDown = false;
      });

      var selectArea = function selectArea(e) {
        if (!mouseDown) return;
        _this5.selectArea((0, _dom2.default)(e.delegatedTarget));
      };

      _dom2.default.on(this.bodyScrollable, 'mousemove', '.data-table-col', (0, _utils.throttle)(selectArea, 50));
    }
  }, {
    key: 'focusCell',
    value: function focusCell($cell) {
      var _ref = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {},
          _ref$skipClearSelecti = _ref.skipClearSelection,
          skipClearSelection = _ref$skipClearSelecti === undefined ? 0 : _ref$skipClearSelecti;

      if (!$cell) return;

      // don't focus if already editing cell
      if ($cell === this.$editingCell) return;

      var _$$data2 = _dom2.default.data($cell),
          colIndex = _$$data2.colIndex,
          isHeader = _$$data2.isHeader;

      if (isHeader) {
        return;
      }

      var column = this.columnmanager.getColumn(colIndex);
      if (column.focusable === false) {
        return;
      }

      this.deactivateEditing();
      if (!skipClearSelection) {
        this.clearSelection();
      }

      if (this.$focusedCell) {
        this.$focusedCell.classList.remove('selected');
      }

      this.$focusedCell = $cell;
      $cell.classList.add('selected');

      // so that keyboard nav works
      $cell.focus();

      this.highlightRowColumnHeader($cell);
      this.scrollToCell($cell);
    }
  }, {
    key: 'highlightRowColumnHeader',
    value: function highlightRowColumnHeader($cell) {
      var _$$data3 = _dom2.default.data($cell),
          colIndex = _$$data3.colIndex,
          rowIndex = _$$data3.rowIndex;

      var _colIndex = this.datamanager.getColumnIndexById('_rowIndex');
      var colHeaderSelector = '.data-table-header .data-table-col[data-col-index="' + colIndex + '"]';
      var rowHeaderSelector = '.data-table-col[data-row-index="' + rowIndex + '"][data-col-index="' + _colIndex + '"]';

      if (this.lastHeaders) {
        _dom2.default.removeStyle(this.lastHeaders, 'backgroundColor');
      }

      var colHeader = (0, _dom2.default)(colHeaderSelector, this.wrapper);
      var rowHeader = (0, _dom2.default)(rowHeaderSelector, this.wrapper);

      _dom2.default.style([colHeader, rowHeader], {
        backgroundColor: '#f5f7fa' // light-bg
      });

      this.lastHeaders = [colHeader, rowHeader];
    }
  }, {
    key: 'selectAreaOnClusterChanged',
    value: function selectAreaOnClusterChanged() {
      if (!(this.$focusedCell && this.$selectionCursor)) return;

      var _$$data4 = _dom2.default.data(this.$selectionCursor),
          colIndex = _$$data4.colIndex,
          rowIndex = _$$data4.rowIndex;

      var $cell = this.getCell$(colIndex, rowIndex);

      if (!$cell || $cell === this.$selectionCursor) return;

      // selectArea needs $focusedCell
      var fCell = _dom2.default.data(this.$focusedCell);
      this.$focusedCell = this.getCell$(fCell.colIndex, fCell.rowIndex);

      this.selectArea($cell);
    }
  }, {
    key: 'focusCellOnClusterChanged',
    value: function focusCellOnClusterChanged() {
      if (!this.$focusedCell) return;

      var _$$data5 = _dom2.default.data(this.$focusedCell),
          colIndex = _$$data5.colIndex,
          rowIndex = _$$data5.rowIndex;

      var $cell = this.getCell$(colIndex, rowIndex);

      if (!$cell) return;
      // this function is called after selectAreaOnClusterChanged,
      // focusCell calls clearSelection which resets the area selection
      // so a flag to skip it
      this.focusCell($cell, { skipClearSelection: 1 });
    }
  }, {
    key: 'selectArea',
    value: function selectArea($selectionCursor) {
      if (!this.$focusedCell) return;

      if (this._selectArea(this.$focusedCell, $selectionCursor)) {
        // valid selection
        this.$selectionCursor = $selectionCursor;
      }
    }
  }, {
    key: '_selectArea',
    value: function _selectArea($cell1, $cell2) {
      var _this6 = this;

      if ($cell1 === $cell2) return false;

      var cells = this.getCellsInRange($cell1, $cell2);
      if (!cells) return false;

      this.clearSelection();
      cells.map(function (index) {
        return _this6.getCell$.apply(_this6, _toConsumableArray(index));
      }).map(function ($cell) {
        return $cell.classList.add('highlight');
      });
      return true;
    }
  }, {
    key: 'getCellsInRange',
    value: function getCellsInRange($cell1, $cell2) {
      var colIndex1 = void 0,
          rowIndex1 = void 0,
          colIndex2 = void 0,
          rowIndex2 = void 0;

      if (typeof $cell1 === 'number') {
        var _arguments = Array.prototype.slice.call(arguments);

        colIndex1 = _arguments[0];
        rowIndex1 = _arguments[1];
        colIndex2 = _arguments[2];
        rowIndex2 = _arguments[3];
      } else if ((typeof $cell1 === 'undefined' ? 'undefined' : _typeof($cell1)) === 'object') {

        if (!($cell1 && $cell2)) {
          return false;
        }

        var cell1 = _dom2.default.data($cell1);
        var cell2 = _dom2.default.data($cell2);

        colIndex1 = cell1.colIndex;
        rowIndex1 = cell1.rowIndex;
        colIndex2 = cell2.colIndex;
        rowIndex2 = cell2.rowIndex;
      }

      if (rowIndex1 > rowIndex2) {
        var _ref2 = [rowIndex2, rowIndex1];
        rowIndex1 = _ref2[0];
        rowIndex2 = _ref2[1];
      }

      if (colIndex1 > colIndex2) {
        var _ref3 = [colIndex2, colIndex1];
        colIndex1 = _ref3[0];
        colIndex2 = _ref3[1];
      }

      if (this.isStandardCell(colIndex1) || this.isStandardCell(colIndex2)) {
        return false;
      }

      var cells = [];
      var colIndex = colIndex1;
      var rowIndex = rowIndex1;
      var rowIndices = [];

      while (rowIndex <= rowIndex2) {
        rowIndices.push(rowIndex);
        rowIndex++;
      }

      rowIndices.map(function (rowIndex) {
        while (colIndex <= colIndex2) {
          cells.push([colIndex, rowIndex]);
          colIndex++;
        }
        colIndex = colIndex1;
      });

      return cells;
    }
  }, {
    key: 'clearSelection',
    value: function clearSelection() {
      _dom2.default.each('.data-table-col.highlight', this.bodyScrollable).map(function (cell) {
        return cell.classList.remove('highlight');
      });

      this.$selectionCursor = null;
    }
  }, {
    key: 'getSelectionCursor',
    value: function getSelectionCursor() {
      return this.$selectionCursor || this.$focusedCell;
    }
  }, {
    key: 'activateEditing',
    value: function activateEditing($cell) {
      var _$$data6 = _dom2.default.data($cell),
          rowIndex = _$$data6.rowIndex,
          colIndex = _$$data6.colIndex;

      var col = this.columnmanager.getColumn(colIndex);
      if (col && (col.editable === false || col.focusable === false)) {
        return;
      }

      var cell = this.getCell(colIndex, rowIndex);
      if (cell && cell.editable === false) {
        return;
      }

      if (this.$editingCell) {
        var _$$data7 = _dom2.default.data(this.$editingCell),
            _rowIndex = _$$data7._rowIndex,
            _colIndex = _$$data7._colIndex;

        if (rowIndex === _rowIndex && colIndex === _colIndex) {
          // editing the same cell
          return;
        }
      }

      this.$editingCell = $cell;
      $cell.classList.add('editing');

      var $editCell = (0, _dom2.default)('.edit-cell', $cell);
      $editCell.innerHTML = '';

      var editor = this.getEditor(colIndex, rowIndex, cell.content, $editCell);

      if (editor) {
        this.currentCellEditor = editor;
        // initialize editing input with cell value
        editor.initValue(cell.content, rowIndex, col);
      }
    }
  }, {
    key: 'deactivateEditing',
    value: function deactivateEditing() {
      // keep focus on the cell so that keyboard navigation works
      if (this.$focusedCell) this.$focusedCell.focus();

      if (!this.$editingCell) return;
      this.$editingCell.classList.remove('editing');
      this.$editingCell = null;
    }
  }, {
    key: 'getEditor',
    value: function getEditor(colIndex, rowIndex, value, parent) {
      // debugger;
      var obj = this.options.getEditor(colIndex, rowIndex, value, parent);
      if (obj && obj.setValue) return obj;

      // editing fallback
      var $input = _dom2.default.create('input', {
        type: 'text',
        inside: parent
      });

      return {
        initValue: function initValue(value) {
          $input.focus();
          $input.value = value;
        },
        getValue: function getValue() {
          return $input.value;
        },
        setValue: function setValue(value) {
          $input.value = value;
        }
      };
    }
  }, {
    key: 'submitEditing',
    value: function submitEditing() {
      var _this7 = this;

      if (!this.$editingCell) return;
      var $cell = this.$editingCell;

      var _$$data8 = _dom2.default.data($cell),
          rowIndex = _$$data8.rowIndex,
          colIndex = _$$data8.colIndex;

      var col = this.datamanager.getColumn(colIndex);

      if ($cell) {
        var editor = this.currentCellEditor;

        if (editor) {
          var value = editor.getValue();
          var done = editor.setValue(value, rowIndex, col);
          var oldValue = this.getCell(colIndex, rowIndex).content;

          // update cell immediately
          this.updateCell(colIndex, rowIndex, value);
          $cell.focus();

          if (done && done.then) {
            // revert to oldValue if promise fails
            done.catch(function (e) {
              console.log(e);
              _this7.updateCell(colIndex, rowIndex, oldValue);
            });
          }
        }
      }

      this.currentCellEditor = null;
    }
  }, {
    key: 'copyCellContents',
    value: function copyCellContents($cell1, $cell2) {
      var _this8 = this;

      if (!$cell2 && $cell1) {
        // copy only focusedCell
        var _$$data9 = _dom2.default.data($cell1),
            colIndex = _$$data9.colIndex,
            rowIndex = _$$data9.rowIndex;

        var cell = this.getCell(colIndex, rowIndex);
        (0, _utils.copyTextToClipboard)(cell.content);
        return;
      }
      var cells = this.getCellsInRange($cell1, $cell2);

      if (!cells) return;

      var values = cells
      // get cell objects
      .map(function (index) {
        return _this8.getCell.apply(_this8, _toConsumableArray(index));
      })
      // convert to array of rows
      .reduce(function (acc, curr) {
        var rowIndex = curr.rowIndex;

        acc[rowIndex] = acc[rowIndex] || [];
        acc[rowIndex].push(curr.content);

        return acc;
      }, [])
      // join values by tab
      .map(function (row) {
        return row.join('\t');
      })
      // join rows by newline
      .join('\n');

      (0, _utils.copyTextToClipboard)(values);
    }
  }, {
    key: 'updateCell',
    value: function updateCell(colIndex, rowIndex, value) {
      var cell = this.datamanager.updateCell(colIndex, rowIndex, {
        content: value
      });
      this.refreshCell(cell);
    }
  }, {
    key: 'refreshCell',
    value: function refreshCell(cell) {
      var $cell = (0, _dom2.default)(this.cellSelector(cell.colIndex, cell.rowIndex), this.bodyScrollable);
      $cell.innerHTML = this.getCellContent(cell);
    }
  }, {
    key: 'isStandardCell',
    value: function isStandardCell(colIndex) {
      // Standard cells are in Sr. No and Checkbox column
      return colIndex < this.columnmanager.getFirstColumnIndex();
    }
  }, {
    key: 'getCell$',
    value: function getCell$(colIndex, rowIndex) {
      return (0, _dom2.default)(this.cellSelector(colIndex, rowIndex), this.bodyScrollable);
    }
  }, {
    key: 'getAboveCell$',
    value: function getAboveCell$($cell) {
      var _$$data10 = _dom2.default.data($cell),
          colIndex = _$$data10.colIndex;

      var $aboveRow = $cell.parentElement.previousElementSibling;

      return (0, _dom2.default)('[data-col-index="' + colIndex + '"]', $aboveRow);
    }
  }, {
    key: 'getBelowCell$',
    value: function getBelowCell$($cell) {
      var _$$data11 = _dom2.default.data($cell),
          colIndex = _$$data11.colIndex;

      var $belowRow = $cell.parentElement.nextElementSibling;

      return (0, _dom2.default)('[data-col-index="' + colIndex + '"]', $belowRow);
    }
  }, {
    key: 'getLeftCell$',
    value: function getLeftCell$($cell) {
      return $cell.previousElementSibling;
    }
  }, {
    key: 'getRightCell$',
    value: function getRightCell$($cell) {
      return $cell.nextElementSibling;
    }
  }, {
    key: 'getLeftMostCell$',
    value: function getLeftMostCell$(rowIndex) {
      return this.getCell$(this.columnmanager.getFirstColumnIndex(), rowIndex);
    }
  }, {
    key: 'getRightMostCell$',
    value: function getRightMostCell$(rowIndex) {
      return this.getCell$(this.columnmanager.getLastColumnIndex(), rowIndex);
    }
  }, {
    key: 'getTopMostCell$',
    value: function getTopMostCell$(colIndex) {
      return this.getCell$(colIndex, this.rowmanager.getFirstRowIndex());
    }
  }, {
    key: 'getBottomMostCell$',
    value: function getBottomMostCell$(colIndex) {
      return this.getCell$(colIndex, this.rowmanager.getLastRowIndex());
    }
  }, {
    key: 'getCell',
    value: function getCell(colIndex, rowIndex) {
      return this.instance.datamanager.getCell(colIndex, rowIndex);
    }
  }, {
    key: 'getCellAttr',
    value: function getCellAttr($cell) {
      return this.instance.getCellAttr($cell);
    }
  }, {
    key: 'getRowHeight',
    value: function getRowHeight() {
      return _dom2.default.style((0, _dom2.default)('.data-table-row', this.bodyScrollable), 'height');
    }
  }, {
    key: 'scrollToCell',
    value: function scrollToCell($cell) {
      if (_dom2.default.inViewport($cell, this.bodyScrollable)) return false;

      var _$$data12 = _dom2.default.data($cell),
          rowIndex = _$$data12.rowIndex;

      this.rowmanager.scrollToRow(rowIndex);
      return false;
    }
  }, {
    key: 'getRowCountPerPage',
    value: function getRowCountPerPage() {
      return Math.ceil(this.instance.getViewportHeight() / this.getRowHeight());
    }
  }, {
    key: 'getCellHTML',
    value: function getCellHTML(cell) {
      var rowIndex = cell.rowIndex,
          colIndex = cell.colIndex,
          isHeader = cell.isHeader;

      var dataAttr = (0, _utils.makeDataAttributeString)({
        rowIndex: rowIndex,
        colIndex: colIndex,
        isHeader: isHeader
      });

      return '\n      <td class="data-table-col noselect" ' + dataAttr + ' tabindex="0">\n        ' + this.getCellContent(cell) + '\n      </td>\n    ';
    }
  }, {
    key: 'getCellContent',
    value: function getCellContent(cell) {
      var isHeader = cell.isHeader;


      var editable = !isHeader && cell.editable !== false;
      var editCellHTML = editable ? this.getEditCellHTML() : '';

      var sortable = isHeader && cell.sortable !== false;
      var sortIndicator = sortable ? '<span class="sort-indicator"></span>' : '';

      var resizable = isHeader && cell.resizable !== false;
      var resizeColumn = resizable ? '<span class="column-resizer"></span>' : '';

      var hasDropdown = isHeader && cell.dropdown !== false;
      var dropdown = hasDropdown ? '<div class="data-table-dropdown">' + (0, _columnmanager.getDropdownHTML)() + '</div>' : '';

      var contentHTML = !cell.isHeader && cell.column.format ? cell.column.format(cell.content) : cell.content;

      return '\n      <div class="content ellipsis">\n        ' + contentHTML + '\n        ' + sortIndicator + '\n        ' + resizeColumn + '\n        ' + dropdown + '\n      </div>\n      ' + editCellHTML + '\n    ';
    }
  }, {
    key: 'getEditCellHTML',
    value: function getEditCellHTML() {
      return '\n      <div class="edit-cell"></div>\n    ';
    }
  }, {
    key: 'cellSelector',
    value: function cellSelector(colIndex, rowIndex) {
      return '.data-table-col[data-col-index="' + colIndex + '"][data-row-index="' + rowIndex + '"]';
    }
  }]);

  return CellManager;
}();

exports.default = CellManager;
module.exports = exports['default'];

/***/ }),
/* 8 */
/***/ (function(module, exports) {

module.exports = __WEBPACK_EXTERNAL_MODULE_8__;

/***/ }),
/* 9 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _dom = __webpack_require__(0);

var _dom2 = _interopRequireDefault(_dom);

var _utils = __webpack_require__(1);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var RowManager = function () {
  function RowManager(instance) {
    _classCallCheck(this, RowManager);

    this.instance = instance;
    this.options = this.instance.options;
    this.wrapper = this.instance.wrapper;
    this.bodyScrollable = this.instance.bodyScrollable;

    this.bindEvents();
    this.refreshRows = (0, _utils.promisify)(this.refreshRows, this);
  }

  _createClass(RowManager, [{
    key: 'bindEvents',
    value: function bindEvents() {
      this.bindCheckbox();
    }
  }, {
    key: 'bindCheckbox',
    value: function bindCheckbox() {
      var _this = this;

      if (!this.options.addCheckboxColumn) return;

      // map of checked rows
      this.checkMap = [];

      _dom2.default.on(this.wrapper, 'click', '.data-table-col[data-col-index="0"] [type="checkbox"]', function (e, $checkbox) {
        var $cell = $checkbox.closest('.data-table-col');

        var _$$data = _dom2.default.data($cell),
            rowIndex = _$$data.rowIndex,
            isHeader = _$$data.isHeader;

        var checked = $checkbox.checked;

        if (isHeader) {
          _this.checkAll(checked);
        } else {
          _this.checkRow(rowIndex, checked);
        }
      });
    }
  }, {
    key: 'refreshRows',
    value: function refreshRows() {
      this.instance.renderBody();
      this.instance.setDimensions();
    }
  }, {
    key: 'refreshRow',
    value: function refreshRow(row, rowIndex) {
      var _this2 = this;

      var _row = this.datamanager.updateRow(row, rowIndex);

      _row.forEach(function (cell) {
        _this2.cellmanager.refreshCell(cell);
      });
    }
  }, {
    key: 'getCheckedRows',
    value: function getCheckedRows() {
      if (!this.checkMap) {
        return [];
      }

      return this.checkMap.map(function (c, rowIndex) {
        if (c) {
          return rowIndex;
        }
        return null;
      }).filter(function (c) {
        return c !== null || c !== undefined;
      });
    }
  }, {
    key: 'highlightCheckedRows',
    value: function highlightCheckedRows() {
      var _this3 = this;

      this.getCheckedRows().map(function (rowIndex) {
        return _this3.checkRow(rowIndex, true);
      });
    }
  }, {
    key: 'checkRow',
    value: function checkRow(rowIndex, toggle) {
      var value = toggle ? 1 : 0;

      // update internal map
      this.checkMap[rowIndex] = value;
      // set checkbox value explicitly
      _dom2.default.each('.data-table-col[data-row-index="' + rowIndex + '"][data-col-index="0"] [type="checkbox"]', this.bodyScrollable).map(function (input) {
        input.checked = toggle;
      });
      // highlight row
      this.highlightRow(rowIndex, toggle);
    }
  }, {
    key: 'checkAll',
    value: function checkAll(toggle) {
      var value = toggle ? 1 : 0;

      // update internal map
      if (toggle) {
        this.checkMap = Array.from(Array(this.getTotalRows())).map(function (c) {
          return value;
        });
      } else {
        this.checkMap = [];
      }
      // set checkbox value
      _dom2.default.each('.data-table-col[data-col-index="0"] [type="checkbox"]', this.bodyScrollable).map(function (input) {
        input.checked = toggle;
      });
      // highlight all
      this.highlightAll(toggle);
    }
  }, {
    key: 'highlightRow',
    value: function highlightRow(rowIndex) {
      var toggle = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : true;

      var $row = this.getRow$(rowIndex);
      if (!$row) return;

      if (!toggle && this.bodyScrollable.classList.contains('row-highlight-all')) {
        $row.classList.add('row-unhighlight');
        return;
      }

      if (toggle && $row.classList.contains('row-unhighlight')) {
        $row.classList.remove('row-unhighlight');
      }

      this._highlightedRows = this._highlightedRows || {};

      if (toggle) {
        $row.classList.add('row-highlight');
        this._highlightedRows[rowIndex] = $row;
      } else {
        $row.classList.remove('row-highlight');
        delete this._highlightedRows[rowIndex];
      }
    }
  }, {
    key: 'highlightAll',
    value: function highlightAll() {
      var toggle = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : true;

      if (toggle) {
        this.bodyScrollable.classList.add('row-highlight-all');
      } else {
        this.bodyScrollable.classList.remove('row-highlight-all');
        for (var rowIndex in this._highlightedRows) {
          var $row = this._highlightedRows[rowIndex];
          $row.classList.remove('row-highlight');
        }
        this._highlightedRows = {};
      }
    }
  }, {
    key: 'getRow$',
    value: function getRow$(rowIndex) {
      return (0, _dom2.default)('.data-table-row[data-row-index="' + rowIndex + '"]', this.bodyScrollable);
    }
  }, {
    key: 'getTotalRows',
    value: function getTotalRows() {
      return this.datamanager.getRowCount();
    }
  }, {
    key: 'getFirstRowIndex',
    value: function getFirstRowIndex() {
      return 0;
    }
  }, {
    key: 'getLastRowIndex',
    value: function getLastRowIndex() {
      return this.datamanager.getRowCount() - 1;
    }
  }, {
    key: 'scrollToRow',
    value: function scrollToRow(rowIndex) {
      rowIndex = +rowIndex;
      this._lastScrollTo = this._lastScrollTo || 0;
      var $row = this.getRow$(rowIndex);
      if (_dom2.default.inViewport($row, this.bodyScrollable)) return;

      var _$row$getBoundingClie = $row.getBoundingClientRect(),
          height = _$row$getBoundingClie.height;

      var _bodyScrollable$getBo = this.bodyScrollable.getBoundingClientRect(),
          top = _bodyScrollable$getBo.top,
          bottom = _bodyScrollable$getBo.bottom;

      var rowsInView = Math.floor((bottom - top) / height);

      var offset = 0;
      if (rowIndex > this._lastScrollTo) {
        offset = height * (rowIndex + 1 - rowsInView);
      } else {
        offset = height * (rowIndex + 1 - 1);
      }

      this._lastScrollTo = rowIndex;
      _dom2.default.scrollTop(this.bodyScrollable, offset);
    }
  }, {
    key: 'getRowHTML',
    value: function getRowHTML(row, props) {
      var _this4 = this;

      var dataAttr = (0, _utils.makeDataAttributeString)(props);

      return '\n      <tr class="data-table-row" ' + dataAttr + '>\n        ' + row.map(function (cell) {
        return _this4.cellmanager.getCellHTML(cell);
      }).join('') + '\n      </tr>\n    ';
    }
  }, {
    key: 'datamanager',
    get: function get() {
      return this.instance.datamanager;
    }
  }, {
    key: 'cellmanager',
    get: function get() {
      return this.instance.cellmanager;
    }
  }]);

  return RowManager;
}();

exports.default = RowManager;
module.exports = exports['default'];

/***/ }),
/* 10 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

exports.getBodyHTML = getBodyHTML;

var _dom = __webpack_require__(0);

var _dom2 = _interopRequireDefault(_dom);

var _clusterize = __webpack_require__(11);

var _clusterize2 = _interopRequireDefault(_clusterize);

var _utils = __webpack_require__(1);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var BodyRenderer = function () {
  function BodyRenderer(instance) {
    _classCallCheck(this, BodyRenderer);

    this.instance = instance;
    this.options = instance.options;
    this.datamanager = instance.datamanager;
    this.rowmanager = instance.rowmanager;
    this.cellmanager = instance.cellmanager;
    this.bodyScrollable = instance.bodyScrollable;
    this.log = instance.log;
    this.appendRemainingData = (0, _utils.promisify)(this.appendRemainingData, this);
  }

  _createClass(BodyRenderer, [{
    key: 'render',
    value: function render() {
      if (this.options.enableClusterize) {
        this.renderBodyWithClusterize();
      } else {
        this.renderBodyHTML();
      }
    }
  }, {
    key: 'renderBodyHTML',
    value: function renderBodyHTML() {
      var rows = this.datamanager.getRows();

      this.bodyScrollable.innerHTML = '\n      <table class="data-table-body">\n        ' + getBodyHTML(rows) + '\n      </table>\n    ';
      this.instance.setDimensions();
      this.restoreState();
    }
  }, {
    key: 'renderBodyWithClusterize',
    value: function renderBodyWithClusterize() {
      var _this = this;

      // first page
      var rows = this.datamanager.getRows(0, 20);
      var initialData = this.getDataForClusterize(rows);

      if (!this.clusterize) {
        // empty body
        this.bodyScrollable.innerHTML = '\n        <table class="data-table-body">\n          ' + getBodyHTML([]) + '\n        </table>\n      ';

        // first 20 rows will appended
        // rest of them in nextTick
        this.clusterize = new _clusterize2.default({
          rows: initialData,
          scrollElem: this.bodyScrollable,
          contentElem: (0, _dom2.default)('tbody', this.bodyScrollable),
          callbacks: {
            clusterChanged: function clusterChanged() {
              _this.restoreState();
            }
          },
          /* eslint-disable */
          no_data_text: this.options.loadingText,
          no_data_class: 'empty-state'
          /* eslint-enable */
        });

        // setDimensions requires atleast 1 row to exist in dom
        this.instance.setDimensions();
      } else {
        this.clusterize.update(initialData);
      }

      this.appendRemainingData();
    }
  }, {
    key: 'restoreState',
    value: function restoreState() {
      this.rowmanager.highlightCheckedRows();
      this.cellmanager.selectAreaOnClusterChanged();
      this.cellmanager.focusCellOnClusterChanged();
    }
  }, {
    key: 'appendRemainingData',
    value: function appendRemainingData() {
      var rows = this.datamanager.getRows(20);
      var data = this.getDataForClusterize(rows);
      this.clusterize.append(data);
    }
  }, {
    key: 'getDataForClusterize',
    value: function getDataForClusterize(rows) {
      var _this2 = this;

      return rows.map(function (row) {
        return _this2.rowmanager.getRowHTML(row, { rowIndex: row[0].rowIndex });
      });
    }
  }]);

  return BodyRenderer;
}();

exports.default = BodyRenderer;
;

function getBodyHTML(rows) {
  var _this3 = this;

  return '\n    <tbody>\n      ' + rows.map(function (row) {
    return _this3.rowmanager.getRowHTML(row, { rowIndex: row[0].rowIndex });
  }).join('') + '\n    </tbody>\n  ';
}

/***/ }),
/* 11 */
/***/ (function(module, exports) {

module.exports = __WEBPACK_EXTERNAL_MODULE_11__;

/***/ }),
/* 12 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _utils = __webpack_require__(1);

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var Style = function () {
  function Style(datatable) {
    _classCallCheck(this, Style);

    this.datatable = datatable;
    this.scopeClass = 'datatable-instance-' + datatable.constructor.instances;
    datatable.datatableWrapper.classList.add(this.scopeClass);

    var styleEl = document.createElement('style');
    datatable.wrapper.insertBefore(styleEl, datatable.datatableWrapper);
    this.styleEl = styleEl;
    this.styleSheet = styleEl.sheet;
  }

  _createClass(Style, [{
    key: 'destroy',
    value: function destroy() {
      this.styleEl.remove();
    }
  }, {
    key: 'setStyle',
    value: function setStyle(rule, styleMap) {
      var index = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : -1;

      var styles = Object.keys(styleMap).map(function (prop) {
        if (!prop.includes('-')) {
          prop = (0, _utils.camelCaseToDash)(prop);
        }
        return prop + ':' + styleMap[prop] + ';';
      }).join('');
      var ruleString = '.' + this.scopeClass + ' ' + rule + ' { ' + styles + ' }';

      var _index = this.styleSheet.cssRules.length;
      if (index !== -1) {
        this.styleSheet.deleteRule(index);
        _index = index;
      }

      this.styleSheet.insertRule(ruleString, _index);
      return _index;
    }
  }]);

  return Style;
}();

exports.default = Style;
module.exports = exports['default'];

/***/ }),
/* 13 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = {
  columns: [],
  data: [],
  dropdownButton: '▼',
  headerDropdown: [{
    label: 'Sort Ascending',
    action: function action(column) {
      this.sortColumn(column.colIndex, 'asc');
    }
  }, {
    label: 'Sort Descending',
    action: function action(column) {
      this.sortColumn(column.colIndex, 'desc');
    }
  }, {
    label: 'Reset sorting',
    action: function action(column) {
      this.sortColumn(column.colIndex, 'none');
    }
  }, {
    label: 'Remove column',
    action: function action(column) {
      this.removeColumn(column.colIndex);
    }
  }],
  events: {
    onRemoveColumn: function onRemoveColumn(column) {},
    onSwitchColumn: function onSwitchColumn(column1, column2) {},
    onSortColumn: function onSortColumn(column) {}
  },
  sortIndicator: {
    asc: '↑',
    desc: '↓',
    none: ''
  },
  freezeMessage: '',
  getEditor: function getEditor() {},
  addSerialNoColumn: true,
  addCheckboxColumn: false,
  enableClusterize: true,
  enableLogs: false,
  takeAvailableSpace: false,
  loadingText: ''
};
module.exports = exports['default'];

/***/ }),
/* 14 */
/***/ (function(module, exports, __webpack_require__) {

// style-loader: Adds some css to the DOM by adding a <style> tag

// load the styles
var content = __webpack_require__(15);
if(typeof content === 'string') content = [[module.i, content, '']];
// Prepare cssTransformation
var transform;

var options = {}
options.transform = transform
// add the styles to the DOM
var update = __webpack_require__(17)(content, options);
if(content.locals) module.exports = content.locals;
// Hot Module Replacement
if(false) {
	// When the styles change, update the <style> tags
	if(!content.locals) {
		module.hot.accept("!!../node_modules/css-loader/index.js!../node_modules/sass-loader/lib/loader.js!./style.scss", function() {
			var newContent = require("!!../node_modules/css-loader/index.js!../node_modules/sass-loader/lib/loader.js!./style.scss");
			if(typeof newContent === 'string') newContent = [[module.id, newContent, '']];
			update(newContent);
		});
	}
	// When the module is disposed, remove the <style> tags
	module.hot.dispose(function() { update(); });
}

/***/ }),
/* 15 */
/***/ (function(module, exports, __webpack_require__) {

exports = module.exports = __webpack_require__(16)(false);
// imports


// module
exports.push([module.i, "/* variables */\n.data-table {\n  /* resets */\n  /* styling */\n  width: 100%;\n  position: relative;\n  overflow: auto; }\n  .data-table *, .data-table *::after, .data-table *::before {\n    box-sizing: border-box; }\n  .data-table button, .data-table input {\n    overflow: visible;\n    font-family: inherit;\n    font-size: inherit;\n    line-height: inherit;\n    margin: 0;\n    padding: 0; }\n  .data-table *, .data-table *:focus {\n    outline: none;\n    border-radius: 0px;\n    box-shadow: none; }\n  .data-table table {\n    border-collapse: collapse; }\n  .data-table table td {\n    padding: 0;\n    border: 1px solid #d1d8dd; }\n  .data-table thead td {\n    border-bottom-width: 1px; }\n  .data-table .freeze-container {\n    display: flex;\n    justify-content: center;\n    align-content: center;\n    position: absolute;\n    left: 0;\n    right: 0;\n    top: 0;\n    bottom: 0;\n    background-color: #f5f7fa;\n    opacity: 0.5;\n    font-size: 2em; }\n    .data-table .freeze-container span {\n      position: absolute;\n      top: 50%;\n      transform: translateY(-50%); }\n  .data-table .trash-container {\n    position: absolute;\n    bottom: 0;\n    left: 30%;\n    right: 30%;\n    height: 70px;\n    background: palevioletred;\n    opacity: 0.5; }\n\n.body-scrollable {\n  max-height: 500px;\n  overflow: auto;\n  border-bottom: 1px solid #d1d8dd; }\n  .body-scrollable.row-highlight-all .data-table-row:not(.row-unhighlight) {\n    background-color: #f5f7fa; }\n\n.data-table-header {\n  position: absolute;\n  top: 0;\n  left: 0;\n  background-color: white;\n  font-weight: bold; }\n  .data-table-header .content span:not(.column-resizer) {\n    cursor: pointer; }\n  .data-table-header .column-resizer {\n    display: none;\n    position: absolute;\n    right: 0;\n    top: 0;\n    width: 0.25rem;\n    height: 100%;\n    background-color: #5292f7;\n    cursor: col-resize; }\n  .data-table-header .data-table-dropdown {\n    position: absolute;\n    right: 10px;\n    display: inline-flex;\n    vertical-align: top;\n    text-align: left; }\n    .data-table-header .data-table-dropdown.is-active .data-table-dropdown-list {\n      display: block; }\n    .data-table-header .data-table-dropdown.is-active .data-table-dropdown-toggle {\n      display: block; }\n  .data-table-header .data-table-dropdown-toggle {\n    display: none;\n    background-color: transparent;\n    border: none; }\n  .data-table-header .data-table-dropdown-list {\n    display: none;\n    font-weight: normal;\n    position: absolute;\n    min-width: 8rem;\n    top: 100%;\n    right: 0;\n    z-index: 1;\n    background-color: white;\n    border-radius: 3px;\n    box-shadow: 0 2px 3px rgba(10, 10, 10, 0.1), 0 0 0 1px rgba(10, 10, 10, 0.1);\n    padding-bottom: 0.5rem;\n    padding-top: 0.5rem; }\n    .data-table-header .data-table-dropdown-list > div {\n      padding: 0.5rem 1rem; }\n      .data-table-header .data-table-dropdown-list > div:hover {\n        background-color: #f5f7fa; }\n  .data-table-header .data-table-col.remove-column {\n    background-color: #FD8B8B;\n    transition: 300ms background-color ease-in-out; }\n  .data-table-header .data-table-col.sortable-chosen {\n    background-color: #f5f7fa; }\n\n.data-table-col {\n  position: relative; }\n  .data-table-col .content {\n    padding: 0.25rem;\n    border: 2px solid transparent; }\n    .data-table-col .content.ellipsis {\n      text-overflow: ellipsis;\n      white-space: nowrap;\n      overflow: hidden; }\n  .data-table-col .edit-cell {\n    display: none;\n    padding: 0.25rem;\n    background: #fff;\n    z-index: 1;\n    height: 100%; }\n    .data-table-col .edit-cell input {\n      outline: none;\n      width: 100%;\n      border: none; }\n  .data-table-col.selected .content {\n    border: 2px solid #5292f7; }\n  .data-table-col.editing .content {\n    display: none; }\n  .data-table-col.editing .edit-cell {\n    border: 2px solid #5292f7;\n    display: block; }\n  .data-table-col.highlight {\n    background-color: #f5f7fa; }\n  .data-table-col:hover .column-resizer {\n    display: inline-block; }\n  .data-table-col:hover .data-table-dropdown-toggle {\n    display: block; }\n\n.data-table-row.row-highlight {\n  background-color: #f5f7fa; }\n\n.noselect {\n  -webkit-touch-callout: none;\n  -webkit-user-select: none;\n  -khtml-user-select: none;\n  -moz-user-select: none;\n  -ms-user-select: none;\n  user-select: none; }\n\nbody.data-table-resize {\n  cursor: col-resize; }\n", ""]);

// exports


/***/ }),
/* 16 */
/***/ (function(module, exports) {

/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Tobias Koppers @sokra
*/
// css base code, injected by the css-loader
module.exports = function(useSourceMap) {
	var list = [];

	// return the list of modules as css string
	list.toString = function toString() {
		return this.map(function (item) {
			var content = cssWithMappingToString(item, useSourceMap);
			if(item[2]) {
				return "@media " + item[2] + "{" + content + "}";
			} else {
				return content;
			}
		}).join("");
	};

	// import a list of modules into the list
	list.i = function(modules, mediaQuery) {
		if(typeof modules === "string")
			modules = [[null, modules, ""]];
		var alreadyImportedModules = {};
		for(var i = 0; i < this.length; i++) {
			var id = this[i][0];
			if(typeof id === "number")
				alreadyImportedModules[id] = true;
		}
		for(i = 0; i < modules.length; i++) {
			var item = modules[i];
			// skip already imported module
			// this implementation is not 100% perfect for weird media query combinations
			//  when a module is imported multiple times with different media queries.
			//  I hope this will never occur (Hey this way we have smaller bundles)
			if(typeof item[0] !== "number" || !alreadyImportedModules[item[0]]) {
				if(mediaQuery && !item[2]) {
					item[2] = mediaQuery;
				} else if(mediaQuery) {
					item[2] = "(" + item[2] + ") and (" + mediaQuery + ")";
				}
				list.push(item);
			}
		}
	};
	return list;
};

function cssWithMappingToString(item, useSourceMap) {
	var content = item[1] || '';
	var cssMapping = item[3];
	if (!cssMapping) {
		return content;
	}

	if (useSourceMap && typeof btoa === 'function') {
		var sourceMapping = toComment(cssMapping);
		var sourceURLs = cssMapping.sources.map(function (source) {
			return '/*# sourceURL=' + cssMapping.sourceRoot + source + ' */'
		});

		return [content].concat(sourceURLs).concat([sourceMapping]).join('\n');
	}

	return [content].join('\n');
}

// Adapted from convert-source-map (MIT)
function toComment(sourceMap) {
	// eslint-disable-next-line no-undef
	var base64 = btoa(unescape(encodeURIComponent(JSON.stringify(sourceMap))));
	var data = 'sourceMappingURL=data:application/json;charset=utf-8;base64,' + base64;

	return '/*# ' + data + ' */';
}


/***/ }),
/* 17 */
/***/ (function(module, exports, __webpack_require__) {

/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Tobias Koppers @sokra
*/

var stylesInDom = {};

var	memoize = function (fn) {
	var memo;

	return function () {
		if (typeof memo === "undefined") memo = fn.apply(this, arguments);
		return memo;
	};
};

var isOldIE = memoize(function () {
	// Test for IE <= 9 as proposed by Browserhacks
	// @see http://browserhacks.com/#hack-e71d8692f65334173fee715c222cb805
	// Tests for existence of standard globals is to allow style-loader
	// to operate correctly into non-standard environments
	// @see https://github.com/webpack-contrib/style-loader/issues/177
	return window && document && document.all && !window.atob;
});

var getElement = (function (fn) {
	var memo = {};

	return function(selector) {
		if (typeof memo[selector] === "undefined") {
			memo[selector] = fn.call(this, selector);
		}

		return memo[selector]
	};
})(function (target) {
	return document.querySelector(target)
});

var singleton = null;
var	singletonCounter = 0;
var	stylesInsertedAtTop = [];

var	fixUrls = __webpack_require__(18);

module.exports = function(list, options) {
	if (typeof DEBUG !== "undefined" && DEBUG) {
		if (typeof document !== "object") throw new Error("The style-loader cannot be used in a non-browser environment");
	}

	options = options || {};

	options.attrs = typeof options.attrs === "object" ? options.attrs : {};

	// Force single-tag solution on IE6-9, which has a hard limit on the # of <style>
	// tags it will allow on a page
	if (!options.singleton) options.singleton = isOldIE();

	// By default, add <style> tags to the <head> element
	if (!options.insertInto) options.insertInto = "head";

	// By default, add <style> tags to the bottom of the target
	if (!options.insertAt) options.insertAt = "bottom";

	var styles = listToStyles(list, options);

	addStylesToDom(styles, options);

	return function update (newList) {
		var mayRemove = [];

		for (var i = 0; i < styles.length; i++) {
			var item = styles[i];
			var domStyle = stylesInDom[item.id];

			domStyle.refs--;
			mayRemove.push(domStyle);
		}

		if(newList) {
			var newStyles = listToStyles(newList, options);
			addStylesToDom(newStyles, options);
		}

		for (var i = 0; i < mayRemove.length; i++) {
			var domStyle = mayRemove[i];

			if(domStyle.refs === 0) {
				for (var j = 0; j < domStyle.parts.length; j++) domStyle.parts[j]();

				delete stylesInDom[domStyle.id];
			}
		}
	};
};

function addStylesToDom (styles, options) {
	for (var i = 0; i < styles.length; i++) {
		var item = styles[i];
		var domStyle = stylesInDom[item.id];

		if(domStyle) {
			domStyle.refs++;

			for(var j = 0; j < domStyle.parts.length; j++) {
				domStyle.parts[j](item.parts[j]);
			}

			for(; j < item.parts.length; j++) {
				domStyle.parts.push(addStyle(item.parts[j], options));
			}
		} else {
			var parts = [];

			for(var j = 0; j < item.parts.length; j++) {
				parts.push(addStyle(item.parts[j], options));
			}

			stylesInDom[item.id] = {id: item.id, refs: 1, parts: parts};
		}
	}
}

function listToStyles (list, options) {
	var styles = [];
	var newStyles = {};

	for (var i = 0; i < list.length; i++) {
		var item = list[i];
		var id = options.base ? item[0] + options.base : item[0];
		var css = item[1];
		var media = item[2];
		var sourceMap = item[3];
		var part = {css: css, media: media, sourceMap: sourceMap};

		if(!newStyles[id]) styles.push(newStyles[id] = {id: id, parts: [part]});
		else newStyles[id].parts.push(part);
	}

	return styles;
}

function insertStyleElement (options, style) {
	var target = getElement(options.insertInto)

	if (!target) {
		throw new Error("Couldn't find a style target. This probably means that the value for the 'insertInto' parameter is invalid.");
	}

	var lastStyleElementInsertedAtTop = stylesInsertedAtTop[stylesInsertedAtTop.length - 1];

	if (options.insertAt === "top") {
		if (!lastStyleElementInsertedAtTop) {
			target.insertBefore(style, target.firstChild);
		} else if (lastStyleElementInsertedAtTop.nextSibling) {
			target.insertBefore(style, lastStyleElementInsertedAtTop.nextSibling);
		} else {
			target.appendChild(style);
		}
		stylesInsertedAtTop.push(style);
	} else if (options.insertAt === "bottom") {
		target.appendChild(style);
	} else {
		throw new Error("Invalid value for parameter 'insertAt'. Must be 'top' or 'bottom'.");
	}
}

function removeStyleElement (style) {
	if (style.parentNode === null) return false;
	style.parentNode.removeChild(style);

	var idx = stylesInsertedAtTop.indexOf(style);
	if(idx >= 0) {
		stylesInsertedAtTop.splice(idx, 1);
	}
}

function createStyleElement (options) {
	var style = document.createElement("style");

	options.attrs.type = "text/css";

	addAttrs(style, options.attrs);
	insertStyleElement(options, style);

	return style;
}

function createLinkElement (options) {
	var link = document.createElement("link");

	options.attrs.type = "text/css";
	options.attrs.rel = "stylesheet";

	addAttrs(link, options.attrs);
	insertStyleElement(options, link);

	return link;
}

function addAttrs (el, attrs) {
	Object.keys(attrs).forEach(function (key) {
		el.setAttribute(key, attrs[key]);
	});
}

function addStyle (obj, options) {
	var style, update, remove, result;

	// If a transform function was defined, run it on the css
	if (options.transform && obj.css) {
	    result = options.transform(obj.css);

	    if (result) {
	    	// If transform returns a value, use that instead of the original css.
	    	// This allows running runtime transformations on the css.
	    	obj.css = result;
	    } else {
	    	// If the transform function returns a falsy value, don't add this css.
	    	// This allows conditional loading of css
	    	return function() {
	    		// noop
	    	};
	    }
	}

	if (options.singleton) {
		var styleIndex = singletonCounter++;

		style = singleton || (singleton = createStyleElement(options));

		update = applyToSingletonTag.bind(null, style, styleIndex, false);
		remove = applyToSingletonTag.bind(null, style, styleIndex, true);

	} else if (
		obj.sourceMap &&
		typeof URL === "function" &&
		typeof URL.createObjectURL === "function" &&
		typeof URL.revokeObjectURL === "function" &&
		typeof Blob === "function" &&
		typeof btoa === "function"
	) {
		style = createLinkElement(options);
		update = updateLink.bind(null, style, options);
		remove = function () {
			removeStyleElement(style);

			if(style.href) URL.revokeObjectURL(style.href);
		};
	} else {
		style = createStyleElement(options);
		update = applyToTag.bind(null, style);
		remove = function () {
			removeStyleElement(style);
		};
	}

	update(obj);

	return function updateStyle (newObj) {
		if (newObj) {
			if (
				newObj.css === obj.css &&
				newObj.media === obj.media &&
				newObj.sourceMap === obj.sourceMap
			) {
				return;
			}

			update(obj = newObj);
		} else {
			remove();
		}
	};
}

var replaceText = (function () {
	var textStore = [];

	return function (index, replacement) {
		textStore[index] = replacement;

		return textStore.filter(Boolean).join('\n');
	};
})();

function applyToSingletonTag (style, index, remove, obj) {
	var css = remove ? "" : obj.css;

	if (style.styleSheet) {
		style.styleSheet.cssText = replaceText(index, css);
	} else {
		var cssNode = document.createTextNode(css);
		var childNodes = style.childNodes;

		if (childNodes[index]) style.removeChild(childNodes[index]);

		if (childNodes.length) {
			style.insertBefore(cssNode, childNodes[index]);
		} else {
			style.appendChild(cssNode);
		}
	}
}

function applyToTag (style, obj) {
	var css = obj.css;
	var media = obj.media;

	if(media) {
		style.setAttribute("media", media)
	}

	if(style.styleSheet) {
		style.styleSheet.cssText = css;
	} else {
		while(style.firstChild) {
			style.removeChild(style.firstChild);
		}

		style.appendChild(document.createTextNode(css));
	}
}

function updateLink (link, options, obj) {
	var css = obj.css;
	var sourceMap = obj.sourceMap;

	/*
		If convertToAbsoluteUrls isn't defined, but sourcemaps are enabled
		and there is no publicPath defined then lets turn convertToAbsoluteUrls
		on by default.  Otherwise default to the convertToAbsoluteUrls option
		directly
	*/
	var autoFixUrls = options.convertToAbsoluteUrls === undefined && sourceMap;

	if (options.convertToAbsoluteUrls || autoFixUrls) {
		css = fixUrls(css);
	}

	if (sourceMap) {
		// http://stackoverflow.com/a/26603875
		css += "\n/*# sourceMappingURL=data:application/json;base64," + btoa(unescape(encodeURIComponent(JSON.stringify(sourceMap)))) + " */";
	}

	var blob = new Blob([css], { type: "text/css" });

	var oldSrc = link.href;

	link.href = URL.createObjectURL(blob);

	if(oldSrc) URL.revokeObjectURL(oldSrc);
}


/***/ }),
/* 18 */
/***/ (function(module, exports) {


/**
 * When source maps are enabled, `style-loader` uses a link element with a data-uri to
 * embed the css on the page. This breaks all relative urls because now they are relative to a
 * bundle instead of the current page.
 *
 * One solution is to only use full urls, but that may be impossible.
 *
 * Instead, this function "fixes" the relative urls to be absolute according to the current page location.
 *
 * A rudimentary test suite is located at `test/fixUrls.js` and can be run via the `npm test` command.
 *
 */

module.exports = function (css) {
  // get current location
  var location = typeof window !== "undefined" && window.location;

  if (!location) {
    throw new Error("fixUrls requires window.location");
  }

	// blank or null?
	if (!css || typeof css !== "string") {
	  return css;
  }

  var baseUrl = location.protocol + "//" + location.host;
  var currentDir = baseUrl + location.pathname.replace(/\/[^\/]*$/, "/");

	// convert each url(...)
	/*
	This regular expression is just a way to recursively match brackets within
	a string.

	 /url\s*\(  = Match on the word "url" with any whitespace after it and then a parens
	   (  = Start a capturing group
	     (?:  = Start a non-capturing group
	         [^)(]  = Match anything that isn't a parentheses
	         |  = OR
	         \(  = Match a start parentheses
	             (?:  = Start another non-capturing groups
	                 [^)(]+  = Match anything that isn't a parentheses
	                 |  = OR
	                 \(  = Match a start parentheses
	                     [^)(]*  = Match anything that isn't a parentheses
	                 \)  = Match a end parentheses
	             )  = End Group
              *\) = Match anything and then a close parens
          )  = Close non-capturing group
          *  = Match anything
       )  = Close capturing group
	 \)  = Match a close parens

	 /gi  = Get all matches, not the first.  Be case insensitive.
	 */
	var fixedCss = css.replace(/url\s*\(((?:[^)(]|\((?:[^)(]+|\([^)(]*\))*\))*)\)/gi, function(fullMatch, origUrl) {
		// strip quotes (if they exist)
		var unquotedOrigUrl = origUrl
			.trim()
			.replace(/^"(.*)"$/, function(o, $1){ return $1; })
			.replace(/^'(.*)'$/, function(o, $1){ return $1; });

		// already a full url? no change
		if (/^(#|data:|http:\/\/|https:\/\/|file:\/\/\/)/i.test(unquotedOrigUrl)) {
		  return fullMatch;
		}

		// convert the url to a full url
		var newUrl;

		if (unquotedOrigUrl.indexOf("//") === 0) {
		  	//TODO: should we add protocol?
			newUrl = unquotedOrigUrl;
		} else if (unquotedOrigUrl.indexOf("/") === 0) {
			// path should be relative to the base url
			newUrl = baseUrl + unquotedOrigUrl; // already starts with '/'
		} else {
			// path should be relative to current directory
			newUrl = currentDir + unquotedOrigUrl.replace(/^\.\//, ""); // Strip leading './'
		}

		// send back the fixed url(...)
		return "url(" + JSON.stringify(newUrl) + ")";
	});

	// send back the fixed css
	return fixedCss;
};


/***/ }),
/* 19 */
/***/ (function(module, exports) {

module.exports = {"name":"frappe-datatable","version":"0.0.1","description":"A modern datatable library for the web","main":"lib/frappe-datatable.js","scripts":{"start":"npm run dev","build":"webpack --env build","dev":"webpack --progress --colors --watch --env dev","test":"mocha --compilers js:babel-core/register --colors ./test/*.spec.js","test:watch":"mocha --compilers js:babel-core/register --colors -w ./test/*.spec.js"},"devDependencies":{"babel-cli":"6.24.1","babel-core":"6.24.1","babel-eslint":"7.2.3","babel-loader":"7.0.0","babel-plugin-add-module-exports":"0.2.1","babel-plugin-transform-builtin-extend":"^1.1.2","babel-preset-env":"^1.6.1","chai":"3.5.0","css-loader":"^0.28.7","eslint":"3.19.0","eslint-loader":"1.7.1","mocha":"3.3.0","node-sass":"^4.5.3","sass-loader":"^6.0.6","style-loader":"^0.18.2","webpack":"^3.1.0","yargs":"7.1.0"},"repository":{"type":"git","url":"https://github.com/frappe/datatable.git"},"keywords":["webpack","es6","starter","library","universal","umd","commonjs"],"author":"Faris Ansari","license":"MIT","bugs":{"url":"https://github.com/frappe/datatable/issues"},"homepage":"https://frappe.github.io/datatable","dependencies":{"clusterize.js":"^0.18.0","sortablejs":"^1.7.0"}}

/***/ })
/******/ ]);
});
//# sourceMappingURL=frappe-datatable.js.map