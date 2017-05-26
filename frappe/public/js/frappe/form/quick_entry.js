frappe.provide('frappe.ui.form');

frappe.ui.form.quick_entry = function(doctype, success, fields_map={}) {
	frappe.model.with_doctype(doctype, function() {
		var mandatory = [];

		if (!fields_map == {}) {
			$.each(fields_map, function(k,v) {
				doc_field = frappe.meta.get_docfield(doctype, k)
				mandatory.push(doc_field);
			});
		} else {
			mandatory = $.map(frappe.get_meta(doctype).fields,
			function(d) { return (d.reqd || d.bold && !d.read_only) ? d : null });
		}

		var meta = frappe.get_meta(doctype);
		var doc = frappe.model.get_new_doc(doctype, null, null, true);

		if(meta.quick_entry != 1 || mandatory.length > 7 || $.map(mandatory, function(d) { return d.fieldtype==='Table' ? d : null }).length) {
			var d = frappe.model.make_new_doc_and_get_name(doctype);
			d = locals[doctype][d];

			$.each(fields_map, function(fieldname, fieldvalue) {
				d[fieldname] = fieldvalue;
			});

			frappe.set_route('Form', doctype, d.name);
			return;
		}

		if(meta.autoname && meta.autoname.toLowerCase()==='prompt') {
			mandatory = [{fieldname:'__name', label:__('{0} Name', [meta.name]),
				reqd: 1, fieldtype:'Data'}].concat(mandatory);
		}

		var dialog = new frappe.ui.Dialog({
			title: __("New {0}", [__(doctype)]),
			fields: mandatory,
		});

		var update_doc = function() {
			var data = dialog.get_values(true);
			$.each(data, function(key, value) {
				if(key==='__name') {
					dialog.doc.name = value;
				} else {
					if(!is_null(value)) {
						dialog.doc[key] = value;
					}
				}
			});
			return dialog.doc;
		}

		var open_doc = function() {
			dialog.hide();
			update_doc();
			frappe.set_route('Form', doctype, doc.name);
		}

		dialog.doc = doc;

		// refresh dependencies etc
		dialog.refresh();

		dialog.set_primary_action(__('Save'), function() {
			if(dialog.working) return;
			var data = dialog.get_values();

			if(data) {
				dialog.working = true;
				values = update_doc();
				frappe.call({
					method: "frappe.client.insert",
					args: {
						doc: values
					},
					callback: function(r) {
						dialog.hide();
						// delete the old doc
						frappe.model.clear_doc(dialog.doc.doctype, dialog.doc.name);
						var doc = r.message;
						if(success) {
							success(doc);
						}
						frappe.ui.form.update_calling_link(doc.name);
					},
					error: function() {
						open_doc();
					},
					always: function() {
						dialog.working = false;
					},
					freeze: true
				});
			}
		});

		var $link = $('<div class="text-muted small" style="padding-left: 10px; padding-top: 15px;">' +
			__("Ctrl+enter to save") + ' | <a class="edit-full">' + __("Edit in full page") + '</a></div>').appendTo(dialog.body);

		$link.find('.edit-full').on('click', function() {
			// edit in form
			open_doc();
		});

		// ctrl+enter to save
		dialog.wrapper.keydown(function(e) {
			if((e.ctrlKey || e.metaKey) && e.which==13) {
				if(!frappe.request.ajax_count) {
					// not already working -- double entry
					dialog.get_primary_btn().trigger("click");
					e.preventDefault();
					return false;
				}
			}
		});

		dialog.show();

		//Set value and visibility if field map exists.
		if (fields_map != {}) {
			$.each(dialog.fields_dict, function(fieldname, field) {
				field.set_input(fields_map[fieldname]);
			});
		} else {
			// set defaults
			$.each(dialog.fields_dict, function(fieldname, field) {
				field.doctype = doc.doctype;
				field.docname = doc.name;
				if(!is_null(doc[fieldname])) {
					field.set_input(doc[fieldname]);
				}
			});
		}
	});
}
