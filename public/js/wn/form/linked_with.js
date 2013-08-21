// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
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
		this.dialog.get_input("list_by").change();
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
				{ fieldtype: "HTML", label: "help", 
					options:"<div class='help'>" + wn._("List of records in which this document is linked") 
						+"</div>" },
				{ fieldtype: "Select", options: links, 
					label: wn._("Type"), fieldname: "list_by" },
				{ fieldtype: "HTML", label: "hr", options:"<hr>" },
				{ fieldtype: "HTML", label: "list" }
			]
		});
		
		this.dialog.get_input("list_by").val(links[0].value);
		
		if(!links) {
			this.dialog.fields_dict.list.$wrapper.html("<div class='alert alert-warning'>"
			+ this.frm.doctype + ": "
			+ (this.linked_with ? wn._("Not Linked to any record.") : wn._("Not enough permission to see links."))
			+ "</div>")
			this.dialog.fields_dict.list_by.$wrapper.toggle(false);
			this.dialog.fields_dict.help.$wrapper.toggle(false);
			return;
		}
		
		this.dialog.get_input("list_by").change(function() {
			me.doctype = me.dialog.get_input("list_by").val();
			
			wn.model.with_doctype(me.doctype, function(r) {
				me.make_listing();
				me.lst.run();
			})
		});
	},
	make_listing: function() {
		var me = this;
		this.listview = wn.views.get_listview(this.doctype, this);
		this.lst = new wn.ui.Listing({
			hide_refresh: true,
			no_loading: true,
			no_toolbar: true,
			doctype: me.doctype,
			show_filters: true,
			parent: $(this.dialog.fields_dict.list.wrapper).empty().css("min-height", "300px")
				.get(0),
			method: 'webnotes.widgets.reportview.get',
			type: "GET",
			custom_new_doc: me.listview.make_new_doc || undefined,
			get_args: function() {
				var args = {
					doctype: this.doctype,
					fields: this.listview.fields,
					filters: this.filter_list.get_filters(),
					docstatus: ['0','1'],
					order_by: this.listview.order_by || undefined,
					group_by: this.listview.group_by || undefined,
				}
				return args;
			},
			render_row: function(parent, data) {
				data.doctype = this.doctype;
				me.listview.render(parent, data, this);
			},
			get_no_result_message: function() {
				return repl("<div class='alert alert-info'>%(doctype)s: " + wn._("Not linked") + "</div>", {
					name: me.frm.doc.name,
					doctype: wn._(me.doctype)
				})
			}
		});
		me.lst.filter_list.show_filters(true);
		me.lst.filter_list.clear_filters();
		
		var link_doctype = me.linked_with[me.doctype].child_doctype || me.doctype;
		
		me.lst.set_filter(me.linked_with[me.doctype].fieldname, me.frm.doc.name, link_doctype);
		me.lst.listview = me.listview;
	}
});