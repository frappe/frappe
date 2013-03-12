// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

_f.FormGrid = function(field) {
	this.field = field;
	this.doctype = field.df.options;
		
	if(!this.doctype) {
		show_alert('No Options for table ' + field.df.label); 
	}
	
	this.col_break_width = cint(this.field.col_break_width);
	if(!this.col_break_width) this.col_break_width = 100;
	
	$y(field.wrapper,{marginTop:'8px'});
	this.init(field.wrapper, field.df.width);
	this.setup();
}

_f.FormGrid.prototype = new _f.Grid();

_f.FormGrid.prototype.setup = function() {
	this.make_columns();
}

_f.FormGrid.prototype.make_buttons = function() {
	var me = this;
	this.tbar_btns = {};
	this.tbar_btns['Del'] = this.make_tbar_link($td(this.tbar_tab,0,0),wn._('Del'), 
		function() { me.delete_row(); }, 'icon-remove-sign');
	this.tbar_btns['Ins'] = this.make_tbar_link($td(this.tbar_tab,0,1),wn._('Ins'), 
		function() { me.insert_row(); }, 'icon-plus');
	this.tbar_btns['Up'] = this.make_tbar_link($td(this.tbar_tab,0,2),wn._('Up'), 
		function() { me.move_row(true); }, 'icon-arrow-up');
	this.tbar_btns['Dn'] = this.make_tbar_link($td(this.tbar_tab,0,3),wn._('Dn'), 
		function() { me.move_row(false); }, 'icon-arrow-down');
		
	for(var i in this.btns)
		this.btns[i].isactive = true;
}

_f.FormGrid.prototype.make_tbar_link = function(parent, label, fn, icon) {

	var div = $a(parent,'div','',{cursor:'pointer'});
	var t = make_table(div, 1, 2, '90%', ['20px',null]);
	var img = $a($td(t,0,0), 'i' , icon);

	$y($td(t,0,0),{textAlign:'right'});

	var l = $a($td(t,0,1),'span','link_type',{color:'#333'});
	l.style.fontSize = '11px';
	l.innerHTML = label;
	div.onclick = fn;
	div.show = function() { $ds(this); }
	div.hide = function() { $dh(this); }

	$td(t,0,0).isactive = 1;
	$td(t,0,1).isactive = 1;
	l.isactive = 1;
	div.isactive = 1;
	img.isactive = 1;

	return div;
}

_f.FormGrid.prototype.make_columns = function() {
	var p = this.field.perm;
	if(p[this.field.df.permlevel] && p[this.field.df.permlevel][READ]) { // if read
		var gl = wn.meta.docfield_list[this.field.df.options];

		if(!gl) {
			alert('Table details not found "'+this.field.df.options+'"');
		}

		gl.sort(function(a,b) { return a.idx - b.idx});
		
		for(var i=0;i<gl.length;i++) {
			this.insert_column(this.field.df.options, gl[i].fieldname, gl[i].fieldtype, gl[i].label, gl[i].width, gl[i].options, this.field.perm, gl[i].reqd, gl[i]);

			// hide it even if it is hidden at start..
			// so that it can be brought back once
			// also, hide column if no permissions found
			if(gl[i].hidden || !(p[gl[i].permlevel] && p[gl[i].permlevel][READ])) {
				this.set_column_disp(gl[i].fieldname, false);
			}
		}
	}
}

_f.FormGrid.prototype.set_column_label = function(fieldname, label) {
	for(var i=0;i<this.head_row.cells.length;i++) {
		var c = this.head_row.cells[i];
		if(c.fieldname == fieldname) {
			c.innerHTML = '<div class="grid_head_div">'+label+'</div>';
			c.cur_label = label;
			break;
		}
	}
}

_f.FormGrid.prototype.get_children = function() {
	return getchildren(this.doctype, this.field.frm.docname, this.field.df.fieldname, this.field.frm.doctype);
}

_f.FormGrid.prototype.refresh = function() {
	var docset = this.get_children();
	var data = [];
	
	//alert(docset.length);
	for(var i=0; i<docset.length; i++) {
		locals[this.doctype][docset[i].name].idx = i+1;
		data[data.length] = docset[i].name;
	}
	this.set_data(data);
	
	// if form open, refresh form
	if(_f.frm_dialog && _f.frm_dialog.dialog.display &&  _f.frm_dialog.cur_frm) {
		_f.frm_dialog.cur_frm.refresh();
	}
}

_f.FormGrid.prototype.set_unsaved = function() {
	// set unsaved
	cur_frm.set_unsaved();
}

_f.FormGrid.prototype.insert_row = function() {
	var d = this.new_row_doc();
	var ci = _f.cur_grid_cell.cellIndex;
	var row_idx = _f.cur_grid_cell.row.rowIndex;
	d.idx = row_idx+1;
	for(var ri = row_idx; ri<this.tab.rows.length; ri++) {
		var r = this.tab.rows[ri];
		if(r.docname)
			locals[this.doctype][r.docname].idx++;
	}
	// refresh
	this.refresh();
	this.cell_select('', row_idx, ci);

	if(this.onrowadd) this.onrowadd(cur_frm.doc, d.doctype, d.name);
}

_f.FormGrid.prototype.new_row_doc = function() {
	// create row doc
	var n = wn.model.make_new_doc_and_get_name(this.doctype);
	var d = locals[this.doctype][n];
	d.parent = this.field.frm.docname;
	d.parentfield = this.field.df.fieldname;
	d.parenttype = this.field.frm.doctype;
	this.set_unsaved();
	return d;
}
_f.FormGrid.prototype.add_newrow = function() {
	var r = this.tab.rows[this.tab.rows.length - 1];
	if(!r.is_newrow)
		throw 'Adding a row which is not flagged as new';

	var d = this.new_row_doc();
	d.idx = r.rowIndex + 1;

	// set row
	r.docname = d.name;
	//r.cells[0].div.innerHTML = r.rowIndex + 1;
	r.is_newrow = false;
	this.set_cell_value(r.cells[0]);
	
	// one more
	this.make_newrow();
	this.refresh_row(r.rowIndex, d.name); // added 26-Mar-09
	
	if(this.onrowadd) this.onrowadd(cur_frm.doc, d.doctype, d.name);
	
	return d.name;
}

_f.FormGrid.prototype.make_newrow = function(from_add_btn) {
	if(!this.can_add_rows) // No Addition
		return;
		
	// check if exists
	if(this.tab.rows.length) {
		var r = this.tab.rows[this.tab.rows.length - 1];
		if(r.is_newrow)
			return;
	}
	
	// make new
	var r = this.append_row();
	r.cells[0].div.innerHTML = '<b style="font-size: 18px;">*</b>';	
	r.is_newrow = true;
}

_f.FormGrid.prototype.check_selected = function() {
	if(!_f.cur_grid_cell) {
		show_alert(wn._('Select a cell first'));
		return false;
	}
	if(_f.cur_grid_cell.grid != this) {
		show_alert(wn._('Select a cell first'));
		return false;
	}
	return true;
}

_f.FormGrid.prototype.delete_row = function(dt, dn) {
	if(dt && dn) {
		wn.model.clear_doc(dt, dn);
		this.refresh();
	} else {
		if(!this.check_selected()) return;
		var r = _f.cur_grid_cell.row;
		if(r.is_newrow)return;

		var ci = _f.cur_grid_cell.cellIndex;
		var ri = _f.cur_grid_cell.row.rowIndex;
		
		wn.model.clear_doc(this.doctype, r.docname);	
		
		this.refresh();
		if(ri < (this.tab.rows.length-1))
			this.cell_select(null, ri, ci);
		else _f.cur_grid_cell = null;	
	}
	this.set_unsaved();
	
	if(this.on_row_delete) this.on_row_delete(cur_frm.doc, dt, dn);
}

_f.FormGrid.prototype.clear_table = function() {
	var me = this;
	$.each(this.get_children(), function(i, d) {
		wn.model.clear_doc(d.doctype, d.name);
		if(me.on_row_delete) me.on_row_delete(cur_frm.doc, d.doctype, d.name);
	});
	this.refresh();
	this.set_unsaved();
}

_f.FormGrid.prototype.move_row = function(up) {
	
	if(!this.check_selected()) return;
	var r = _f.cur_grid_cell.row;	
	if(r.is_newrow)return;

	if(up && r.rowIndex > 0) {
		var swap_row = this.tab.rows[r.rowIndex - 1];
	} else if (!up) {
		var len = this.tab.rows.length;
		if(this.tab.rows[len-1].is_newrow)
			len = len - 1;
		if(r.rowIndex < (len-1))
			var swap_row = this.tab.rows[r.rowIndex + 1];	
	}
	
	if(swap_row) {
		var cidx = _f.cur_grid_cell.cellIndex;
		this.cell_deselect();

		// swap index
		var aidx = locals[this.doctype][r.docname].idx;
		locals[this.doctype][r.docname].idx = locals[this.doctype][swap_row.docname].idx; 
		locals[this.doctype][swap_row.docname].idx = aidx;

		// swap rows
		var adocname = swap_row.docname;
		this.refresh_row(swap_row.rowIndex, r.docname);
		this.refresh_row(r.rowIndex, adocname);

		this.cell_select(this.tab.rows[swap_row.rowIndex].cells[cidx]);
		
		this.set_unsaved();
	}
}
