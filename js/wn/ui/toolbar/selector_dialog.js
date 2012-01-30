/*
opts:

- title
- execute

*/

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
		this.dialog = new wn.widgets.Dialog({
			title: this.opts.title,
			width: 300,
			fields: [
				{fieldtype:'Select', fieldname:'doctype', options:'Select...', label:'Select Type'},
				{fieldtype:'Button', label:'Go', fieldname:'go'}
			]
		});
	},
	bind_events: function() {
		var me = this;
		
		// on go
		$(this.dialog.fields_dict.go.input).click(function() {
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