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
			var new_doc = frappe.model.get_new_doc(doctype);

			// set the name if called from a link field
			if(opts && opts.name_field) {
				var meta = frappe.get_meta(doctype);
				if(meta.autoname && meta.autoname.indexOf("field:")!==-1) {
					new_doc[meta.autoname.substr(6)] = opts.name_field;
				} else if(meta.title_field) {
					new_doc[meta.title_field] = opts.name_field;
				}
			}

			frappe.set_route("Form", doctype, new_doc.name);

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
