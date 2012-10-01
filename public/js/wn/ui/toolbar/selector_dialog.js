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

/*
opts:

- title
- execute

*/

wn.provide('wn.ui.toolbar');

wn.ui.toolbar.SelectorDialog = Class.extend({
	init: function(opts) {
		this.opts = opts;
		try{
			this.make_dialog();			
		} catch(e) {
			console.log(e);
		}
		this.bind_events();
	},
	make_dialog: function() {
		this.dialog = new wn.ui.Dialog({
			title: this.opts.title,
			width: 300,
			fields: [
				{fieldtype:'Select', fieldname:'doctype', options:'Select...', label:'Select Type'},
				{fieldtype:'Button', label:'Go', fieldname:'go'}
			]
		});
		if(this.opts.help) {
			$("<div class='help'>"+this.opts.help+"</div>").appendTo(this.dialog.body);
		}
	},
	bind_events: function() {
		var me = this;
		
		// on go
		$(this.dialog.fields_dict.go.input).click(function() {
			if(!me.dialog.display) return;
			me.dialog.hide();
			me.opts.execute(me.dialog.fields_dict.doctype.get_value());
		});
		
		// on change
		$(this.dialog.fields_dict.doctype.input).change(function() {
			me.dialog.fields_dict.go.input.click();
		}).keypress(function(ev) {
			if(ev.which==13) {
				me.dialog.fields_dict.go.input.click();				
			}
		});
		
		
	},
	show: function() {
		this.dialog.show();
		this.dialog.fields_dict.doctype.input.focus();
		return false;
	},
	set_values: function(lst) {
		// convert to labels
		for(var i=0;i<lst.length;i++) 
			lst[i]=get_doctype_label(lst[i]);
		
		// set values
		var sel = this.dialog.fields_dict.doctype.input;
		$(sel).empty();
		add_sel_options(sel, lst.sort());		
	}
})