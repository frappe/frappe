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

// Image field definition
// ======================================================================================

_f.ImageField = function() { this.images = {}; }
_f.ImageField.prototype = new Field();
_f.ImageField.prototype.onrefresh = function() { 
	$(this.label_span).toggle(false);
	$(this.wrapper).find("img").remove();
	if(this.df.options && this.frm.doc[this.df.options]) {
		$("<img src='"+wn.utils.get_file_link(this.frm.doc[this.df.options])+"' style='max-width: 70%;'>")
			.appendTo($(this.wrapper).empty());
	} else {
		$("<div class='missing-image'><i class='icon-camera'></i></div>")
			.appendTo($(this.wrapper).empty())
	}
}

_f.ImageField.prototype.set_disp = function (val) { }
_f.ImageField.prototype.set = function (val) { }

// Table
// ======================================================================================

_f.TableField = function() { };
_f.TableField.prototype = new Field();
_f.TableField.prototype.with_label = 0;
_f.TableField.prototype.make_body = function() {
	if(this.perm[this.df.permlevel] && this.perm[this.df.permlevel][READ]) {
		this.wrapper = $("<div>").appendTo(this.parent).get(0);
		this.grid = new wn.ui.form.Grid({
			frm: this.frm,
			df: this.df,
			perm: this.perm,
			parent: $("<div>").appendTo(this.wrapper)
		})
		if(this.frm)
			this.frm.grids[this.frm.grids.length] = this;

		// description
		if(this.df.description) {
			$('<p class="text-muted small">' + this.df.description + '</p>')
				.appendTo(this.wrapper);
		}
	}
}

_f.TableField.prototype.refresh = function() {
	if(!this.grid)return;
	
	// hide / show grid
	var st = this.get_status();

	if(!this.df['default']) 
		this.df['default']='';

	this.grid.can_add_rows = false;
	this.grid.can_edit = false;
	
	if(st=='Write') {
		this.grid.can_edit = true;
		if(this.df['default'].toLowerCase()!='no toolbar')
			this.grid.can_add_rows = true;
		
		if(this.df['default'].toLowerCase()=='no add rows') {
			this.grid.can_add_rows = false;
		}
	}
	
	$(this.wrapper).toggle(st=='Write' || st=="Read");
	this.grid.refresh();
}

_f.TableField.prototype.set = function(v) { }; // nothing
_f.TableField.prototype.set_input = function(v) { }; // nothing


_f.CodeField = function() { };
_f.CodeField.prototype = new Field();
_f.CodeField.prototype.make_input = function() {
	var me = this;

	this.label_span.innerHTML = this.df.label;

	$(this.input_area).css({"min-height":"360px"});

	if(this.df.fieldtype=='Text Editor') {
		this.input = new wn.editors.BootstrapWYSIWYG({
			parent: this.input_area,
			change: function(value) {
				me.set_value_and_run_trigger(value);
			},
			field: this
		});
	} else {
		this.input = new wn.editors.ACE({
			parent: this.input_area,
			change: function(value) {
				me.set_value_and_run_trigger(value);
			},
			field: this
		});
	}
	this.get_value = function() {
		return this.input.get_value();
	}
}

_f.CodeField.prototype.set_value_and_run_trigger = function(value) {
	if(locals[cur_frm.doctype][cur_frm.docname][this.df.fieldname] != value) {
		this.set(value);
		this.changing_value = true;
		this.run_trigger();
		this.changing_value = false;
	}
}

_f.CodeField.prototype.set_disp = function(val) {
	$y(this.disp_area, {width:'90%'})
	if(this.df.fieldtype=='Text Editor') {
		this.disp_area.innerHTML = val;
	} else {
		this.disp_area.innerHTML = '<textarea class="code_text" readonly=1>'
			+val+'</textarea>';
	}
}

// ======================================================================================

