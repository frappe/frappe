// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.formview');

frappe.views.FormFactory = class FormFactory extends frappe.views.Factory {
	make(route) {
		var me = this,
			doctype = route[1],
			doctype_layout = frappe.router.doctype_layout || doctype;

		if (!frappe.views.formview[doctype_layout]) {
			frappe.model.with_doctype(doctype, function() {
				me.page = frappe.container.add_page("form/" + doctype_layout);
				frappe.views.formview[doctype_layout] = me.page;
				me.page.frm = new frappe.ui.form.Form(doctype, me.page, true, frappe.router.doctype_layout);
				me.show_doc(route);
			});
		} else {
			me.show_doc(route);
		}

		if (!this.initialized) {
			$(document).on("page-change", function() {
				frappe.ui.form.close_grid_form();
			});

			frappe.realtime.on("doc_viewers", function(data) {
				// set users that currently viewing the form
				frappe.ui.form.set_users(data, 'viewers');
			});

			frappe.realtime.on("doc_typers", function(data) {
				// set users that currently typing on the form
				frappe.ui.form.set_users(data, 'typers');
			});
		}


		this.initialized = true;
	}

	show_doc(route) {
		debugger;
		var doctype = route[1],
			doctype_layout = frappe.router.doctype_layout || doctype,
			name = route.slice(2).join("/"),
			me = this;

		if (frappe.model.new_names[name]) {
			name = frappe.model.new_names[name];
			frappe.set_route("Form", doctype_layout, name);
			return;
		}

		frappe.model.with_doc(doctype, name, function(name, r) {
			if (r && r['403']) return; // not permitted

			if (!(locals[doctype] && locals[doctype][name])) {
				// doc not found, but starts with New,
				// make a new doc and set it
				if (name && name==='new') {
					var new_name = frappe.model.make_new_doc_and_get_name(doctype, true);
					if (new_name===name) {
						me.load(doctype_layout, name);
					} else {
						frappe.set_route("Form", doctype_layout, new_name);
					}
				} else {
					frappe.show_not_found(route);
				}
				return;
			}
			me.load(doctype_layout, name);
		});
	}

	load(doctype_layout, name) {
		frappe.container.change_to("form/" + doctype_layout);
		frappe.views.formview[doctype_layout].frm.refresh(name);
	}
}
