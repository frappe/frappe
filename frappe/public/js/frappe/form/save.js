// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.save = function(frm, action, callback, btn) {
	$(btn).prop("disabled", true);

	var save = function() {
		check_name();
		if(check_mandatory()) {
			_call({
				method: "frappe.widgets.form.save.savedocs",
				args: { doc: frm.doc, action:action},
				callback: function(r) {
					$(document).trigger("save", [frm.doc]);
					callback(r);
				},
				btn: btn
			});
		} else {
			$(btn).prop("disabled", false);
		}
	};

	var cancel = function() {
		_call({
			method: "frappe.widgets.form.save.cancel",
			args: { doctype: frm.doc.doctype, name: frm.doc.name },
			callback: function(r) {
				$(document).trigger("save", [frm.doc]);
				callback(r);
			},
			btn: btn
		});
	};

	var check_name = function() {
		var doc = frm.doc;
		var meta = locals.DocType[doc.doctype];
		if(doc.__islocal && (meta && meta.autoname
				&& meta.autoname.toLowerCase()=='prompt')) {
			var newname = prompt('Enter the name of the new '+ doc.doctype, '');
			if(newname) {
				doc.__newname = strip(newname);
			} else {
				msgprint(__("Name is required"));
				$(btn).prop("disabled", false);
				throw "name required";
			}
		}
	};

	var check_mandatory = function() {
		var me = this;
		var has_errors = false;
		frm.scroll_set = false;

		if(frm.doc.docstatus==2) return true; // don't check for cancel

		$.each(frappe.model.get_all_docs(frm.doc), function(i, doc) {

			var error_fields = [];
			var folded = false;

			$.each(frappe.meta.docfield_list[doc.doctype] || [], function(i, docfield) {
				if(docfield.fieldname) {
					var df = frappe.meta.get_docfield(doc.doctype,
						docfield.fieldname, frm.doc.name);

					if(df.fieldtype==="Fold") {
						folded = frm.layout.folded;
					}

					if(df.reqd && !frappe.model.has_value(doc.doctype, doc.name, df.fieldname)) {
						has_errors = true;
						error_fields[error_fields.length] = __(df.label);

						// scroll to field
						if(!me.scroll_set) {
							scroll_to(doc.parentfield || df.fieldname);
						}

						if(folded) {
							frm.layout.unfold();
							folded = false;
						}
					}

				}
			});
			if(error_fields.length)
				msgprint(__('Mandatory fields required in {0}', [(doc.parenttype
					? (__(frappe.meta.docfield_map[doc.parenttype][doc.parentfield].label) + ' ('+ __("Table") + ')')
					: __(doc.doctype))]) + '\n' + error_fields.join('\n'));
		});

		return !has_errors;
	};

	var scroll_to = function(fieldname) {
		var f = cur_frm.fields_dict[fieldname];
		if(f) {
			$(document).scrollTop($(f.wrapper).offset().top - 80);
		}
		frm.scroll_set = true;
	};

	var _call = function(opts) {
		// opts = {
		// 	method: "some server method",
		// 	args: {args to be passed},
		// 	callback: callback,
		// 	btn: btn
		// }
		$(opts.btn).prop("disabled", true);
		return frappe.call({
			freeze: true,
			method: opts.method,
			args: opts.args,
			callback: function(r) {
				$(opts.btn).prop("disabled", false);
				opts.callback && opts.callback(r);
			}
		})
	};

	if(action==="cancel") {
		cancel();
	} else {
		save();
	}
}
