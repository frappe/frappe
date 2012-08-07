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

	var fn = this.df.fieldname?this.df.fieldname:this.df.label;
	// header
	if(this.df&&this.df.label){
		this.label = $a(this.cell.wrapper, 'h4', '', '', this.df.label);
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
		$(this.row.main_head).html(repl('<div class="form-section-head">\
				<h3 class="head">%(label)s</h3>\
				<div class="help small" \
					style="margin-top: 4px; margin-bottom: 8px;">%(description)s</div>\
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

_f.SectionBreak.prototype.has_data = function() {
	// return true if
	// 1. any field in the section is mandatory & not set as default
	// 2. any field in the section has data that is not default
	// 3. if table, table has rows
	
	var me = this;
	for(var i in me.fields) {
		var f = me.fields[i];
		var v = f.get_value ? f.get_value() : null;
		
		// value that is not default
		defaultval = f.df['default'] || sys_defaults[f.fieldname] || user_defaults[f.fieldname];
		if(v && v != defaultval) {
			return true;
		}
		
		// unfilled mandatory field
		if(f.df.reqd && !v) {
			return true;
		}
		
		// filled table
		if(f.df.fieldtype=='Table') {
			if(f.grid.get_children().length || f.df.reqd) {
				return true;
			}
		}
	}
	return false;
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
_f.ImageField.prototype.onmake = function() {
	this.no_img = $a(this.wrapper, 'div','no_img');
	this.no_img.innerHTML = "No Image";
	$dh(this.no_img);
}

_f.ImageField.prototype.get_image_src = function(doc) {
	if(doc.file_list) {
		file = doc.file_list.split(',');
		// if image
		extn = file[0].split('.');
		extn = extn[extn.length - 1].toLowerCase();
		var img_extn_list = ['gif', 'jpg', 'bmp', 'jpeg', 'jp2', 'cgm',  'ief', 'jpm', 'jpx', 'png', 'tiff', 'jpe', 'tif'];

		if(in_list(img_extn_list, extn)) {
			var src = wn.request.url + "?cmd=downloadfile&file_id="+file[1];
		}
	} else {
		var src = "";
	}
	return src;
}
_f.ImageField.prototype.onrefresh = function() { 
	var me = this;
	if(!this.images[this.docname]) this.images[this.docname] = $a(this.wrapper, 'img');
	else $di(this.images[this.docname]);
	
	var img = this.images[this.docname]
	
	// hide all other
	for(var dn in this.images) if(dn!=this.docname)$dh(this.images[dn]);

	var doc = locals[this.frm.doctype][this.frm.docname];
	
	if(!this.df.options) var src = this.get_image_src(doc);
	else var src = wn.request.url + '?cmd=get_file&fname='+this.df.options+"&__account="+account_id + (__sid150 ? ("&sid150="+__sid150) : '');

	
	if(src) {
		$dh(this.no_img);
		if(img.getAttribute('src')!=src) img.setAttribute('src',src);
		canvas = this.wrapper;
		canvas.img = this.images[this.docname];
		canvas.style.overflow = "auto";
		$w(canvas, "100%");
	
		if(!this.col_break_width)this.col_break_width = '100%';
		var allow_width = cint(1000 * (cint(this.col_break_width)-10) / 100);

		if((!img.naturalWidth) || cint(img.naturalWidth)>allow_width)
			$w(img, allow_width + 'px');

	} else {
		$ds(this.no_img);
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
		this.grid = new _f.FormGrid(this);
		if(this.frm)this.frm.grids[this.frm.grids.length] = this;
		this.grid.make_buttons();
		
		// description
		if(this.df.description) {
			this.desc_area = $a(this.parent, 'div', 'help small', 
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
	this.grid.can_edit = false
	if(st=='Write') {
		if(cur_frm.editable && this.perm[this.df.permlevel] && this.perm[this.df.permlevel][WRITE]) {
			this.grid.can_edit = true;
			if(this.df['default'].toLowerCase()!='no toolbar')
				this.grid.can_add_rows = true;
		}
		
		// submitted or cancelled
		if(cur_frm.editable && cur_frm.doc.docstatus > 0) {
			if(this.df.allow_on_submit && cur_frm.doc.docstatus==1) {
				this.grid.can_edit = true;
				if(this.df['default'].toLowerCase()=='no toolbar') {
					this.grid.can_add_rows = false;
				} else {
					this.grid.can_add_rows = true;
				}
			} else {
				this.grid.can_add_rows = false;
				this.grid.can_edit = false;
			}
		}

		if(this.df['default'].toLowerCase()=='no add rows') {
			this.grid.can_add_rows = false;
		}
	}
	
	//if(this.old_status!=st) {
	if(st=='Write') {
		// nothing
		this.grid.show();
	} else if(st=='Read') {
		this.grid.show();
	} else {
		this.grid.hide();
	}
	//	this.old_status = st; // save this if next time
	//}

	this.grid.refresh();
}

_f.TableField.prototype.set = function(v) { }; // nothing
_f.TableField.prototype.set_input = function(v) { }; // nothing

// ==============================================================


_f.CodeField = function() { };
_f.CodeField.prototype = new Field();
_f.CodeField.prototype.make_input = function() {
	var me = this;

	this.label_span.innerHTML = this.df.label;

	if(this.df.fieldtype=='Text Editor') {
		this.input = $a(this.input_area, 'text_area', '', {fontSize:'12px'});
		this.myid = wn.dom.set_unique_id(this.input);

		// setup tiny mce
		$(me.input).tinymce({
			// Location of TinyMCE script
			script_url : 'js/lib/tiny_mce_33/tiny_mce.js',

			// General options
			theme : "advanced",
			plugins : "style,inlinepopups,table",
			extended_valid_elements: "div[id|dir|class|align|style]",
			
			// w/h
			width: '100%',
			height: '360px',
	
			// buttons
			theme_advanced_buttons1 : "bold,italic,underline,strikethrough,hr,|,justifyleft,justifycenter,justifyright,|,formatselect,fontselect,fontsizeselect",
			theme_advanced_buttons2 : "bullist,numlist,|,outdent,indent,|,undo,redo,|,link,unlink,code,|,forecolor,backcolor,|,tablecontrols",
			theme_advanced_buttons3 : "",

			theme_advanced_toolbar_location : "top",
			theme_advanced_toolbar_align : "left",

			content_css: "js/lib/tiny_mce_33/custom_content.css?q=1",

			oninit: function() { me.init_editor(); }
		});

		this.input.set_input = function(v) {
			if(me.editor) {
				me.editor.setContent(v);				
			} else {
				$(me.input).val(v);
			}
		}
		this.input.onchange = function() {
			me.set(me.editor.getContent());
			me.run_trigger();
		}
		this.get_value = function() {
			return me.editor.getContent(); // tinyMCE
		}	

	} else {
		// setup ace
		//this.input = $a(this.input_area, 'div', '', {position:'relative', width: '90%', height:'300px'});

		wn.require('js/lib/ace/ace.js');
		//wn.require('js/lib/ace/theme-twilight.js');
		
		$(this.input_area).css('border','1px solid #aaa');
		this.pre = $a(this.input_area, 'pre', '', {
			position:'relative', height: '400px', width:'100%'
		});
		this.input = {};
		this.myid = wn.dom.set_unique_id(this.pre);
		this.editor = ace.edit(this.myid);
		//this.editor.getSession().setUseWrapMode(true);
	    //this.editor.setTheme("ace/theme/twilight");

		if(me.df.options=='Markdown' || me.df.options=='HTML') {
			wn.require('js/lib/ace/mode-html.js');	
			var HTMLMode = require("ace/mode/html").Mode;
		    me.editor.getSession().setMode(new HTMLMode());
		}

		else if(me.df.options=='Javascript') {
			wn.require('js/lib/ace/mode-javascript.js');	
			var JavascriptMode = require("ace/mode/javascript").Mode;
		    me.editor.getSession().setMode(new JavascriptMode());
		}

		else if(me.df.options=='Python') {
			wn.require('js/lib/ace/mode-python.js');	
			var PythonMode = require("ace/mode/python").Mode;
		    me.editor.getSession().setMode(new PythonMode());
		}
		
		this.input.set_input = function(v) {
			me.setting_value = true;
			me.editor.getSession().setValue(v);
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
					me.run_trigger();
				}
			})
		});
		
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

