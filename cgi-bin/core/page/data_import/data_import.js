(function() {
  var ColumnSelect, DataImport;
  var __bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; };
  DataImport = (function() {
    function DataImport() {
      this.upload_done = __bind(this.upload_done, this);      new PageHeader($('#data_importer .head').get(0), 'Import Data');
      new Uploader($('#upload_form').get(0), {
        cmd: 'core.page.data_import.data_import.upload'
      }, pscript.check_upload);
    }
    DataImport.prototype.upload_done = function(first_row) {
      this.first_row = first_row;
      return this.show_table_select;
    };
    DataImport.prototype.show_table_select = function() {
      var s;
      $ds($('#data_importer .box').get(1));
      s = $i('import_table_select');
      add_sel_options(s, add_lists([''], session.can_read));
      return $(s).change(function() {
        return this.load_doctype(sel_val(s));
      });
    };
    DataImport.prototype.load_doctype = function() {};
    return DataImport;
  })();
  ColumnSelect = (function() {
    function ColumnSelect() {}
    return ColumnSelect;
  })();
  pscript['onload_data-import'] = function() {
    return pscript.data_import = new DataImport();
  };
  pscript.upload_done = function(first_row) {
    var s;
    $ds($('#data_importer .box').get(1));
    s = $i('import_table_select');
    add_sel_options(s, add_lists([''], session.can_read));
    $(s).change(function() {});
    return msgprint(first_row);
  };
}).call(this);
