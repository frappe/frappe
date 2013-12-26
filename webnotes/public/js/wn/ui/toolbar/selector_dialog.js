// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

/*
opts:

- title
- execute

*/

wn.provide('wn.ui.toolbar');

wn.ui.toolbar.SelectorDialog = Class.extend({
	init: function(opts) {
		this.opts = opts;
		this.make_dialog();			
		this.bind_events();
	},
	make_dialog: function() {
		this.dialog = new wn.ui.Dialog({
			title: this.opts.title,
			width: 300,
			fields: [
				{fieldtype:'Select', fieldname:'doctype', options:'Select...', label:wn._('Select Type')},
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
			lst[i]={label:wn._(lst[i]), value:lst[i]};
		
		// set values
		var sel = this.dialog.fields_dict.doctype.input;
		$(sel).empty().add_options(lst.sort(function(a, b) { 
			return (a.label > b.label ? 1 : -1) }));
	}
})