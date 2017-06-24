(function ($) {
  // register namespace
  $.extend(true, window, {
    "Slick": {
      "CellExternalCopyManager": CellExternalCopyManager
    }
  });


  function CellExternalCopyManager(options) {
    /*
      This manager enables users to copy/paste data from/to an external Spreadsheet application
      
      Since it is not possible to access directly the clipboard in javascript, the plugin uses
      a trick to do it's job. After detecting the keystroke, we dynamically create a textarea
      where the browser copies/pastes the serialized data. 
      
      options:
        copiedCellStyle : sets the css className used for copied cells. default : "copied"
        copiedCellStyleLayerKey : sets the layer key for setting css values of copied cells. default : "copy-manager"
        dataItemColumnValueExtractor : option to specify a custom column value extractor function
        dataItemColumnValueSetter : option to specify a custom column value setter function
    */
    var _grid;
    var _self = this;
    var _copiedRanges;
    var _options = options || {};
    var _copiedCellStyleLayerKey = _options.copiedCellStyleLayerKey || "copy-manager";
    var _copiedCellStyle = _options.copiedCellStyle || "copied";
    var _clearCopyTI = 0;
    
    var keyCodes = {
      'C':67,
      'V':86
    }

    function init(grid) {
      _grid = grid;
      _grid.onKeyDown.subscribe(handleKeyDown);
      
      // we need a cell selection model
      var cellSelectionModel = grid.getSelectionModel();
      if (!cellSelectionModel){
        throw new Error("Selection model is mandatory for this plugin. Please set a selection model on the grid before adding this plugin: grid.setSelectionModel(new Slick.CellSelectionModel())");
      }
      // we give focus on the grid when a selection is done on it.
      // without this, if the user selects a range of cell without giving focus on a particular cell, the grid doesn't get the focus and key stroke handles (ctrl+c) don't work
      cellSelectionModel.onSelectedRangesChanged.subscribe(function(e, args){
        _grid.focus();
      });
    }

    function destroy() {
      _grid.onKeyDown.unsubscribe(handleKeyDown);
    }
    
    function getDataItemValueForColumn(item, columnDef) {
      if (_options.dataItemColumnValueExtractor) {
        return _options.dataItemColumnValueExtractor(item, columnDef);
      }
      // if a custom getter is not defined, we call serializeValue of the editor to serialize
      var editorArgs = {
        'container':$(document),  // a dummy container
        'column':columnDef
      };
      var editor = new columnDef.editor(editorArgs);
      var retVal = '';
      editor.loadValue(item);
      retVal = editor.serializeValue();
      editor.destroy();

      return retVal;
    }
    
    function setDataItemValueForColumn(item, columnDef, value) {
      if (_options.dataItemColumnValueSetter) {
        return _options.dataItemColumnValueSetter(item, columnDef, value);
      }
      // if a custom setter is not defined, we call applyValue of the editor to unserialize
      var editorArgs = {
        'container':$(document),  // a dummy container
        'column':columnDef
      };
      var editor = new columnDef.editor(editorArgs);
      editor.loadValue(item);
      editor.applyValue(item, value);
      editor.destroy();
    }
    
    
    function _createTextBox(innerText){
      var ta = document.createElement('textarea');
      ta.style.position = 'absolute';
      ta.style.left = '-1000px';
      ta.style.top = '-1000px';
      ta.value = innerText;
      document.body.appendChild(ta);
      ta.focus();
      
      return ta;
    }
    
    function _decodeTabularData(_grid, ta){
      var columns = _grid.getColumns();
      var clipText = ta.value;
      var clipRows = clipText.split(/[\n\f\r]/);
      var clippedRange = [];
      
      document.body.removeChild(ta);

      for (var i=0; i<clipRows.length; i++) {
        if (clipRows[i]!="")
          clippedRange[i] = clipRows[i].split("\t");
      }
      
      var selectedCell = _grid.getActiveCell();
      var ranges = _grid.getSelectionModel().getSelectedRanges();
      var selectedRange = ranges && ranges.length ? ranges[0] : null;   // pick only one selection
      var activeRow = null;
      var activeCell = null;
      
      if (selectedRange){
        activeRow = selectedRange.fromRow;
        activeCell = selectedRange.fromCell;
      } else if (selectedCell){
        activeRow = selectedCell.row;
        activeCell = selectedCell.cell;
      } else {
        // we don't know where to paste
        return;
      }
      
      var oneCellToMultiple = false;
      var destH = clippedRange.length;
      var destW = clippedRange.length ? clippedRange[0].length : 0;
      if (clippedRange.length == 1 && clippedRange[0].length == 1 && selectedRange){
        oneCellToMultiple = true;
        destH = selectedRange.toRow - selectedRange.fromRow +1;
        destW = selectedRange.toCell - selectedRange.fromCell +1;
      }
      
      var desty = activeRow;
      var destx = activeCell;
      var h = 0;
      var w = 0;
      
      for (var y = 0; y < destH; y++){
        h++;
        w=0;
        for (var x = 0; x < destW; x++){
          w++;
          var desty = activeRow + y;
          var destx = activeCell + x;
          
          if (desty < data.length && destx < grid.getColumns().length ) { 
            var nd = _grid.getCellNode(desty, destx);
            var dt = _grid.getDataItem(desty);
            if (oneCellToMultiple)
              setDataItemValueForColumn(dt, columns[destx], clippedRange[0][0]);
            else
              setDataItemValueForColumn(dt, columns[destx], clippedRange[y][x]);
            _grid.updateCell(desty, destx);
          }
        }
      }
      
      var bRange = {
        'fromCell': activeCell,
        'fromRow': activeRow,
        'toCell': activeCell+w-1,
        'toRow': activeRow+h-1
      }

      markCopySelection([bRange]);
      _grid.getSelectionModel().setSelectedRanges([bRange]);
      _self.onPasteCells.notify({ranges: [bRange]});
    }
    
    
    function handleKeyDown(e, args) {
      var ranges;
      if (!_grid.getEditorLock().isActive()) {
        if (e.which == frappe.ui.keyCode.ESCAPE) {
          if (_copiedRanges) {
            e.preventDefault();
            clearCopySelection();
            _self.onCopyCancelled.notify({ranges: _copiedRanges});
            _copiedRanges = null;
          }
        }
        
        if (e.which == keyCodes.C && (e.ctrlKey || e.metaKey)) {    // CTRL + C
          ranges = _grid.getSelectionModel().getSelectedRanges();
          if (ranges.length != 0) {
            _copiedRanges = ranges;
            markCopySelection(ranges);
            _self.onCopyCells.notify({ranges: ranges});
            
            var columns = _grid.getColumns();
            var clipTextArr = [];
            
            for (var rg = 0; rg < ranges.length; rg++){
                var range = ranges[rg];
                var clipTextRows = [];
                for (var i=range.fromRow; i< range.toRow+1 ; i++){
                    var clipTextCells = [];
                    var dt = _grid.getDataItem(i);
                    
                    for (var j=range.fromCell; j< range.toCell+1 ; j++){
                        clipTextCells.push(getDataItemValueForColumn(dt, columns[j]));
                    }
                    clipTextRows.push(clipTextCells.join("\t"));
                }
                clipTextArr.push(clipTextRows.join("\r\n"));
            }
            var clipText = clipTextArr.join('');
            var ta = _createTextBox(clipText);
            $(ta).select();
            
            setTimeout(function(){
                document.body.removeChild(ta);
            }, 100);
            
            return false;
          }
        }

        if (e.which == keyCodes.V && (e.ctrlKey || e.metaKey)) {    // CTRL + V
            var ta = _createTextBox('');
            
            setTimeout(function(){
                _decodeTabularData(_grid, ta);
            }, 100);
            
            return false;
        }
      }
    }

    function markCopySelection(ranges) {
      clearCopySelection();
      
      var columns = _grid.getColumns();
      var hash = {};
      for (var i = 0; i < ranges.length; i++) {
        for (var j = ranges[i].fromRow; j <= ranges[i].toRow; j++) {
          hash[j] = {};
          for (var k = ranges[i].fromCell; k <= ranges[i].toCell && k<columns.length; k++) {
            hash[j][columns[k].id] = _copiedCellStyle;
          }
        }
      }
      _grid.setCellCssStyles(_copiedCellStyleLayerKey, hash);
      clearTimeout(_clearCopyTI);
      _clearCopyTI = setTimeout(function(){
        _self.clearCopySelection();
      }, 2000);
    }

    function clearCopySelection() {
      _grid.removeCellCssStyles(_copiedCellStyleLayerKey);
    }

    $.extend(this, {
      "init": init,
      "destroy": destroy,
      "clearCopySelection": clearCopySelection,
      "handleKeyDown":handleKeyDown,
      "onCopyCells": new Slick.Event(),
      "onCopyCancelled": new Slick.Event(),
      "onPasteCells": new Slick.Event()
    });
  }
})(jQuery);