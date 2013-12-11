// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.provide('wn.ui');

var cur_dialog;

wn.ui.open_dialogs = [];
wn.ui.Dialog = wn.ui.FieldGroup.extend({
	_intro:'	usage:\n\
		\n\
		var dialog = new wn.ui.Dialog({\n\
			title: "Dialog Title",\n\
			fields: [\n\
				{fieldname:"field1", fieldtype:"Data", reqd:1, label: "Test 1"},\n\
				{fieldname:"field2", fieldtype:"Link", reqd:1, label: "Test 1", options:"Some DocType"},\n\
				{fieldname:"mybutton", fieldtype:"Button", reqd:1, label: "Submit"},\n\
			]\n\
		})\n\
		dialog.get_input("mybutton").click(function() { /* do something; */ dialog.hide(); });\n\
		dialog.show()',
	init: function(opts) {
		this.display = false;
		this.is_dialog = true;
		if(!opts.width) opts.width = 480;

		$.extend(this, opts);
		this._super();
		this.make();
	},
	make: function() {
		this.$wrapper = wn.get_modal("", "");
		this.wrapper = this.$wrapper.find('.modal-dialog').get(0);
		this.make_head();
		this.body = this.$wrapper.find(".modal-body").get(0);
		
		// make fields (if any)
		this._super();
		
		var me = this;
		this.$wrapper
			.on("hide.bs.modal", function() {
				me.display = false;
				if(wn.ui.open_dialogs[wn.ui.open_dialogs.length-1]===me) {
					wn.ui.open_dialogs.pop();
					if(wn.ui.open_dialogs.length)
						cur_dialog = wn.ui.open_dialogs[wn.ui.open_dialogs.length-1];
					else
						cur_dialog = null;
				}
				me.onhide && me.onhide();
			})
			.on("shown.bs.modal", function() {
				// focus on first input
				me.display = true;
				cur_dialog = me;
				wn.ui.open_dialogs.push(me);
				var first = me.$wrapper.find(':input:first');
				if(first.length && first.attr("data-fieldtype")!="Date") {
					try {
						first.get(0).focus();
					} catch(e) {
						console.log("Dialog: unable to focus on first input: " + e);
					}
				}
				me.onshow && me.onshow();
			})
		
		
	},
	make_head: function() {
		var me = this;
		//this.appframe = new wn.ui.AppFrame(this.wrapper);
		//this.appframe.set_document_title = false;
		this.set_title(this.title);
	},
	set_title: function(t) {
		this.$wrapper.find(".modal-title").html(t);
	},
	show: function() {
		// show it
		this.$wrapper.modal("show");
	},
	hide: function(from_event) {
		this.$wrapper.modal("hide");
	},
	no_cancel: function() {
		this.$wrapper.find('.close').toggle(false);
	}
});

// close open dialogs on ESC
$(document).bind('keydown', function(e) {
	if(cur_dialog && !cur_dialog.no_cancel_flag && e.which==27) {
		cur_dialog.hide();
	}
});