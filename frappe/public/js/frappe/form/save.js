// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.save = function (frm, action, callback, btn) {
	$(btn).prop("disabled", true);

	// specified here because there are keyboard shortcuts to save
	const working_label = {
		Save: __("Saving", null, "Freeze message while saving a document"),
		Submit: __("Submitting", null, "Freeze message while submitting a document"),
		Update: __("Updating", null, "Freeze message while updating a document"),
		Amend: __("Amending", null, "Freeze message while amending a document"),
		Cancel: __("Cancelling", null, "Freeze message while cancelling a document"),
	}[toTitle(action)];

	var freeze_message = working_label ? __(working_label) : "";

	var save = function () {
		$(frm.wrapper).addClass("validated-form");
		if ((action !== "Save" || frm.is_dirty()) && frappe.ui.form.check_mandatory(frm)) {
			_call({
				method:
					action === "Submit"
						? "frappe.desk.form.save.submit"
						: "frappe.desk.form.save.savedocs",
				args: { doc: frm.doc, action: action },
				callback: function (r) {
					$(document).trigger("save", [frm.doc]);
					callback(r);
				},
				error: function (r) {
					callback(r);
				},
				btn: btn,
				freeze_message: freeze_message,
			});
		} else {
			!frm.is_dirty() &&
				frappe.show_alert({ message: __("No changes in document"), indicator: "orange" });
			$(btn).prop("disabled", false);
		}
	};

	var cancel = function () {
		var args = {
			doctype: frm.doc.doctype,
			name: frm.doc.name,
		};

		// update workflow state value if workflow exists
		var workflow_state_fieldname = frappe.workflow.get_state_fieldname(frm.doctype);
		if (workflow_state_fieldname) {
			$.extend(args, {
				workflow_state_fieldname: workflow_state_fieldname,
				workflow_state: frm.doc[workflow_state_fieldname],
			});
		}

		_call({
			method: "frappe.desk.form.save.cancel",
			args: args,
			callback: function (r) {
				$(document).trigger("save", [frm.doc]);
				callback(r);
			},
			btn: btn,
			freeze_message: freeze_message,
		});
	};

	var _call = function (opts) {
		// opts = {
		// 	method: "some server method",
		// 	args: {args to be passed},
		// 	callback: callback,
		// 	btn: btn
		// }

		if (frappe.ui.form.is_saving) {
			// this is likely to happen if the user presses the shortcut cmd+s for a longer duration or uses double click
			// no need to show this to user, as they can see "Saving" in freeze message
			console.log("Already saving. Please wait a few moments.");
			throw "saving";
		}

		// ensure we remove new docs routes ONLY
		if (frm.is_new()) {
			frappe.ui.form.remove_old_form_route();
		}
		frappe.ui.form.is_saving = true;

		return frappe.call({
			freeze: true,
			// freeze_message: opts.freeze_message,
			method: opts.method,
			args: opts.args,
			btn: opts.btn,
			callback: function (r) {
				opts.callback && opts.callback(r);
			},
			error: opts.error,
			always: function (r) {
				$(btn).prop("disabled", false);
				frappe.ui.form.is_saving = false;

				if (r) {
					var doc = r.docs && r.docs[0];
					if (doc) {
						frappe.ui.form.update_calling_link(doc);
					}
				}
			},
		});
	};

	if (action === "cancel") {
		cancel();
	} else {
		save();
	}
};

frappe.ui.form.check_mandatory = function (frm) {
	var has_errors = false;
	frm.scroll_set = false;

	if (frm.doc.docstatus == 2) return true; // don't check for cancel

	const ROW_LIMIT = 10;
	const parent_errors = [];
	const table_errors = {};

	$.each(frappe.model.get_all_docs(frm.doc), function (i, doc) {
		var error_fields = [];
		var folded = false;
		const fields_dict = frappe.meta.get_docfield_copy(doc.doctype, doc.name) || {};

		$.each(frappe.meta.docfield_list[doc.doctype] || [], function (i, docfield) {
			if (docfield.fieldname) {
				const df = fields_dict[docfield.fieldname];
				if (!df) return;

				if (!df.reqd && !df.mandatory_depends_on && df.fieldtype !== "Fold") {
					return;
				}

				if (df.fieldtype === "Fold") {
					folded = frm.layout.folded;
					return;
				}

				if (
					is_docfield_mandatory(doc, df) &&
					!frappe.model.has_value(doc.doctype, doc.name, df.fieldname)
				) {
					has_errors = true;
					error_fields[error_fields.length] = __(df.label, null, df.parent);
					// scroll to field
					if (!frm.scroll_set) {
						scroll_to(doc.parentfield || df.fieldname);
					}

					if (folded) {
						frm.layout.unfold();
						folded = false;
					}
				}
			}
		});

		if (frm.is_new() && frm.meta.autoname === "Prompt" && !frm.doc.__newname) {
			has_errors = true;
			error_fields = [__("Name"), ...error_fields];
		}

		if (error_fields.length) {
			let meta = frappe.get_meta(doc.doctype);
			if (meta.istable) {
				const parentfield = doc.parentfield;
				if (!table_errors[parentfield]) {
					const table_field = frappe.meta.docfield_map[doc.parenttype][parentfield];
					const table_label = __(
						table_field.label || frappe.unscrub(table_field.fieldname)
					).bold();
					table_errors[parentfield] = {
						label: table_label,
						fields: {},
						total_rows: (frm.doc[parentfield] || []).length,
					};
				}
				error_fields.forEach(function (field_label) {
					if (!table_errors[parentfield].fields[field_label]) {
						table_errors[parentfield].fields[field_label] = [];
					}
					table_errors[parentfield].fields[field_label].push(doc.idx);
				});
			} else {
				error_fields.forEach(function (field_label) {
					parent_errors.push(__("{0} is required.", [field_label.bold()]));
				});
			}
		}
	});

	const lines = [...parent_errors];
	Object.values(table_errors).forEach(function (te) {
		Object.entries(te.fields).forEach(function (entry) {
			const field_label = entry[0];
			const rows = entry[1].sort((a, b) => a - b);

			const ranges = [];
			let start = rows[0];
			let prev = rows[0];
			for (let i = 1; i < rows.length; i++) {
				if (rows[i] === prev + 1) {
					prev = rows[i];
				} else {
					ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
					start = prev = rows[i];
				}
			}
			ranges.push(start === prev ? `${start}` : `${start}-${prev}`);

			if (rows.length === te.total_rows) {
				lines.push(
					__("In {0}, {1} is required in every row.", [te.label, field_label.bold()])
				);
			} else if (rows.length === 1) {
				lines.push(
					__("In {0}, {1} is required in row {2}.", [
						te.label,
						field_label.bold(),
						rows[0],
					])
				);
			} else if (ranges.length <= ROW_LIMIT) {
				lines.push(
					__("In {0}, {1} is required in rows {2}.", [
						te.label,
						field_label.bold(),
						frappe.utils.comma_and(ranges),
					])
				);
			} else {
				lines.push(
					__("In {0}, {1} is required in {2} rows.", [
						te.label,
						field_label.bold(),
						rows.length,
					])
				);
			}
		});
	});

	if (lines.length) {
		frappe.msgprint({
			message:
				__("Please fill the following mandatory fields before saving:") +
				"<br><br><ul><li>" +
				lines.join("</li><li>") +
				"</li></ul>",
			indicator: "red",
			title: __("Missing Fields"),
		});
		frm.refresh();
	}

	return !has_errors;

	function is_docfield_mandatory(doc, df) {
		if (df.mandatory_depends_on && doc) {
			let out = null;
			let expression = df.mandatory_depends_on;
			let parent = frm.doc;

			if (typeof expression === "boolean") {
				out = expression;
			} else if (typeof expression === "function") {
				out = expression(doc);
			} else if (expression.substr(0, 5) == "eval:") {
				try {
					out = frappe.utils.eval(expression.substr(5), { doc, parent });
				} catch (e) {
					frappe.throw(__('Invalid "mandatory_depends_on" expression'));
				}
			} else {
				var value = doc[expression];
				if ($.isArray(value)) {
					out = !!value.length;
				} else {
					out = !!value;
				}
			}

			return out;
		}

		return !!df.reqd;
	}

	function scroll_to(fieldname) {
		if (frm.scroll_to_field(fieldname, false)) {
			frm.scroll_set = true;
		}
	}
};

frappe.ui.form.remove_old_form_route = () => {
	let current_route = frappe.get_route().join("/");
	frappe.route_history = frappe.route_history.filter(
		(route) => route.join("/") !== current_route
	);
};

frappe.ui.form.update_calling_link = async (newdoc) => {
	if (!frappe._from_link) return;

	const { field_obj, doc, set_route_args, scrollY } = frappe._from_link;
	const df = field_obj.df;

	if (!["Link", "Dynamic Link", "Table MultiSelect"].includes(df.fieldtype)) return;

	const is_valid_doctype = () => {
		switch (df.fieldtype) {
			case "Link":
				return newdoc.doctype === df.options;
			case "Dynamic Link":
				return newdoc.doctype === doc[df.options];
			case "Table MultiSelect":
				return newdoc.doctype === field_obj.get_options();
		}
	};

	if (!is_valid_doctype()) return;

	// switch back to the original doc first,
	// this is necessary in case from_link.doctype === newdoc.doctype
	if (field_obj.frm) {
		await frappe.set_route(...set_route_args);
		frappe.utils.scroll_to(scrollY);
	}

	delete frappe._from_link;

	await frappe.model.with_doctype(newdoc.doctype);
	const meta = frappe.get_meta(newdoc.doctype);

	// update link title cache
	if (meta.title_field && meta.show_title_field_in_link) {
		frappe.utils.add_link_title(newdoc.doctype, newdoc.name, newdoc[meta.title_field]);
	}

	// parsing is needed for table multiselect to convert string to array
	await field_obj.parse_validate_and_set_in_model(newdoc.name);

	field_obj.refresh();

	// only quick entry form should proceed from here on
	if (field_obj.frm || !(field_obj.layout instanceof frappe.ui.form.QuickEntryForm)) return;

	const quick_entry = field_obj.layout;

	// quick entry form is still open (nested case), no need to redirect
	if (quick_entry.wrapper[0].offsetParent !== null) return;

	// redirect to the original doc's form
	const { doc: original_doc } = quick_entry;
	if (original_doc && original_doc.doctype && original_doc.name) {
		frappe.set_route("Form", original_doc.doctype, original_doc.name);
	}
};
