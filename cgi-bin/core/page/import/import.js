(function() {
  var ColumnSelect, ColumnSelector, ImportSection, Output, TableSelector, Uploader;
  var __hasProp = Object.prototype.hasOwnProperty, __extends = function(child, parent) {
    for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; }
    function ctor() { this.constructor = child; }
    ctor.prototype = parent.prototype;
    child.prototype = new ctor;
    child.__super__ = parent.prototype;
    return child;
  };
  ImportSection = (function() {
    function ImportSection() {}
    ImportSection.prototype.render = function(label, description, hidden) {
      this.wrapper = $a($('#data_importer .body').get(0), 'div', 'box round');
      this.head = $a(this.wrapper, 'h3', 'head', null, label);
      $a(this.wrapper, 'div', 'comment', null, description);
      this.body = $a(this.wrapper, 'div');
      if (hidden) {
        return $dh(this.wrapper);
      }
    };
    return ImportSection;
  })();
  Uploader = (function() {
    __extends(Uploader, ImportSection);
    function Uploader() {
      this.render('Step 1: Upload A File', 'Upload a file in ".csv" format. <ol>\
		<li>The first row should be headings.\
		<li>Please do not enter blank rows.\
		<li>If you using a spreadsheet, select "Save As" CSV to \
		generate the csv file.</ol>');
    }
    return Uploader;
  })();
  TableSelector = (function() {
    function TableSelector() {}
    return TableSelector;
  })();
  ColumnSelector = (function() {
    function ColumnSelector() {}
    return ColumnSelector;
  })();
  ColumnSelect = (function() {
    function ColumnSelect() {}
    return ColumnSelect;
  })();
  Output = (function() {
    function Output() {}
    return Output;
  })();
  pscript.onload_import = function() {
    new PageHeader($('#data_importer .head').get(0), 'Import Data');
    return new Uploader();
  };
}).call(this);
