// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

function loadreport(dt, rep_name, onload) {
	if(rep_name)
		frappe.set_route('Report', dt, rep_name);
	else
		frappe.set_route('Report', dt);
}

function loaddoc(doctype, name, onload) {
	frappe.model.with_doctype(doctype, function() {
		if(locals.DocType[doctype].in_dialog) {
			_f.edit_record(doctype, name);
		} else {
			frappe.set_route('Form', doctype, name);
		}
	})
}
var load_doc = loaddoc;

frappe.create_routes = {};
function new_doc(doctype, opts) {
	frappe.model.with_doctype(doctype, function() {
		if(frappe.create_routes[doctype]) {
			frappe.set_route(frappe.create_routes[doctype]);
		} else {
			frappe.ui.form.quick_entry(doctype, function(doc) {
				frappe.set_route('Form', doctype, doc.name);
			});
		}
	});
}
var newdoc = new_doc;

function loadpage(page_name, call_back, no_history) {
	frappe.set_route(page_name);
}

function loaddocbrowser(dt) {
	frappe.set_route('List', dt);
}
