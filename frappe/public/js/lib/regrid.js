(function webpackUniversalModuleDefinition(root, factory) {
	if(typeof exports === 'object' && typeof module === 'object')
		module.exports = factory();
	else if(typeof define === 'function' && define.amd)
		define("ReGrid", [], factory);
	else if(typeof exports === 'object')
		exports["ReGrid"] = factory();
	else
		root["ReGrid"] = factory();
})(this, function() {
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
/******/ 	return __webpack_require__(__webpack_require__.s = 0);
/******/ })
/************************************************************************/
/******/ ([
/* 0 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _regrid = __webpack_require__(1);

var _regrid2 = _interopRequireDefault(_regrid);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

exports.default = _regrid2.default;
module.exports = exports['default'];

/***/ }),
/* 1 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }(); /* globals $, Clusterize */

// import $ from 'jQuery';
// import Clusterize from 'clusterize.js';

var _utils = __webpack_require__(2);

__webpack_require__(3);

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var ReGrid = function () {
  function ReGrid(_ref) {
    var wrapper = _ref.wrapper,
        events = _ref.events,
        data = _ref.data,
        editing = _ref.editing,
        addSerialNoColumn = _ref.addSerialNoColumn,
        enableClusterize = _ref.enableClusterize,
        enableLogs = _ref.enableLogs;

    _classCallCheck(this, ReGrid);

    this.wrapper = $(wrapper);
    if (this.wrapper.length === 0) {
      throw new Error('Invalid argument given for `wrapper`');
    }

    this.events = (0, _utils.getDefault)(events, {});
    this.addSerialNoColumn = (0, _utils.getDefault)(addSerialNoColumn, false);
    this.enableClusterize = (0, _utils.getDefault)(enableClusterize, false);
    this.enableLogs = (0, _utils.getDefault)(enableLogs, true);
    this.editing = (0, _utils.getDefault)(editing, null);

    if (data) {
      this.refresh(data);
    }
  }

  _createClass(ReGrid, [{
    key: 'makeDom',
    value: function makeDom() {
      this.wrapper.html('\n      <div class="data-table">\n        <table class="data-table-header table table-bordered">\n        </table>\n        <div class="body-scrollable">\n        </div>\n        <div class="data-table-footer">\n        </div>\n        <div class="data-table-popup">\n          <div class="edit-popup"></div>\n        </div>\n      </div>\n    ');

      this.header = this.wrapper.find('.data-table-header');
      this.bodyScrollable = this.wrapper.find('.body-scrollable');
      // this.body = this.wrapper.find('.data-table-body');
      this.footer = this.wrapper.find('.data-table-footer');
    }
  }, {
    key: 'refresh',
    value: function refresh(data) {
      this.data = this.prepareData(data);
      this.render();
    }
  }, {
    key: 'render',
    value: function render() {
      if (this.wrapper.find('.data-table').length === 0) {
        this.makeDom();
        this.makeStyle();
        this.bindEvents();
      }

      this.renderHeader();
      this.renderBody();
      this.setDimensions();
    }
  }, {
    key: 'renderHeader',
    value: function renderHeader() {
      // fixed header
      this.header.html((0, _utils.getHeaderHTML)(this.data.columns));
    }
  }, {
    key: 'renderBody',
    value: function renderBody() {
      if (this.enableClusterize) {
        this.renderBodyWithClusterize();
      } else {
        this.renderBodyHTML();
      }
    }
  }, {
    key: 'renderBodyHTML',
    value: function renderBodyHTML() {
      // scrollable body
      this.bodyScrollable.html('\n      <table class="data-table-body table table-bordered">\n        ' + (0, _utils.getBodyHTML)(this.data.rows) + '\n      </table>\n    ');
    }
  }, {
    key: 'renderBodyWithClusterize',
    value: function renderBodyWithClusterize() {
      // empty body
      this.bodyScrollable.html('\n      <table class="data-table-body table table-bordered">\n        ' + (0, _utils.getBodyHTML)([]) + '\n      </table>\n    ');

      this.start = 0;
      this.pageLength = 1000;
      this.end = this.start + this.pageLength;

      var initialData = this.getDataForClusterize(
      // only append ${this.pageLength} rows in the beginning
      // defer remaining rows
      this.data.rows.slice(this.start, this.end));

      this.clusterize = new Clusterize({
        rows: initialData,
        scrollElem: this.bodyScrollable.get(0),
        contentElem: this.bodyScrollable.find('tbody').get(0)
      });
      this.log('dataAppended', this.pageLength);
      this.appendRemainingData();
    }
  }, {
    key: 'appendRemainingData',
    value: function appendRemainingData() {
      var dataAppended = this.pageLength;
      var promises = [];

      while (dataAppended + this.pageLength < this.data.rows.length) {
        this.start = this.end;
        this.end = this.start + this.pageLength;
        promises.push(this.appendNextPagePromise(this.start, this.end));
        dataAppended += this.pageLength;
      }

      if (this.data.rows.length % this.pageLength > 0) {
        // last page
        this.start = this.end;
        this.end = this.start + this.pageLength;
        promises.push(this.appendNextPagePromise(this.start, this.end));
      }

      return promises.reduce(function (prev, cur) {
        return prev.then(cur);
      }, Promise.resolve());
    }
  }, {
    key: 'appendNextPagePromise',
    value: function appendNextPagePromise(start, end) {
      var _this = this;

      return new Promise(function (resolve) {
        setTimeout(function () {
          var rows = _this.data.rows.slice(start, end);
          var data = _this.getDataForClusterize(rows);

          _this.clusterize.append(data);
          _this.log('dataAppended', rows.length);
          resolve();
        }, 0);
      });
    }
  }, {
    key: 'getDataForClusterize',
    value: function getDataForClusterize(rows) {
      return rows.map(function (row) {
        return (0, _utils.getRowHTML)(row, { rowIndex: row[0].rowIndex });
      });
    }
  }, {
    key: 'updateCell',
    value: function updateCell(rowIndex, colIndex, value) {
      var cell = this.getCell(rowIndex, colIndex);

      cell.content = value;
      this.refreshCell(cell);
    }
  }, {
    key: 'refreshRows',
    value: function refreshRows() {
      this.renderBody();
      this.setDimensions();
    }
  }, {
    key: 'refreshCell',
    value: function refreshCell(cell) {
      var selector = '.data-table-col[data-row-index="' + cell.rowIndex + '"][data-col-index="' + cell.colIndex + '"]';
      var $cell = this.bodyScrollable.find(selector);
      var $newCell = $((0, _utils.getColumnHTML)(cell));

      $cell.replaceWith($newCell);
    }
  }, {
    key: 'prepareData',
    value: function prepareData(data) {
      // cache original data passed
      this._data = data;
      var columns = data.columns,
          rows = data.rows;


      if (this.addSerialNoColumn) {
        var serialNoColumn = {
          content: 'Sr. No',
          resizable: false
        };

        columns = [serialNoColumn].concat(columns);

        rows = rows.map(function (row, i) {
          var val = i + 1 + '';

          return [val].concat(row);
        });
      }

      var _columns = (0, _utils.prepareRowHeader)(columns);
      var _rows = (0, _utils.prepareRows)(rows);

      return {
        columns: _columns,
        rows: _rows
      };
    }
  }, {
    key: 'bindEvents',
    value: function bindEvents() {
      this.bindFocusCell();
      this.bindEditCell();
      this.bindResizeColumn();
      this.bindSortColumn();
    }
  }, {
    key: 'setDimensions',
    value: function setDimensions() {
      var self = this;

      // setting width as 0 will ensure that the
      // header doesn't take the available space
      this.header.css({
        width: 0,
        margin: 0
      });

      // cache minWidth for each column
      this.minWidthMap = (0, _utils.getDefault)(this.minWidthMap, []);
      this.header.find('.data-table-col').each(function () {
        var col = $(this);
        var width = parseInt(col.find('.content').css('width'), 10);
        var colIndex = col.attr('data-col-index');

        if (!self.minWidthMap[colIndex]) {
          // only set this once
          self.minWidthMap[colIndex] = width;
        }
      });

      // set initial width as naturally calculated by table's first row
      this.bodyScrollable.find('.data-table-row[data-row-index="0"] .data-table-col').each(function () {
        var $cell = $(this);
        var width = parseInt($cell.find('.content').css('width'), 10);
        var height = parseInt($cell.find('.content').css('height'), 10);

        var _self$getCellAttr = self.getCellAttr($cell),
            colIndex = _self$getCellAttr.colIndex;

        self.setColumnWidth(colIndex, width);
        self.setDefaultCellHeight(height);
      });

      this.setBodyWidth();

      this.setStyle('.data-table .body-scrollable', {
        'margin-top': this.header.height() + 1 + 'px'
      });

      // hide edit cells by default
      this.setStyle('.data-table .body-scrollable .edit-cell', {
        display: 'none'
      });

      this.bodyScrollable.find('.table').css('margin', 0);
    }
  }, {
    key: 'bindFocusCell',
    value: function bindFocusCell() {
      var self = this;

      this.$focusedCell = null;
      this.bodyScrollable.on('click', '.data-table-col', function () {
        var $cell = $(this);

        self.$focusedCell = $cell;
        self.bodyScrollable.find('.data-table-col').removeClass('selected');
        $cell.addClass('selected');
      });
    }
  }, {
    key: 'bindEditCell',
    value: function bindEditCell() {
      var _this2 = this;

      var self = this;

      this.$editingCell = null;
      this.bodyScrollable.on('dblclick', '.data-table-col', function () {
        self.activateEditing($(this));
      });

      $(document.body).on('keypress', function (e) {
        // enter keypress on focused cell
        if (e.which === 13 && _this2.$focusedCell && !_this2.$editingCell) {
          _this2.log('editingCell');
          _this2.activateEditing(_this2.$focusedCell);
          e.stopImmediatePropagation();
        }
      });

      $(document.body).on('keypress', function (e) {
        // enter keypress on editing cell
        if (e.which === 13 && _this2.$editingCell) {
          _this2.log('submitCell');
          _this2.submitEditing(_this2.$editingCell);
          e.stopImmediatePropagation();
        }
      });

      $(document.body).on('click', function (e) {
        if ($(e.target).is('.edit-cell, .edit-cell *')) return;
        self.bodyScrollable.find('.edit-cell').hide();
        _this2.$editingCell = null;
      });
    }
  }, {
    key: 'activateEditing',
    value: function activateEditing($cell) {
      var _getCellAttr = this.getCellAttr($cell),
          rowIndex = _getCellAttr.rowIndex,
          colIndex = _getCellAttr.colIndex;

      if (this.$editingCell) {
        var _getCellAttr2 = this.getCellAttr(this.$editingCell),
            _rowIndex = _getCellAttr2._rowIndex,
            _colIndex = _getCellAttr2._colIndex;

        if (rowIndex === _rowIndex && colIndex === _colIndex) {
          // editing the same cell
          return;
        }
      }

      this.$editingCell = $cell;
      var $editCell = $cell.find('.edit-cell').empty();
      var cell = this.getCell(rowIndex, colIndex);
      var editing = this.getEditingObject(colIndex, rowIndex, cell.content, $editCell);

      if (editing) {
        this.currentCellEditing = editing;
        // initialize editing input with cell value
        editing.initValue(cell.content);
        $editCell.show();
      }
    }
  }, {
    key: 'getEditingObject',
    value: function getEditingObject(colIndex, rowIndex, value, parent) {
      if (this.editing) {
        return this.editing(colIndex, rowIndex, value, parent);
      }

      // editing fallback
      var $input = $('<input type="text" />');

      parent.append($input);

      return {
        initValue: function initValue(value) {
          return $input.val(value);
        },
        getValue: function getValue() {
          return $input.val();
        },
        setValue: function setValue(value) {
          return $input.val(value);
        }
      };
    }
  }, {
    key: 'submitEditing',
    value: function submitEditing($cell) {
      var _this3 = this;

      var _getCellAttr3 = this.getCellAttr($cell),
          rowIndex = _getCellAttr3.rowIndex,
          colIndex = _getCellAttr3.colIndex;

      if ($cell) {
        var editing = this.currentCellEditing;

        if (editing) {
          var value = editing.getValue();
          var done = editing.setValue(value);

          if (done && done.then) {
            // wait for promise then update internal state
            done.then(function () {
              return _this3.updateCell(rowIndex, colIndex, value);
            });
          } else {
            this.updateCell(rowIndex, colIndex, value);
          }
        }
      }

      this.currentCellEditing = null;
    }
  }, {
    key: 'bindResizeColumn',
    value: function bindResizeColumn() {
      var self = this;
      var isDragging = false;
      var $currCell = void 0,
          startWidth = void 0,
          startX = void 0;

      this.header.on('mousedown', '.data-table-col', function (e) {
        $currCell = $(this);
        var colIndex = $currCell.attr('data-col-index');
        var col = self.getColumn(colIndex);

        if (col && col.resizable === false) {
          return;
        }

        isDragging = true;
        startWidth = $currCell.find('.content').width();
        startX = e.pageX;
      });

      $('body').on('mouseup', function (e) {
        if (!$currCell) return;
        isDragging = false;
        var colIndex = $currCell.attr('data-col-index');

        if ($currCell) {
          var width = parseInt($currCell.find('.content').css('width'), 10);

          self.setColumnWidth(colIndex, width);
          self.setBodyWidth();
          $currCell = null;
        }
      });

      $('body').on('mousemove', function (e) {
        if (!isDragging) return;
        var finalWidth = startWidth + (e.pageX - startX);
        var colIndex = $currCell.attr('data-col-index');

        if (self.getColumnMinWidth(colIndex) > finalWidth) {
          // don't resize past minWidth
          return;
        }

        self.setColumnHeaderWidth(colIndex, finalWidth);
      });
    }
  }, {
    key: 'bindSortColumn',
    value: function bindSortColumn() {
      var self = this;

      this.header.on('click', '.data-table-col .content span', function () {
        var $cell = $(this).closest('.data-table-col');
        var sortAction = (0, _utils.getDefault)($cell.attr('data-sort-action'), 'none');
        var colIndex = $cell.attr('data-col-index');

        // reset sort indicator
        self.header.find('.sort-indicator').text('');
        self.header.find('.data-table-col').attr('data-sort-action', 'none');

        if (sortAction === 'none') {
          $cell.attr('data-sort-action', 'asc');
          $cell.find('.sort-indicator').text('▲');
        } else if (sortAction === 'asc') {
          $cell.attr('data-sort-action', 'desc');
          $cell.find('.sort-indicator').text('▼');
        } else if (sortAction === 'desc') {
          $cell.attr('data-sort-action', 'none');
          $cell.find('.sort-indicator').text('');
        }

        // sortWith this action
        var sortWith = $cell.attr('data-sort-action');

        if (self.events.onSort) {
          self.events.onSort(colIndex, sortWith);
        } else {
          self.sortRows(colIndex, sortWith);
          self.refreshRows();
        }
      });
    }
  }, {
    key: 'sortRows',
    value: function sortRows(colIndex) {
      var sortAction = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 'none';

      colIndex = +colIndex;

      this.data.rows.sort(function (a, b) {
        var _aIndex = a[0].rowIndex;
        var _bIndex = b[0].rowIndex;
        var _a = a[colIndex].content;
        var _b = b[colIndex].content;

        if (sortAction === 'none') {
          return _aIndex - _bIndex;
        } else if (sortAction === 'asc') {
          if (_a < _b) return -1;
          if (_a > _b) return 1;
          if (_a === _b) return 0;
        } else if (sortAction === 'desc') {
          if (_a < _b) return 1;
          if (_a > _b) return -1;
          if (_a === _b) return 0;
        }
        return 0;
      });
    }
  }, {
    key: 'setColumnWidth',
    value: function setColumnWidth(colIndex, width) {
      // set width for content
      this.setStyle('[data-col-index="' + colIndex + '"] .content', {
        width: width + 'px'
      });
      // set width for edit cell
      this.setStyle('[data-col-index="' + colIndex + '"] .edit-cell', {
        width: width + 'px'
      });
    }
  }, {
    key: 'setColumnHeaderWidth',
    value: function setColumnHeaderWidth(colIndex, width) {
      this.setStyle('[data-col-index="' + colIndex + '"][data-is-header] .content', {
        width: width + 'px'
      });
    }
  }, {
    key: 'setDefaultCellHeight',
    value: function setDefaultCellHeight(height) {
      this.setStyle('.data-table-col .content', {
        height: height + 'px'
      });
    }
  }, {
    key: 'setRowHeight',
    value: function setRowHeight(rowIndex, height) {
      this.setStyle('[data-row-index="' + rowIndex + '"] .content', {
        height: height + 'px'
      });
    }
  }, {
    key: 'setColumnWidths',
    value: function setColumnWidths() {
      var _this4 = this;

      var availableWidth = this.wrapper.width();
      var headerWidth = this.header.width();

      if (headerWidth > availableWidth) {
        // don't resize, horizontal scroll takes place
        return;
      }

      var deltaWidth = (availableWidth - headerWidth) / this.data.columns.length;

      this.data.columns.map(function (col) {
        var width = _this4.getColumnHeaderElement(col.colIndex).width();
        var finalWidth = width + deltaWidth - 16;

        if (_this4.addSerialNoColumn && col.colIndex === 0) {
          return;
        }

        _this4.setColumnHeaderWidth(col.colIndex, finalWidth);
        _this4.setColumnWidth(col.colIndex, finalWidth);
      });
      this.setBodyWidth();
    }
  }, {
    key: 'setBodyWidth',
    value: function setBodyWidth() {
      this.bodyScrollable.css('width', parseInt(this.header.css('width'), 10) + 1);
    }
  }, {
    key: 'setStyle',
    value: function setStyle(rule, styleMap) {
      var styles = this.$style.text();

      styles = (0, _utils.buildCSSRule)(rule, styleMap, styles);
      this.$style.html(styles);
    }
  }, {
    key: 'makeStyle',
    value: function makeStyle() {
      this.$style = $('<style data-id="regrid"></style>').prependTo(this.wrapper);
    }
  }, {
    key: 'getColumn',
    value: function getColumn(colIndex) {
      colIndex = +colIndex;
      return this.data.columns.find(function (col) {
        return col.colIndex === colIndex;
      });
    }
  }, {
    key: 'getRow',
    value: function getRow(rowIndex) {
      rowIndex = +rowIndex;
      return this.data.rows.find(function (row) {
        return row[0].rowIndex === rowIndex;
      });
    }
  }, {
    key: 'getCell',
    value: function getCell(rowIndex, colIndex) {
      rowIndex = +rowIndex;
      colIndex = +colIndex;
      return this.data.rows.find(function (row) {
        return row[0].rowIndex === rowIndex;
      })[colIndex];
    }
  }, {
    key: 'getColumnHeaderElement',
    value: function getColumnHeaderElement(colIndex) {
      colIndex = +colIndex;
      if (colIndex < 0) return null;
      return this.wrapper.find('.data-table-col[data-is-header][data-col-index="' + colIndex + '"]');
    }
  }, {
    key: 'getColumnMinWidth',
    value: function getColumnMinWidth(colIndex) {
      colIndex = +colIndex;
      return this.minWidthMap && this.minWidthMap[colIndex];
    }
  }, {
    key: 'getCellAttr',
    value: function getCellAttr($cell) {
      return $cell.data();
    }
  }, {
    key: 'log',
    value: function log() {
      if (this.enableLogs) {
        console.log.apply(console, arguments);
      }
    }
  }]);

  return ReGrid;
}();

exports.default = ReGrid;
module.exports = exports['default'];

/***/ }),
/* 2 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});
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

function getEditCellHTML() {
  return '\n    <div class="edit-cell"></div>\n  ';
}

function getColumnHTML(column) {
  var rowIndex = column.rowIndex,
      colIndex = column.colIndex,
      isHeader = column.isHeader;

  var dataAttr = makeDataAttributeString({
    rowIndex: rowIndex,
    colIndex: colIndex,
    isHeader: isHeader
  });

  var editCellHTML = isHeader ? '' : getEditCellHTML();

  return '\n    <td class="data-table-col noselect" ' + dataAttr + '>\n      <div class="content ellipsis">\n        ' + (column.format ? column.format(column.content) : column.content) + '\n        <span class="sort-indicator"></span>\n      </div>\n      ' + editCellHTML + '\n    </td>\n  ';
}

function getRowHTML(columns, props) {
  var dataAttr = makeDataAttributeString(props);

  return '\n    <tr class="data-table-row" ' + dataAttr + '>\n      ' + columns.map(getColumnHTML).join('') + '\n    </tr>\n  ';
}

function getHeaderHTML(columns) {
  var $header = '\n    <thead>\n      ' + getRowHTML(columns, { isHeader: 1, rowIndex: -1 }) + '\n    </thead>\n  ';

  // columns.map(col => {
  //   if (!col.width) return;
  //   const $cellContent = $header.find(
  //     `.data-table-col[data-col-index="${col.colIndex}"] .content`
  //   );

  //   $cellContent.width(col.width);
  // });

  return $header;
}

function getBodyHTML(rows) {
  return '\n    <tbody>\n      ' + rows.map(function (row) {
    return getRowHTML(row, { rowIndex: row[0].rowIndex });
  }).join('') + '\n    </tbody>\n  ';
}

function prepareColumn(col, i) {
  if (typeof col === 'string') {
    col = {
      content: col
    };
  }
  return Object.assign(col, {
    colIndex: i
  });
}

function prepareColumns(columns) {
  var props = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};

  var _columns = columns.map(prepareColumn);

  return _columns.map(function (col) {
    return Object.assign(col, props);
  });
}

function prepareRowHeader(columns) {
  return prepareColumns(columns, {
    rowIndex: -1,
    isHeader: 1,
    format: function format(content) {
      return '<span>' + content + '</span>';
    }
  });
}

function prepareRow(row, i) {
  return prepareColumns(row, {
    rowIndex: i
  });
}

function prepareRows(rows) {
  return rows.map(prepareRow);
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

function namespaceSelector(selector) {
  return '.data-table ' + selector;
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

exports.default = {
  getHeaderHTML: getHeaderHTML,
  getBodyHTML: getBodyHTML,
  getRowHTML: getRowHTML,
  getColumnHTML: getColumnHTML,
  getEditCellHTML: getEditCellHTML,
  prepareRowHeader: prepareRowHeader,
  prepareRows: prepareRows,
  namespaceSelector: namespaceSelector,
  getCSSString: getCSSString,
  buildCSSRule: buildCSSRule,
  makeDataAttributeString: makeDataAttributeString,
  getDefault: getDefault,
  escapeRegExp: escapeRegExp
};
module.exports = exports['default'];

/***/ }),
/* 3 */
/***/ (function(module, exports, __webpack_require__) {

// style-loader: Adds some css to the DOM by adding a <style> tag

// load the styles
var content = __webpack_require__(4);
if(typeof content === 'string') content = [[module.i, content, '']];
// Prepare cssTransformation
var transform;

var options = {}
options.transform = transform
// add the styles to the DOM
var update = __webpack_require__(6)(content, options);
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
/* 4 */
/***/ (function(module, exports, __webpack_require__) {

exports = module.exports = __webpack_require__(5)(undefined);
// imports


// module
exports.push([module.i, ".table {\n  width: 100%;\n  max-width: 100%;\n  margin-bottom: 1rem;\n  background-color: transparent; }\n  .table th,\n  .table td {\n    padding: 0.75rem;\n    vertical-align: top;\n    border-top: 1px solid #e9ecef; }\n  .table thead th {\n    vertical-align: bottom;\n    border-bottom: 2px solid #e9ecef; }\n  .table tbody + tbody {\n    border-top: 2px solid #e9ecef; }\n  .table .table {\n    background-color: #fff; }\n\n.table-sm th,\n.table-sm td {\n  padding: 0.3rem; }\n\n.table-bordered {\n  border: 1px solid #e9ecef; }\n  .table-bordered th,\n  .table-bordered td {\n    border: 1px solid #e9ecef; }\n  .table-bordered thead th,\n  .table-bordered thead td {\n    border-bottom-width: 2px; }\n\n.table-striped tbody tr:nth-of-type(odd) {\n  background-color: rgba(0, 0, 0, 0.05); }\n\n.table-hover tbody tr:hover {\n  background-color: rgba(0, 0, 0, 0.075); }\n\n.table-primary,\n.table-primary > th,\n.table-primary > td {\n  background-color: #b8daff; }\n\n.table-hover .table-primary:hover {\n  background-color: #9fcdff; }\n  .table-hover .table-primary:hover > td,\n  .table-hover .table-primary:hover > th {\n    background-color: #9fcdff; }\n\n.table-secondary,\n.table-secondary > th,\n.table-secondary > td {\n  background-color: #dddfe2; }\n\n.table-hover .table-secondary:hover {\n  background-color: #cfd2d6; }\n  .table-hover .table-secondary:hover > td,\n  .table-hover .table-secondary:hover > th {\n    background-color: #cfd2d6; }\n\n.table-success,\n.table-success > th,\n.table-success > td {\n  background-color: #c3e6cb; }\n\n.table-hover .table-success:hover {\n  background-color: #b1dfbb; }\n  .table-hover .table-success:hover > td,\n  .table-hover .table-success:hover > th {\n    background-color: #b1dfbb; }\n\n.table-info,\n.table-info > th,\n.table-info > td {\n  background-color: #bee5eb; }\n\n.table-hover .table-info:hover {\n  background-color: #abdde5; }\n  .table-hover .table-info:hover > td,\n  .table-hover .table-info:hover > th {\n    background-color: #abdde5; }\n\n.table-warning,\n.table-warning > th,\n.table-warning > td {\n  background-color: #ffeeba; }\n\n.table-hover .table-warning:hover {\n  background-color: #ffe8a1; }\n  .table-hover .table-warning:hover > td,\n  .table-hover .table-warning:hover > th {\n    background-color: #ffe8a1; }\n\n.table-danger,\n.table-danger > th,\n.table-danger > td {\n  background-color: #f5c6cb; }\n\n.table-hover .table-danger:hover {\n  background-color: #f1b0b7; }\n  .table-hover .table-danger:hover > td,\n  .table-hover .table-danger:hover > th {\n    background-color: #f1b0b7; }\n\n.table-light,\n.table-light > th,\n.table-light > td {\n  background-color: #fdfdfe; }\n\n.table-hover .table-light:hover {\n  background-color: #ececf6; }\n  .table-hover .table-light:hover > td,\n  .table-hover .table-light:hover > th {\n    background-color: #ececf6; }\n\n.table-dark,\n.table-dark > th,\n.table-dark > td {\n  background-color: #c6c8ca; }\n\n.table-hover .table-dark:hover {\n  background-color: #b9bbbe; }\n  .table-hover .table-dark:hover > td,\n  .table-hover .table-dark:hover > th {\n    background-color: #b9bbbe; }\n\n.table-active,\n.table-active > th,\n.table-active > td {\n  background-color: rgba(0, 0, 0, 0.075); }\n\n.table-hover .table-active:hover {\n  background-color: rgba(0, 0, 0, 0.075); }\n  .table-hover .table-active:hover > td,\n  .table-hover .table-active:hover > th {\n    background-color: rgba(0, 0, 0, 0.075); }\n\n.thead-inverse th {\n  color: #fff;\n  background-color: #212529; }\n\n.thead-default th {\n  color: #495057;\n  background-color: #e9ecef; }\n\n.table-inverse {\n  color: #fff;\n  background-color: #212529; }\n  .table-inverse th,\n  .table-inverse td,\n  .table-inverse thead th {\n    border-color: #32383e; }\n  .table-inverse.table-bordered {\n    border: 0; }\n  .table-inverse.table-striped tbody tr:nth-of-type(odd) {\n    background-color: rgba(255, 255, 255, 0.05); }\n  .table-inverse.table-hover tbody tr:hover {\n    background-color: rgba(255, 255, 255, 0.075); }\n\n@media (max-width: 991px) {\n  .table-responsive {\n    display: block;\n    width: 100%;\n    overflow-x: auto;\n    -ms-overflow-style: -ms-autohiding-scrollbar; }\n    .table-responsive.table-bordered {\n      border: 0; } }\n\n.data-table {\n  width: 100%;\n  position: relative;\n  overflow: auto; }\n  .data-table .table {\n    border-collapse: collapse; }\n  .data-table .table > thead > tr > td, .data-table .table > tbody > tr > td {\n    padding: 0; }\n\n.body-scrollable {\n  max-height: 500px;\n  overflow: auto;\n  border-bottom: 1px solid #e9ecef; }\n\n.data-table-header {\n  position: absolute;\n  top: 0;\n  left: 0;\n  background-color: white;\n  font-weight: bold;\n  cursor: col-resize; }\n  .data-table-header .content span {\n    cursor: pointer; }\n  .data-table-header .sort-indicator {\n    position: absolute;\n    right: 8px;\n    top: 9px; }\n\n.data-table-col {\n  position: relative; }\n  .data-table-col .content {\n    padding: 8px;\n    border: 1px solid white; }\n  .data-table-col.selected .content {\n    border: 1px solid #007bff; }\n  .data-table-col .content.ellipsis {\n    text-overflow: ellipsis;\n    white-space: nowrap;\n    overflow: hidden; }\n\n.edit-cell {\n  position: absolute;\n  top: -1px;\n  left: -1px;\n  background: white;\n  z-index: 1; }\n  .edit-cell input {\n    outline: none;\n    padding: 8px;\n    font-size: inherit;\n    font-family: inherit;\n    width: inherit;\n    height: inherit;\n    border: 2px solid #007bff; }\n\n.noselect {\n  -webkit-touch-callout: none;\n  -webkit-user-select: none;\n  -khtml-user-select: none;\n  -moz-user-select: none;\n  -ms-user-select: none;\n  user-select: none; }\n", ""]);

// exports


/***/ }),
/* 5 */
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
/* 6 */
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

var	fixUrls = __webpack_require__(7);

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
/* 7 */
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


/***/ })
/******/ ]);
});
//# sourceMappingURL=regrid.js.map