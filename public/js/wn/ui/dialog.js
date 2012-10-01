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

// opts { width, height, title, fields (like docfields) }

wn.provide('wn.ui');

wn.ui.FieldGroup = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make_fields();
		this.catch_enter_as_submit();
	},
	first_button: false,
	make_fields: function() {
		if(!window.make_field) {
			// called in website, load some libs
			wn.require('css/fields.css');
			wn.require('js/fields.js');
		}

		$(this.parent).css({padding:'11px'});
		this.fields_dict = {}; // reset
		for(var i=0; i< this.fields.length; i++) {
			var df = this.fields[i];
			if(!df.fieldname && df.label) {
				df.fieldname = df.label.replace(/ /g, '_').toLowerCase();
			}
			if(!df.fieldtype) df.fieldtype="Data";
			
			var div = $a(this.parent, 'div', '', {margin:'6px 0px'})
			f = make_field(df, null, div, null);
			f.not_in_form = 1;
			this.fields_dict[df.fieldname] = f
			f.refresh();
			
			// first button primary ?
			if(df.fieldtype=='Button' && !this.first_button) {
				$(f.input).addClass('btn-info');
				this.first_button = true;
			}
		}
	},
	catch_enter_as_submit: function() {
		var me = this;
		$(this.parent).find(':input[type="text"], :input[type="password"]').keypress(function(e) {
			if(e.which==13) {
				$(me.parent).find('.btn-info:first').click();
			}
		})
	},
	get_values: function() {
		var ret = {};
		var errors = [];
		for(var key in this.fields_dict) {
			var f = this.fields_dict[key];
			var v = f.get_value ? f.get_value() : null;

			if(f.df.reqd && !v) 
				errors.push(f.df.label + ' is mandatory');

			if(v) ret[f.df.fieldname] = v;
		}
		if(errors.length) {
			msgprint('<b>Please check the following Errors</b>\n' + errors.join('\n'));
			return null;
		}
		return ret;
	},
	get_value: function(key) {
		var f = this.fields_dict[key];
		return f && (f.get_value ? f.get_value() : null);
	},
	set_value: function(key, val){
		var f = this.fields_dict[key];
		if(f) {
			f.set_input(val);
			f.refresh_mandatory();
		}		
	},
	set_values: function(dict) {	
		for(var key in dict) {
			if(this.fields_dict[key]) {
				this.set_value(key, dict[key]);
			}
		}
	},
	clear: function() {
		for(key in this.fields_dict) {
			var f = this.fields_dict[key];
			if(f) {
				f.set_input(f.df['default'] || '');				
			}
		}
	}
});

wn.ui.Dialog = wn.ui.FieldGroup.extend({
	init: function(opts) {
		this.display = false;
		if(!opts.width) opts.width = 480;

		$.extend(this, opts);
		this.make();
		
		// init fields
		if(this.fields) {
			this.parent = this.body
			this._super({});
		}
	},
	make: function() {
		if(!$('#dialog-container').length) {
			$('<div id="dialog-container">').appendTo('body');
		}
		
		this.wrapper = $('<div class="dialog_wrapper">')
			.appendTo('#dialog-container').get(0);

		if(this.width)
			this.wrapper.style.width = this.width + 'px';

		this.make_head();
		this.body = $a(this.wrapper, 'div', 'dialog_body');	
	},
	make_head: function() {
		var me = this;
		this.appframe = new wn.ui.AppFrame(this.wrapper);
		this.appframe.$titlebar.find('.close').unbind('click').click(function() {
			if(me.oncancel)me.oncancel(); me.hide();
		});
		this.set_title(this.title);
	},
	set_title: function(t) {
		this.appframe.$titlebar.find('.appframe-title').html(t || '');
	},
	set_postion: function() {
		// place it at the center
		this.wrapper.style.left  = (($(window).width() - cint(this.wrapper.style.width))/2) + 'px';
        this.wrapper.style.top = ($(window).scrollTop() + 60) + 'px';

		// place it on top
		top_index++;
		$y(this.wrapper,{zIndex:top_index});		
	},
	show: function() {
		// already live, do nothing
		if(this.display) return;

		// set position
		this.set_postion()

		// show it
		$ds(this.wrapper);
		
		// hide background
		freeze();

		this.display = true;
		cur_dialog = this;

		// call onshow
		if(this.onshow)this.onshow();
		
		// focus on first input
		$(this.wrapper).find(':input:first').focus();
	},
	hide: function() {
		// call onhide
		if(this.onhide) this.onhide();

		// hide
		unfreeze();
		$dh(this.wrapper);

		// flags
		this.display = false;
		cur_dialog = null;
	},
	no_cancel: function() {
		this.appframe.$titlebar.find('.close').toggle(false);
	}
});

// close open dialogs on ESC
$(document).bind('keydown', function(e) {
	if(cur_dialog && !cur_dialog.no_cancel_flag && e.which==27) {
		cur_dialog.hide();
	}
});