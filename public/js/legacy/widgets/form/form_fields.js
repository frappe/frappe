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

//
// Form Input
// ======================================================================================

_f.ColumnBreak = function() {
	this.set_input = function() { };
}

_f.ColumnBreak.prototype.make_body = function() {
	this.cell = this.frm.layout.addcell(this.df.width);
	$y(this.cell.wrapper, {padding: '8px'});
	_f.cur_col_break_width = this.df.width;

	var fn = this.df.fieldname || this.df.label;
	// header
	if(this.df&&this.df.label){
		this.label = $a(this.cell.wrapper, 'h4', '', '', wn._(this.df.label));
	}
}

_f.ColumnBreak.prototype.refresh = function(layout) {
	//if(!this.cell)return; // no perm
	
	var hidden = 0;
	// we generate column breaks, but hide it based on perms/hidden value
	if((!this.perm[this.df.permlevel]) || (!this.perm[this.df.permlevel][READ]) || 
		this.df.hidden) {
		// do not display, as no permission
		hidden = 1;
	}
	
	// hidden
	if(this.set_hidden!=hidden) {
		if(hidden)
			this.cell.hide();
		else
			this.cell.show();
		this.set_hidden = hidden;
	}
}

// ======================================================================================

_f.SectionBreak = function() {
	this.fields = [];
	this.set_input = function() { };
	this.make_row = function() {
		this.row = this.df.label ? this.frm.layout.addrow() : this.frm.layout.addsubrow();		
	}
}

_f.SectionBreak.prototype.make_body = function() {
	var me = this;
	this.make_row();

	if(this.df.label) {
		if(!this.df.description) 
			this.df.description = '';
		
		this.df._label = wn._(this.df.label);
		this.df._description = wn._(this.df.description);
		
		$(this.row.main_head).html(repl('<div class="form-section-head">\
				<h3 class="head">%(_label)s</h3>\
				<div class="help small" \
					style="margin-top: 4px; margin-bottom: 8px;">%(_description)s</div>\
			</div>', this.df));
	} else {
		// simple
		$(this.wrapper).html('<div class="form-section-head"></div>');
	}

	// collapse section
	this.section_collapse = function() {
		$(me.row.main_head).find('.head')
			.html('<i class="icon-chevron-right"></i> \
				<a href="#" onclick="return false;">Show "' + me.df.label + '"</a>');
		$(me.row.main_body).toggle(false);
		
	}
	
	// expand section
	this.section_expand = function(no_animation) {
		$(me.row.main_head).find('.head')
			.html('<h3><i class="icon-chevron-down" style="vertical-align: middle; margin-bottom: 2px"></i> ' 
				+ me.df.label + '</h3>');
		if(no_animation)
			$(me.row.main_body).toggle(true);
		else
			$(me.row.main_body).slideDown();
	}
}

_f.SectionBreak.prototype.refresh = function(from_form) {
	var hidden = 0;
	// we generate section breaks, but hide it based on perms/hidden value
	if((!this.perm[this.df.permlevel]) || (!this.perm[this.df.permlevel][READ]) || this.df.hidden) {
		// no display
		hidden = 1;
	}

	if(hidden) {
		if(this.row)this.row.hide();
	} else {
		if(this.row)this.row.show();
	}
}

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
		this.grid = new _f.FormGrid(this);
		if(this.frm)this.frm.grids[this.frm.grids.length] = this;
		this.grid.make_buttons();
		
		// description
		if(this.df.description) {
			this.desc_area = $a(this.wrapper, 'div', 'help small', 
				{marginBottom:'9px', marginTop:'0px'}, this.df.description)
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
	
	if(st=='Write' || st=="Read") {
		$(this.wrapper).toggle(true);
		this.grid.show();
	} else {
		$(this.wrapper).toggle(false);
		this.grid.hide();
	}

	this.grid.refresh();
}

_f.TableField.prototype.set = function(v) { }; // nothing
_f.TableField.prototype.set_input = function(v) { }; // nothing


_f.CodeField = function() { };
_f.CodeField.prototype = new Field();
_f.CodeField.prototype.make_input = function() {
	var me = this;

	this.label_span.innerHTML = this.df.label;

	if(this.df.fieldtype=='Text Editor') {
		$(this.input_area).css({"min-height":"360px"});
		this.input = $a(this.input_area, 'text_area', '', {fontSize:'12px'});
		this.myid = wn.dom.set_unique_id(this.input);

		// setup tiny mce
		$(me.input).tinymce({
			// Location of TinyMCE script
			script_url : 'lib/js/lib/tiny_mce_3.5.7/tiny_mce.js',

			// General options
			theme : "advanced",
			plugins : "style,inlinepopups,table,advimage",
			extended_valid_elements: "script|embed",
			
			// w/h
			width: '100%',
			height: '360px',
	
			// buttons
			theme_advanced_buttons1 : "bold,italic,underline,hr,|,justifyleft,justifycenter,|,formatselect,fontsizeselect,|,bullist,numlist,|,image,|,outdent,indent,|,link,|,forecolor,backcolor,|,code",
			theme_advanced_buttons2 : "",
			theme_advanced_buttons3 : "",

			theme_advanced_toolbar_location : "top",
			theme_advanced_toolbar_align : "left",
			theme_advanced_statusbar_location: "none",
			theme_advanced_path: false,

			valid_elements : "*[*]",

			content_css: "lib/js/lib/tiny_mce_3.5.7/custom_content.css?q=1",

			oninit: function() { me.init_editor(); },
			setup: function(ed) {
				ed.onChange.add(function(ed, l) {
					me.set(l.content);
					me.run_trigger();
				});
			}
		});

		this.input.set_input = function(v) {
			if(me.editor) {
				me.editor.setContent(v==null ? "" : v);
			} else {
				$(me.input).val(v);
			}
		}
		this.get_value = function() {
			return me.editor && me.editor.getContent(); // tinyMCE
		}	

	} else {
		// setup ace
		wn.require('lib/js/lib/ace/ace.js');
		
		$(this.input_area).css('border','1px solid #aaa');
		this.pre = $("<pre style='position: relative; height: 400px; \
			width: 100%; padding: 0px; border-radius: 0px;\
			margin: 0px; background-color: #fff;'>").appendTo(this.input_area).get(0);

		this.input = {};
		this.myid = wn.dom.set_unique_id(this.pre);
		this.editor = ace.edit(this.myid);

		if(me.df.options=='Markdown' || me.df.options=='HTML') {
			wn.require('lib/js/lib/ace/mode-html.js');	
			var HTMLMode = require("ace/mode/html").Mode;
		    me.editor.getSession().setMode(new HTMLMode());
		}

		else if(me.df.options=='Javascript') {
			wn.require('lib/js/lib/ace/mode-javascript.js');	
			var JavascriptMode = require("ace/mode/javascript").Mode;
		    me.editor.getSession().setMode(new JavascriptMode());
		}

		else if(me.df.options=='Python') {
			wn.require('lib/js/lib/ace/mode-python.js');	
			var PythonMode = require("ace/mode/python").Mode;
		    me.editor.getSession().setMode(new PythonMode());
		}
		
		this.input.set_input = function(v) {
			// during field refresh in run trigger, set_input is called
			// if called during on_change, setting doesn't make sense
			// and causes cursor to shift back to first position
			if(me.changing_value) return;
			
			me.setting_value = true;
			me.editor.getSession().setValue(v==null ? "" : v);
			me.setting_value = false;
		}
		
		this.get_value = function() {
			return me.editor.getSession().getValue(); // tinyMCE
		}
		$(cur_frm.wrapper).bind('render_complete', function() {
			me.editor.resize();
			me.editor.getSession().on('change', function() {
				if(me.setting_value) return;
				var val = me.get_value();
				if(locals[cur_frm.doctype][cur_frm.docname][me.df.fieldname] != val) {
					me.set(me.get_value());

					me.changing_value = true;
					me.run_trigger();
					me.changing_value = false;
				}
			})
		});
		this.onrefresh = function() {
			me.editor && me.editor.resize();
		}
	}
	
}

_f.CodeField.prototype.init_editor = function() {
	// attach onchange methods
	var me = this;
	this.editor = tinymce.get(this.myid);
	this.editor.onKeyUp.add(function(ed, e) { 
		me.set(ed.getContent()); 
	});
	this.editor.onPaste.add(function(ed, e) { 
		me.set(ed.getContent());
	});
	this.editor.onSetContent.add(function(ed, e) { 
		me.set(ed.getContent()); 
	});
	
	// reset content
	var c = locals[cur_frm.doctype][cur_frm.docname][this.df.fieldname];
	if(cur_frm && c) {
		this.editor.setContent(c);
	}
}

_f.CodeField.prototype.set_disp = function(val) {
	$y(this.disp_area, {width:'90%'})
	if(this.df.fieldtype=='Text Editor') {
		this.disp_area.innerHTML = val;
	} else {
		this.disp_area.innerHTML = '<textarea class="code_text" readonly=1>'+val+'</textarea>';
	}
}

// ======================================================================================

