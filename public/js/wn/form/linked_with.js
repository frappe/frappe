// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for license information please see license.txt

wn.provide("wn.ui.form")

wn.ui.form.LinkedWith = Class.extend({
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
	},
	show: function() {
		if(!this.dialog)
			this.make_dialog();
		
		this.dialog.show();
	},
	make_dialog: function() {
		var me = this;
		this.linked_with = this.frm.meta.__linked_with;

		var links = [];
		$.each(this.linked_with, function(doctype, tmp) {
			if(wn.model.can_get_report(doctype)) {
				links.push({label: wn._(doctype), value: doctype});
			}
		});
		
		links = wn.utils.sort(links, "label");
				
		this.dialog = new wn.ui.Dialog({
			width: 700,
			hide_on_page_refresh: true,
			title: wn._("Linked With"),
			fields: [
				{ fieldtype: "HTML", label: "list" }
			]
		});
				
		if(!links) {
			this.dialog.fields_dict.list.$wrapper.html("<div class='alert alert-warning'>"
			+ this.frm.doctype + ": "
			+ (this.linked_with ? wn._("Not Linked to any record.") : wn._("Not enough permission to see links."))
			+ "</div>")
			return;
		}
		
		this.dialog.onshow = function() {
			me.dialog.fields_dict.list.$wrapper.html('<div class="progress progress-striped active">\
					<div class="progress-bar" style="width: 100%;">\
					</div></div>');
			
			wn.call({
				method:"webnotes.widgets.form.utils.get_linked_docs",
				args: {
					doctype: me.frm.doctype,
					name: me.frm.docname,
					metadata_loaded: keys(locals.DocType)
				},
				callback: function(r) {
					var parent = me.dialog.fields_dict.list.$wrapper.empty();

					if(keys(r.message || {}).length) {
						$.each(keys(r.message).sort(), function(i, doctype) {							
							var listview = wn.views.get_listview(doctype, me);
							listview.no_delete = true;
							$("<h4>").html(wn._(doctype)).appendTo(parent);
							
							$.each(r.message[doctype], function(i, d) {
								d.doctype = doctype;
								listview.render($("<div>").appendTo(parent), d, me);
							})
						})
					} else {
						parent.html(wn._("Not Linked to any record."));
					}
				}
			})
		}
		
	},
});