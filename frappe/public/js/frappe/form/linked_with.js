// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.LinkedWith = Class.extend({
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
	},
	show: function() {
		if(!this.dialog)
			this.make_dialog();

		this.dialog.fields_dict.list.$wrapper.html('<div class="text-muted text-center">'
			+ __("Loading") + '...</div>');

		this.dialog.show();
	},
	make_dialog: function() {
		var me = this;

		this.dialog = new frappe.ui.Dialog({
			hide_on_page_refresh: true,
			title: __("Linked With"),
			fields: [
				{ fieldtype: "HTML", label: "list" }
			]
		});

		this.dialog.$wrapper.find(".modal-dialog").addClass("linked-with-dialog");

		this.dialog.on_page_show = function() {
			// execute ajax calls sequentially
			// 1. get linked doctypes
			// 2. load all doctypes
			// 3. load linked docs
			$.when(me.get_linked_doctypes())
				.then(function() { return me.load_doctypes() })
				.then(function() {
					if (me.links_not_permitted_or_missing()) {
						return;
					}

					return me.get_linked_docs();
				});
		}

	},

	load_doctypes: function() {
		var me = this;
		var already_loaded = Object.keys(locals.DocType);
		var doctypes_to_load = [];
		$.each(Object.keys(me.frm.__linked_doctypes), function(i, v) {
			if (already_loaded.indexOf(v)===-1) {
				doctypes_to_load.push(v);
			}
		});

		// load all doctypes sequentially using with_doctype
		return $.when.apply($, $.map(doctypes_to_load, function(dt) {
			return frappe.model.with_doctype(dt, function() {
				if (frappe.listview_settings[dt]) {
					// add additional fields to __linked_doctypes
					me.frm.__linked_doctypes[dt].add_fields = frappe.listview_settings[dt].add_fields;
				}
			});
		}));
	},

	links_not_permitted_or_missing: function() {
		var me = this;
		var links = [];
		$.each(me.frm.__linked_doctypes, function(doctype, tmp) {
			if(frappe.model.can_get_report(doctype)) {
				links.push({label: __(doctype), value: doctype});
			}
		});

		links = frappe.utils.sort(links, "label");

		if(!links) {
			me.dialog.fields_dict.list.$wrapper.html("<div class='alert alert-warning'>"
			+ me.frm.doctype + ": "
			+ (me.frm.__linked_doctypes ? __("Not Linked to any record.") : __("Not enough permission to see links."))
			+ "</div>")
			return true;
		}

		return false;
	},

	get_linked_doctypes: function() {
		var me = this;
		if (this.frm.__linked_doctypes) {
			return;
		}

		return frappe.call({
			method: "frappe.desk.form.linked_with.get_linked_doctypes",
			args: {
				doctype: this.frm.doctype
			},
			callback: function(r) {
				me.frm.__linked_doctypes = r.message;
			}
		});
	},

	get_linked_docs: function() {
		var me = this;

		return frappe.call({
			method:"frappe.desk.form.linked_with.get_linked_docs",
			args: {
				doctype: me.frm.doctype,
				name: me.frm.docname,
				linkinfo: me.frm.__linked_doctypes
			},
			callback: function(r) {
				var parent = me.dialog.fields_dict.list.$wrapper.empty();

				if(keys(r.message || {}).length) {
					$.each(keys(r.message).sort(), function(i, doctype) {
						var listview = frappe.views.get_listview(doctype, me);
						listview.no_delete = true;

						var wrapper = $('<div class="panel panel-default"><div>').appendTo(parent);
						$('<div class="panel-heading">').html(__(doctype).bold()).appendTo(wrapper);
						var body = $('<div class="panel-body">').appendTo(wrapper);

						$.each(r.message[doctype], function(i, d) {
							d.doctype = doctype;
							listview.render($('<div class="list-row"></div>')
								.appendTo(body), d, me);
						})
					})
				} else {
					parent.html(__("Not Linked to any record."));
				}
			}
		});
	}
});
