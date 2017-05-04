// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.save = function(frm, action, callback, btn) {
	$(btn).prop("disabled", true);

	// specified here because there are keyboard shortcuts to save
	var working_label = {
		"Save": __("Saving"),
		"Submit": __("Submitting"),
		"Update": __("Updating"),
		"Amend": __("Amending"),
		"Cancel": __("Cancelling")
	}[toTitle(action)];

	var freeze_message = working_label ? __(working_label) : "";

	var save = function() {
		check_name(function() {
			$(frm.wrapper).addClass('validated-form');
			if(check_mandatory()) {
				_call({
					method: "frappe.desk.form.save.savedocs",
					args: { doc: frm.doc, action:action},
					callback: function(r) {
						$(document).trigger("save", [frm.doc]);
						callback(r);
					},
					btn: btn,
					freeze_message: freeze_message
				});
			} else {
				$(btn).prop("disabled", false);
			}
		});

	};

	var cancel = function() {
		var args = {
			doctype: frm.doc.doctype,
			name: frm.doc.name
		};

		// update workflow state value if workflow exists
		var workflow_state_fieldname = frappe.workflow.get_state_fieldname(frm.doctype);
		if(workflow_state_fieldname) {
			$.extend(args, {
				workflow_state_fieldname: workflow_state_fieldname,
				workflow_state: frm.doc[workflow_state_fieldname]

			});
		}

		_call({
			method: "frappe.desk.form.save.cancel",
			args: args,
			callback: function(r) {
				$(document).trigger("save", [frm.doc]);
				callback(r);
			},
			btn: btn,
			freeze_message: freeze_message
		});
	};

	var check_name = function(callback) {
		var doc = frm.doc;
		var meta = locals.DocType[doc.doctype];
		if(doc.__islocal && (meta && meta.autoname
				&& meta.autoname.toLowerCase()=='prompt')) {
			var d = frappe.prompt(__("Name"), function(values) {
				var newname = values.value;
				if(newname) {
					doc.__newname = strip(newname);
				} else {
					msgprint(__("Name is required"));
					throw "name required";
				}

				callback();

			}, __('Enter the name of the new {0}', [doc.doctype]), __("Create"));

			if(doc.__newname) {
				d.set_value("value", doc.__newname);
			}

			d.onhide = function() {
				$(btn).prop("disabled", false);
			}
		} else {
			callback();
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
			if(error_fields.length) {
				if(doc.parenttype) {
					var message = __('Mandatory fields required in table {0}, Row {1}',
						[__(frappe.meta.docfield_map[doc.parenttype][doc.parentfield].label).bold(), doc.idx]);
				} else {
					var message = __('Mandatory fields required in {0}', [__(doc.doctype)]);

				}
				message = message + '<br><br><ul><li>' + error_fields.join('</li><li>') + "</ul>";
				msgprint({
					message: message,
					indicator: 'red',
					title: __('Missing Fields')
				});
			}
		});

		return !has_errors;
	};

	var scroll_to = function(fieldname) {
		var f = cur_frm.fields_dict[fieldname];
		if(f) {
			$(document).scrollTop($(f.wrapper).offset().top - 60);
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

		if(frappe.ui.form.is_saving) {
			// this is likely to happen if the user presses the shortcut cmd+s for a longer duration or uses double click
			// no need to show this to user, as they can see "Saving" in freeze message
			console.log("Already saving. Please wait a few moments.")
			throw "saving";
		}
		frappe.ui.form.is_saving = true;

		return frappe.call({
			freeze: true,
			freeze_message: opts.freeze_message,
			method: opts.method,
			args: opts.args,
			btn: opts.btn,
			callback: function(r) {
				opts.callback && opts.callback(r);
			},
			always: function(r) {
				frappe.ui.form.is_saving = false;
				if(r) {
					var doc = r.docs && r.docs[0];
					if(doc) {
						frappe.ui.form.update_calling_link(doc);
					}					
				}
			}
		})
	};

	if(action==="cancel") {
		cancel();
	} else {
		save();
	}
}

frappe.ui.form.update_calling_link = function(newdoc) {
	if(frappe._from_link && newdoc.doctype===frappe._from_link.df.options) {
		var doc = frappe.get_doc(frappe._from_link.doctype, frappe._from_link.docname);
		// set value
		if (doc && doc.parentfield){
			//update values for child table
			$.each(frappe._from_link.frm.fields_dict[doc.parentfield].grid.grid_rows, function(index, field) {
				if(field.doc && field.doc.name===frappe._from_link.docname){
					frappe._from_link.set_value(newdoc.name);
			}});
		} else {
			frappe._from_link.set_value(newdoc.name);
	    }

		// refresh field
		frappe._from_link.refresh();

		// if from form, switch
		if(frappe._from_link.frm) {
			frappe.set_route("Form", frappe._from_link.frm.doctype, frappe._from_link.frm.docname);
			setTimeout(function() { frappe.utils.scroll_to(frappe._from_link_scrollY); }, 100);
		}

		frappe._from_link = null;
	}
}

