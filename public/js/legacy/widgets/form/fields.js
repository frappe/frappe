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

// fields.js
//
// Fields are divided into 2 types
// 1. Standard fields are loaded with the libarary
// 2. Special fields are loaded with form.compressed.js
//
//
// + wrapper
// 		+ input_area
//		+ display_area
// ======================================================================================
var no_value_fields = ['Section Break', 'Column Break', 'HTML', 'Table', 'FlexTable', 'Button', 'Image'];
var codeid=0; var code_editors={};

function Field() {	
	this.with_label = 1;
}

Field.prototype.make_body = function() { 	
	// parent element
	this.$wrapper = $('<div class="control-group" style="max-width: 600px;">\
		<label class="control-label"></label>\
		<div class="controls">\
			<div class="control-input"></div>\
			<div class="control-value"></div>\
		</div>\
	</div>').appendTo(this.parent);
	this.wrapper = this.$wrapper.get(0);
	
	this.label_area = this.label_span = this.$wrapper.find(".control-label").get(0);
	this.input_area = this.$wrapper.find(".control-input").get(0);
	this.disp_area = this.$wrapper.find(".control-value").get(0);

	// set description
	this.set_description();	

	if(this.onmake)this.onmake();
}


Field.prototype.set_max_width = function() {
	var no_max = ['Code', 'Text Editor', 'Text', 'Small Text', 'Table', 'HTML']
	if(this.wrapper && this.layout_cell && this.layout_cell.parentNode.cells 
		&& this.layout_cell.parentNode.cells.length==1 && !in_list(no_max, this.df.fieldtype)) {
			$y(this.wrapper, {paddingRight:'50%'});
	}
}

Field.prototype.set_label = function(label) {
	this.label_span.innerHTML = wn._(label || this.df.label);
}

Field.prototype.set_description = function(txt) {
	if(txt) {
		if(!this.$wrapper.find(".help-box").length) {
			$('<p class="help-box small"></p>').appendTo(this.input_area);
		}
		this.$wrapper.find(".help-box").html(txt);
	} else {
		this.$wrapper.find(".help-box").empty().toggle(false);
	}
}

Field.prototype.get_status = function(explain) {
	if(!this.doctype) 
		return "Write";
	return wn.perm.get_field_display_status(this.df, 
		locals[this.doctype][this.docname], this.perm, explain)
}

Field.prototype.refresh_mandatory = function() { 
	if(this.in_filter)return;
	//this.$wrapper.toggleClass("has-warning", cint(this.df.reqd) ? true : false);
	this.refresh_label_icon()
}

Field.prototype.refresh_display = function() {
	// from permission
	if(!this.current_status || this.current_status!=this.disp_status) { // status changed
		if(this.disp_status=='Write') { // write
			if(this.make_input&&(!this.input)) { // make input if reqd
				this.make_input();
				if(this.txt || this.input)
					$(this.txt || this.input).addClass("mousetrap");
				if(this.onmake_input) this.onmake_input();				
			}
			
			if(this.show) this.show()
			else { $ds(this.wrapper); }
			
			// input or content
			if(this.input) { // if there, show it!
				$ds(this.input_area);
				$dh(this.disp_area);
				if(this.input.refresh)
					this.input.refresh();
			} else { // no widget
				$dh(this.input_area);
				$ds(this.disp_area);
			}
		} else if(this.disp_status=='Read') { 
			
			// read
			if(this.show) this.show()
			else { $ds(this.wrapper); }

			$dh(this.input_area);
			$ds(this.disp_area);

		} else { 
			
			// None - hide all
			if(this.hide) this.hide();
			else $dh(this.wrapper);
		}
		this.current_status = this.disp_status;
	}
}

Field.prototype.refresh = function() {
	// get status
	this.disp_status = this.get_status();

	// if there is a special refresh in case of table, then this is not valid
	if(this.in_grid 
		&& this.table_refresh 
			&& this.disp_status == 'Write') 
				{ this.table_refresh(); return; }

	this.set_label();
	this.refresh_display();
			
	if(this.input) {
		if(this.input.refresh) this.input.refresh(this.df);
	}

	// further refresh	
	if(this.onrefresh) 
		this.onrefresh(); // called by various fields

	if(this.wrapper) {
		this.wrapper.fieldobj = this;
		$(this.wrapper).trigger('refresh');		
	}
	
	if(!this.not_in_form)
		this.set_input(_f.get_value(this.doctype,this.docname,this.df.fieldname));

	this.refresh_mandatory();	
	this.set_max_width();

}

Field.prototype.refresh_label_icon = function() {	
	// mandatory
	var to_update = false;
	if(this.df.reqd && this.get_value && is_null(this.get_value())) 
		to_update = true;
		
	this.$wrapper.toggleClass("has-error", to_update);
}

Field.prototype.set = function(val) {
	// not in form
	if(this.not_in_form)
		return;
			
	if((!this.docname) && this.grid) {
		this.docname = this.grid.add_newrow(); // new row
	}
	
	if(this.validate)
		val = this.validate(val);
		
	cur_frm.set_value_in_locals(this.doctype, this.docname, 
		this.df.fieldname, val);
	this.value = val; // for return
}

Field.prototype.set_input = function(val) {
	this.value = val;
	if(this.input && this.input.set_input) {
		this.input.set_input(val); // in widget
	}
	var disp_val = val;
	if(val==null) 
		disp_val = ''; 
	this.set_disp(disp_val); // text
}

Field.prototype.run_trigger = function() {
	// update mandatory icon
	this.refresh_label_icon();

	if(this.not_in_form) {
		return;
	}

	if(cur_frm.cscript[this.df.fieldname])
		cur_frm.runclientscript(this.df.fieldname, this.doctype, this.docname);

	cur_frm.refresh_dependency();
}

Field.prototype.set_disp_html = function(t) {
	if(this.disp_area){
		$(this.disp_area).addClass('disp-area');

		this.disp_area.innerHTML = (t==null ? '' : t);
		if(!t) $(this.disp_area).addClass('disp-area-no-val');
	}
}

Field.prototype.set_disp = function(val) { 
	this.set_disp_html(val);
}

Field.prototype.get_input = function() { 
	return this.txt || this.input;
}


function DataField() { } DataField.prototype = new Field();
DataField.prototype.make_input = function() {
	var me = this;
	this.input = $a_input(this.input_area, this.df.fieldtype=='Password' ? 'password' : 'text');
	
	if(this.df.placeholder) $(this.input).attr("placeholder", this.df.placeholder);
	
	this.get_value= function() {
		var v = this.input.value;
		if(this.validate)
			v = this.validate(v);
		return v;
	}

	this.input.name = this.df.fieldname;
	
	$(this.input).blur(function() {
		me.set_value(me.get_value ? me.get_value() : $(this).val());
	});
	
	this.set_value = function(val) {
		if(!me.last_value) me.last_value=undefined;
		
		if(me.validate) {
			val = me.validate(val);
			if(me.last_value === val) return;
			me.input.value = (val==undefined) ? '' : val;
		} else if(me.last_value === val) { return; }

		me.set(val);
		if(me.format_input)
			me.format_input();
			
		if(in_list(['Currency','Float','Int'], me.df.fieldtype)) {
			if(flt(me.last_value)==flt(val)) {
				me.last_value = val;
				return; // do not run trigger
			}
		}
		me.last_value = val;
		me.run_trigger();
	}
	this.input.set_input = function(val) { 
		if(val==null)val='';
		me.input.value = val; 
		if(me.format_input)me.format_input();
	}
}
DataField.prototype.validate = function(v) {
	if(this.df.options == 'Phone') {
		if(v+''=='')return '';
		v1 = ''
		// phone may start with + and must only have numbers later, '-' and ' ' are stripped
		v = v.replace(/ /g, '').replace(/-/g, '').replace(/\(/g, '').replace(/\)/g, '');

		// allow initial +,0,00
		if(v && v.substr(0,1)=='+') {
			v1 = '+'; v = v.substr(1);
		}
		if(v && v.substr(0,2)=='00') {
			v1 += '00'; v = v.substr(2);
		} 
		if(v && v.substr(0,1)=='0') {
			v1 += '0'; v = v.substr(1);
		}
		v1 += cint(v) + '';
		return v1;
	} else if(this.df.options == 'Email') {
		if(v+''=='')return '';
		if(!validate_email(v)) {
			msgprint(this.df.label + ': ' + v + ' is not a valid email id');
			return '';
		} else
			return v;
	} else {
		return v;	
	}	
}

// ======================================================================================

function HTMLField() { 
	var me = this;
	this.make_body = function() {
		me.wrapper = $("<div>").appendTo(me.parent);
	}
	this.set_disp = function(val) {
		if(val)
			$(me.wrapper).html(val);
	}
	this.set_input = function(val) {
		me.set_disp(val);
	}
	this.refresh = function() {
		if(me.df.options)
			me.set_disp(me.df.options);
	}
} 

// reference when a new record is created via link
function LinkField() { } LinkField.prototype = new Field();
LinkField.prototype.make_input = function() { 
	var me = this;
	
	if(me.df.no_buttons) {
		this.txt = $("<input type='text'>")
			.appendTo(this.input_area).get(0);
		this.input = this.txt;	
	} else {
		me.input = me.input_area;
		me.input_group = $('<div class="input-group link-field">').appendTo(me.input_area);
			
		me.txt = $('<input type="text" style="margin-right: 0px;">')
			.appendTo(me.input_group).get(0);
			
		me.input_group_btn = $('<div class="input-group-btn">').appendTo(me.input_group);
				
		me.btn = $('<button class="btn" title="'+wn._('Search Link')+'">\
			<i class="icon-search"></i></button>').appendTo(me.input_group_btn).get(0);
		me.btn1 = $('<button class="btn" title="'+wn._('Open Link')+'">\
			<i class="icon-play"></i></button>').appendTo(me.input_group_btn).get(0);
		me.btn2 = $('<button class="btn" title="'+wn._('Make New')+'">\
			<i class="icon-plus"></i></button>').appendTo(me.input_group_btn).get(0);	

		me.txt.name = me.df.fieldname;
		me.setdisabled = function(tf) { me.txt.disabled = tf; }
			
		// setup buttons
		me.setup_buttons();
	}
	
	me.onrefresh = function() {
		var can_create = in_list(wn.boot.profile.can_create, me.df.options);
		var can_read = in_list(wn.boot.profile.can_read, me.df.options);
		if(!can_create) $(this.btn2).remove();
		if(!can_read) $(this.btn1).remove();
	}

	me.onrefresh();

	me.txt.field_object = this;
	// set onchange triggers

	me.input.set_input = function(val) {
		if(val==undefined)val='';
		me.txt.value = val;
	}

	me.get_value = function() { return me.txt.value; }
	
	// increasing zindex of input to increase zindex of autosuggest
	// because of the increase in zindex of dialog_wrapper
	if(cur_dialog || me.dialog_wrapper) {
		var $dialog_wrapper = $(cur_dialog ? cur_dialog.wrapper : me.dialog_wrapper)
		var zindex = cint($dialog_wrapper.css("z-index"));
		$(me.txt).css({"z-index": (zindex >= 10 ? zindex : 10) + 1});
	}
	
	$(me.txt).autocomplete({
		source: function(request, response) {
			var args = {
				'txt': request.term, 
				'dt': me.df.options,
			};
			
			var q = me.get_custom_query();
			if (typeof(q)==="string") {
				args.query = q;
			} else if($.isPlainObject(q)) {
				if(q.filters) {
					$.each(q.filters, function(key, value) {
						q.filters[key] = value===undefined ? null : value;
					});
				}
				$.extend(args, q);
			}
			
			wn.call({
				method:'webnotes.widgets.search.search_link',
				args: args,
				callback: function(r) {
					response(r.results);
				},
			});
		},
		select: function(event, ui) {
			me.set_input_value(ui.item.value);
		}
	}).data('autocomplete')._renderItem = function(ul, item) {
		return $('<li></li>')
			.data('item.autocomplete', item)
			.append(repl('<a><span style="font-weight: bold;">%(label)s</span><br>\
				<span style="font-size:10px;">%(info)s</span></a>',
				item))
			.appendTo(ul);
	};
	
	$(this.txt).change(function() {
		var val = $(this).val();//me.get_value();

		me.set_input_value_executed = false;
		
		if(!val) {
			if(selector && selector.display) 
				return;
			me.set_input_value('');			
		} else {
			// SetTimeout hack! if in put is set via autocomplete, do not validate twice
			setTimeout(function() {
				if (!me.set_input_value_executed) {
					me.set_input_value(val);
				}
			}, 1000);
		}
	})
}

LinkField.prototype.get_custom_query = function() {
	this.set_get_query();
	if(this.get_query) {
		if(cur_frm)
			var doc = locals[cur_frm.doctype][cur_frm.docname];
		return this.get_query(doc, this.doctype, this.docname);
	}
}

LinkField.prototype.setup_buttons = function() { 
	var me = this;
	
	// magnifier - search
	me.btn.onclick = function() {
		selector.set(me, me.df.options, me.df.label);
		selector.show(me.txt);
	}

	// open
	if(me.btn1)me.btn1.onclick = function() {
		if(me.txt.value && me.df.options) { loaddoc(me.df.options, me.txt.value); }
	}	
	// add button - for inline creation of records
	me.can_create = 0;
	if((!me.not_in_form) && in_list(profile.can_create, me.df.options)) {
		me.can_create = 1;
		me.btn2.onclick = function() { 
			var on_save_callback = function(new_rec) {
				if(new_rec) {
					var d = _f.calling_doc_stack.pop(); // patch for composites
					
					locals[d[0]][d[1]][me.df.fieldname] = new_rec;
					me.refresh();
					
					if(me.grid)me.grid.refresh();
					
					// call script
					me.run_trigger();					
				}
			}
			_f.calling_doc_stack.push([me.doctype, me.docname]);
			new_doc(me.df.options); 
		}
	} else {
		$(me.btn2).remove();
	}
}

LinkField.prototype.set_input_value = function(val) {
	var me = this;
	
	// SetTimeout hack! if in put is set via autocomplete, do not validate twice
	me.set_input_value_executed = true;

	var from_selector = false;
	if(selector && selector.display) from_selector = true;
		
	// refresh mandatory style
	me.refresh_label_icon();
	
	// not in form, do nothing
	if(me.not_in_form) {
		$(this.txt).val(val);
		return;
	}
	
	// same value, do nothing
	if(cur_frm) {
		if(val == locals[me.doctype][me.docname][me.df.fieldname]) { 
			//me.set(val); // one more time, grid bug?
			me.run_trigger(); // wanted - called as refresh?
			return; 
		}
	}
	
	// set in locals
	me.set(val);
	
	// deselect cell if in grid
	if(_f.cur_grid_cell)
		_f.cur_grid_cell.grid.cell_deselect();
	
	if(val) {
		// validate only if val is not empty
		me.validate_link(val, from_selector);
	} else {
		// run trigger if value is cleared
		me.run_trigger();
	}
}

LinkField.prototype.validate_link = function(val, from_selector) {
	// validate the value just entered
	var me = this;

	if(this.df.options=="[Select]") {
		$(me.txt).val(val);
		me.run_trigger();
		return;		
	}

	var fetch = '';
	if(cur_frm.fetch_dict[me.df.fieldname])
		fetch = cur_frm.fetch_dict[me.df.fieldname].columns.join(', ');
		
	$c('webnotes.widgets.form.utils.validate_link', {
			'value':val, 
			'options':me.df.options, 
			'fetch': fetch
		}, 
		function(r,rt) {
			if(r.message=='Ok') {
				// set fetch values
				if($(me.txt).val()!=val) {
					if((me.grid && !from_selector) || (!me.grid)) {
						$(me.txt).val(val);
					}
				}
				
				if(r.fetch_values) 
					me.set_fetch_values(r.fetch_values);

				me.run_trigger();
			} else {
				me.txt.value = ''; 
				me.set('');
			}
		}
	);
}

LinkField.prototype.set_fetch_values = function(fetch_values) { 
	var fl = cur_frm.fetch_dict[this.df.fieldname].fields;
	var changed_fields = [];
	for(var i=0; i< fl.length; i++) {
		if(locals[this.doctype][this.docname][fl[i]]!=fetch_values[i]) {
			locals[this.doctype][this.docname][fl[i]] = fetch_values[i];
			if(!this.grid) {
				refresh_field(fl[i]);
				
				// call trigger on the target field
				changed_fields.push(fl[i]);
			}
		}
	}
	
	// run triggers
	for(i=0; i<changed_fields.length; i++) {
		if(cur_frm.fields_dict[changed_fields[i]]) // on main
			cur_frm.fields_dict[changed_fields[i]].run_trigger();
	}
	
	// refresh grid
	if(this.grid) this.grid.refresh();
}

LinkField.prototype.set_get_query = function() { 
	if(this.get_query)return;

	if(this.grid) {
		var f = this.grid.get_field(this.df.fieldname);
		if(f.get_query) this.get_query = f.get_query;
	}
}

LinkField.prototype.set_disp = function(val) {
	var t = null; 
	if(val)t = "<a href=\'javascript:loaddoc(\""+this.df.options+"\", \""+val+"\")\'>"+val+"</a>";
	this.set_disp_html(t);
}



var tmpid = 0;

_f.ButtonField = function() { };
_f.ButtonField.prototype = new Field();
_f.ButtonField.prototype.with_label = 0;
_f.ButtonField.prototype.make_input = function() { var me = this;

	// make a button area for one button
	if(!this.button_area) 
		this.button_area = $a(this.input_area, 'div','',{
				marginBottom:'4px'});
	
	// make the input
	this.input = $btn(this.button_area, 
		me.df.label, null, 
		{fontWeight:'bold'}, null, 1)

	$(this.input).click(function() {
		if(me.not_in_form) return;
		
		if(cur_frm.cscript[me.df.fieldname] && (!me.in_filter)) {
			cur_frm.runclientscript(me.df.fieldname, me.doctype, me.docname);
		} else {
			cur_frm.runscript(me.df.options, me);
		}
	});
}

_f.ButtonField.prototype.hide = function() { 
	$dh(this.wrapper);
};

_f.ButtonField.prototype.show = function() { 
	$ds(this.wrapper);
};


_f.ButtonField.prototype.set = function(v) { }; // No Setter
_f.ButtonField.prototype.set_disp = function(val) {  } // No Disp on readonly

function make_field(docfield, doctype, parent, frm, in_grid, hide_label) { // Factory
	return new wn.ui.form.make_control({
		df: docfield,
		doctype: doctype,
		parent: parent,
		hide_label: hide_label,
		frm: frm
	});

	switch(docfield.fieldtype.toLowerCase()) {		
		// form fields
		case 'code':var f = new _f.CodeField(); break;
		case 'text editor':var f = new _f.CodeField(); break;
		case 'table':var f = new _f.TableField(); break;
		case 'image':var f= new _f.ImageField(); break;
	}
	
	if(!f) console.log(docfield.fieldtype)

	f.parent 	= parent;
	f.doctype 	= doctype;
	f.df 		= docfield;
	f.perm 		= frm ? frm.perm : [[1,1,1]];
	if(_f)
		f.col_break_width = _f.cur_col_break_width;

	if(in_grid) {
		f.in_grid = true;
		f.with_label = 0;
	}
	if(hide_label) {
		f.with_label = 0;
	}
	if(frm) {
		f.frm = frm;
		if(parent)
			f.layout_cell = parent.parentNode;
	}
	if(f.init) f.init();
	f.make_body();
	return f;
}

