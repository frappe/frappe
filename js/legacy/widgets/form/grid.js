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

// _f.Grid

_f.cur_grid_cell = null;
_f.Grid = function(parent) { }

_f.Grid.prototype.init = function(parent, row_height) {
	
	var me = this;
	this.col_idx_by_name = {}
	this.alt_row_bg = '#F2F2FF';
	this.row_height = row_height;

	// make the grid
	if(!row_height)this.row_height = '26px';
	this.make_ui(parent);
		
	// Sr No
	this.insert_column('', '', 'Int', 'Sr', '50px', '', [1,0,0]);
	
	if(this.oninit)this.oninit();
	
	// bind clicks
	$(this.wrapper).bind('keydown', function(e) {
		me.notify_keypress(e, e.which);
	})
	
	// reset grid heights after complete is triggerd on the form
	$(cur_frm.wrapper).bind('render_complete', function() {
		me.set_ht();
	});	
}

_f.Grid.prototype.make_ui = function(parent) { 

	var ht = make_table($a(parent, 'div'), 1, 2, '100%', ['60%','40%']);
	this.main_title = $td(ht,0,0); this.main_title.className = 'columnHeading';
	$td(ht,0,1).style.textAlign = 'right';
	this.tbar_div = $a($td(ht,0,1), 'div', 'grid_tbarlinks');
	this.tbar_tab = make_table(this.tbar_div,1,4,'100%',['25%','25%','25%','25%']);	
			
	this.wrapper = $a(parent, 'div', 'grid_wrapper');

	this.head_wrapper = $a(this.wrapper, 'div', 'grid_head_wrapper');

	this.head_tab = $a(this.head_wrapper, 'table', 'grid_head_table');
	this.head_row = this.head_tab.insertRow(0);

	this.tab_wrapper = $a(this.wrapper, 'div', 'grid_tab_wrapper');	
	this.tab = $a(this.tab_wrapper, 'table', 'grid_table');

	var me = this;
	
	this.wrapper.onscroll = function() { me.head_wrapper.style.top = me.wrapper.scrollTop+'px'; }
}

_f.Grid.prototype.show = function() { 
	if(this.can_edit && this.field.df['default'].toLowerCase()!='no toolbar') {
		$ds(this.tbar_div);
		if(this.can_add_rows) {
			$td(this.tbar_tab, 0, 0).style.display = 'table-cell';
			$td(this.tbar_tab, 0, 1).style.display = 'table-cell';
		} else {
			$td(this.tbar_tab, 0, 0).style.display = 'none';
			$td(this.tbar_tab, 0, 1).style.display = 'none';
		}
	} else {
		$dh(this.tbar_div);
	}
	$ds(this.wrapper);
}
_f.Grid.prototype.hide = function() { 
	$dh(this.wrapper); $dh(this.tbar_div); 
}

_f.Grid.prototype.insert_column = function(doctype, fieldname, fieldtype, label, width, options, perm, reqd) {
	
	var idx = this.head_row.cells.length;
	if(!width)width = '100px';
	if((width+'').slice(-2)!='px') {
		width= width + 'px';
	}
	var col = this.head_row.insertCell(idx);
	
	col.doctype = doctype; // for report (fields may be from diff doctypes)
	col.fieldname = fieldname;
	col.fieldtype = fieldtype;
	col.innerHTML = '<div data-grid-fieldname = "'+doctype+'-'+fieldname+'">'+label+'</div>';
	col.label = label;
	if(reqd)
		col.childNodes[0].style.color = "#D22";
	
	col.style.width = width;
	col.options = options;
	col.perm = perm;

	this.col_idx_by_name[fieldname] = idx;
}

_f.Grid.prototype.reset_table_width = function() { 
	var w = 0;
	$.each(this.head_row.cells, function(i, cell) {
		if((cell.style.display || '').toLowerCase()!='none')
			w += cint(cell.style.width);
	})
	
	this.head_tab.style.width = w + 'px';
	this.tab.style.width = w + 'px';
}

_f.Grid.prototype.set_column_disp = function(fieldname, show) { 
	var cidx = this.col_idx_by_name[fieldname];
	if(!cidx) {
		msgprint('Trying to hide unknown column: ' + fieldname);
		return;
	}
	
	var disp = show ? 'table-cell' : 'none';

	// head
	this.head_row.cells[cidx].style.display = disp;

	// body
	for(var i=0, len=this.tab.rows.length; i<len; i++) {
		var cell = this.tab.rows[i].cells[cidx];
		cell.style.display = disp;
	}
	
	// reset table width
	this.reset_table_width();
}

_f.Grid.prototype.append_row = function(idx, docname) { 
	if(!idx)idx = this.tab.rows.length;
	var row = this.tab.insertRow(idx);
	row.docname = docname;
	
	if(idx % 2)var odd=true; else var odd=false;

	var me = this;
	// make cells
	for(var i=0; i<this.head_row.cells.length; i++){
		var cell = row.insertCell(i);
		var hc = this.head_row.cells[i];
		
		// ape style of head
		cell.style.width = hc.style.width;
		cell.style.display = hc.style.display;
		
		cell.row = row;
		cell.grid = this;
		cell.className = 'grid_cell';

		cell.div = $a(cell, 'div', 'grid_cell_div');
		if(this.row_height) {
			cell.div.style.height = this.row_height; }
		cell.div.cell = cell;
		cell.div.onclick = function(e) { me.cell_select(this.cell); }

		if(odd) {
			$bg(cell, this.alt_row_bg); cell.is_odd = 1;
			cell.div.style.border = '2px solid ' + this.alt_row_bg;
		} else $bg(cell,'#FFF');

		if(!hc.fieldname) cell.div.style.cursor = 'default'; // Index
	}

	this.set_ht();

	return row;	
}

_f.Grid.prototype.refresh_cell = function(docname, fieldname) {
	for(var r=0;r<this.tab.rows.length;r++) {
		if(this.tab.rows[r].docname==docname) {
			for(var c=0;c<this.head_row.cells.length;c++) {
				var hc = this.head_row.cells[c];
				if(hc.fieldname==fieldname) {
					this.set_cell_value(this.tab.rows[r].cells[c]);
				}
			}
		}
	}
}

// for form edit
_f.cur_grid; 
_f.cur_grid_ridx; 

_f.Grid.prototype.set_cell_value = function(cell) {
	// if newrow
	if(cell.row.is_newrow)return;

	// show static
	var hc = this.head_row.cells[cell.cellIndex];
	
	if(hc.fieldname && locals[hc.doctype][cell.row.docname]) {
		var v = locals[hc.doctype][cell.row.docname][hc.fieldname];
	} else {
		var v = (cell.row.rowIndex + 1); // Index
	}
	
	if(v==null){ v=''; }
	var me = this;
	
	// variations
	if(cell.cellIndex) {
		var ft = hc.fieldtype;
		if(ft=='Link' && cur_frm.doc.docstatus < 1) ft='Data';
		$s(cell.div, v, ft, hc.options);
	} else {
		// Index column
		cell.div.style.padding = '2px';
		cell.div.style.textAlign = 'left';
		cell.innerHTML = '';

		var t = make_table(cell,1,3,'60px',['20px','20px','20px'],{verticalAlign: 'middle', padding:'2px'});
		$y($td(t,0,0),{paddingLeft:'4px'});
		$td(t,0,0).innerHTML = cell.row.rowIndex + 1;

		if(cur_frm.editable && this.can_edit) {

			var ed = $a($td(t,0,1),'i','icon-edit',{cursor:'pointer'}); ed.cell = cell; ed.title = 'Edit Row';
			ed.onclick = function() { 
				_f.cur_grid = me;
				_f.cur_grid_ridx = this.cell.row.rowIndex;
				_f.edit_record(me.doctype, this.cell.row.docname, 1);				
			}
			
		} else {
			cell.div.innerHTML = (cell.row.rowIndex + 1);
			cell.div.style.cursor = 'default';
			cell.div.onclick = function() { }
		}
	}
}

// if clicked on whitespace 
// and a grid cell is selected
// deselect the cell
$(document).bind('click', function(e) {
	var me = this;
	var is_target_toolbar = function() {
		return $(e.target).parents('.grid_tbarlinks').length;
	}
	
	var is_target_input = function() {
		// select opened
		if(e.target.tagName.toLowerCase()=='option') return true;
		
		// autosuggest openend
		//if(wn._autosugg_open) return true;
				
		return $(e.target).parents().get().indexOf(_f.cur_grid_cell)!=-1;
	}
	
	if(_f.cur_grid_cell && !is_target_input() && !is_target_toolbar()) {
		if(!(text_dialog && text_dialog.display) 
			&& !datepicker_active && !(selector && selector.display)) {
				setTimeout('_f.cur_grid_cell.grid.cell_deselect()', 500);
				return false;
		}
	}
});

_f.Grid.prototype.cell_deselect = function() {
	if(_f.cur_grid_cell) {
		var c = _f.cur_grid_cell;
		c.grid.remove_template(c);
		c.div.className = 'grid_cell_div';
		if(c.is_odd) c.div.style.border = '2px solid ' + c.grid.alt_row_bg;
		else c.div.style.border = '2px solid #FFF';
		_f.cur_grid_cell = null;
	}
}

_f.Grid.prototype.cell_select = function(cell, ri, ci) {
	if(_f.cur_grid_cell==cell && cell.hc) return;
	
	if(ri!=null && ci!=null)
		cell = this.tab.rows[ri].cells[ci];

	var hc = this.head_row.cells[cell.cellIndex];
	
	if(!hc.template) {
		this.make_template(hc);
	}

	hc.template.perm = this.field ? this.field.perm : hc.perm; // get latest permissions

	if(hc.fieldname && hc.template.get_status()=='Write') {
		this.cell_deselect();
		cell.div.style.border = '2px solid #88F';
		_f.cur_grid_cell = cell;
		this.add_template(cell);
	}
}

_f.Grid.prototype.add_template = function(cell) {
	if(!cell.row.docname && this.add_newrow) { // activate new row here
		this.add_newrow();
		this.cell_select(cell);
	} else {
		var hc = this.head_row.cells[cell.cellIndex];
		cell.div.innerHTML = '';
		cell.div.appendChild(hc.template.wrapper);
		hc.template.activate(cell.row.docname);
		hc.template.activated=1;
		cell.hc = hc;
		
		if(hc.template.input && hc.template.input.set_width) {
			hc.template.input.set_width($(cell).width());
		}
	}
}

_f.Grid.prototype.get_field = function(fieldname) { // get template
	for(var i=0;i<this.head_row.cells.length;i++) {
		var hc = this.head_row.cells[i];
		if(hc.fieldname == fieldname) {
			if(!hc.template) {
				this.make_template(hc);
			}
			return hc.template;
		}
	}
	return {} // did not find, return empty object not to throw error in get_query
}


_f.grid_date_cell = '';
_f.grid_refresh_date = function() {
	_f.grid_date_cell.grid.set_cell_value(_f.grid_date_cell);
}
_f.grid_refresh_field = function(temp, input) {
	if($(input).val() != _f.get_value(temp.doctype, temp.docname, temp.df.fieldname))
		$(input).trigger('change');
}

_f.Grid.prototype.remove_template = function(cell) {
	var hc = this.head_row.cells[cell.cellIndex];

	if(!hc.template)return;
	if(!hc.template.activated)return;

	/*if(hc.template.df.fieldtype=='Date') {
		// for calendar popup. the value will come after this
		_f.grid_date_cell = cell;
		setTimeout('_f.grid_refresh_date()', 100);
	} else {
		var input = hc.template.txt || hc.template.input;
		_f.grid_refresh_field(hc.template, input)
	}*/

	if(hc.template && hc.template.wrapper.parentNode)
		cell.div.removeChild(hc.template.wrapper);
	this.set_cell_value(cell);
	hc.template.activated=0;
}

_f.Grid.prototype.notify_keypress = function(e, keycode) {
	if(keycode>=37 && keycode<=40 && e.shiftKey) {
		if(text_dialog && text_dialog.display) {
			return;
		}
	} else 
		return;

	if(!_f.cur_grid_cell) return;
	if(_f.cur_grid_cell.grid != this) return;
	var ri = _f.cur_grid_cell.row.rowIndex;
	var ci = _f.cur_grid_cell.cellIndex;
	switch(keycode) {
		case 38: // up
			if (ri > 0) {
				this.cell_select('', ri - 1, ci);
			} break;
		case 40: // down
			if (ri < (this.tab.rows.length - 1)) {
				this.cell_select('', ri + 1, ci);
			} break;
		case 39: // right
			if (ci < (this.head_row.cells.length - 1)) {
				this.cell_select('', ri, ci + 1);
			} break;
		case 37: // left
			if (ci > 1) {
				this.cell_select('', ri, ci - 1);
			} break;
	}
}

_f.Grid.prototype.make_template = function(hc) {
	hc.template = make_field(get_field(hc.doctype, hc.fieldname), hc.doctype, '', this.field.frm, true);
	hc.template.grid = this;
}

_f.Grid.prototype.append_rows = function(n) { 
	for(var i=0;i<n;i++) this.append_row(); 
}

_f.Grid.prototype.truncate_rows = function(n) { 
	for(var i=0;i<n;i++) this.tab.deleteRow(this.tab.rows.length-1); 
}

_f.Grid.prototype.set_data = function(data) {

	// deselect if not done yet
	this.cell_deselect();

	// set table widths
	this.reset_table_width();

	// append if reqd
	if(data.length > this.tab.rows.length)
		this.append_rows(data.length - this.tab.rows.length);

	// truncate if reqd
	if(data.length < this.tab.rows.length)
		this.truncate_rows(this.tab.rows.length - data.length);

	// set data
	for(var ridx=0;ridx<data.length;ridx++) {
		this.refresh_row(ridx, data[ridx]);
	}
	
	if(this.can_add_rows && this.make_newrow) {
		this.make_newrow();
	}
		
	if(this.wrapper.onscroll)this.wrapper.onscroll();
}

_f.Grid.prototype.set_ht = function() {
	var max_ht = cint(0.37 * screen.width);
	var ht = $(this.tab).height() + $(this.head_tab).height() + 30;

	if(ht < 100)
		ht=100; 
		
	if(ht > max_ht) ht = max_ht;

	ht += 4;
	$y(this.wrapper,{height:ht+'px'});	
}

_f.Grid.prototype.refresh_row = function(ridx, docname) {
	var row = this.tab.rows[ridx];
	row.docname = docname;
	row.is_newrow = false;
		
	for(var cidx=0; cidx<row.cells.length; cidx++) {
		this.set_cell_value(row.cells[cidx]);
	}
}
