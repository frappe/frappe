frappe.provide('frappe.ui.form');

frappe.ui.form.quick_entry = function(doctype, success) {
	frappe.model.with_doctype(doctype, function() {
		var mandatory = $.map(frappe.get_meta(doctype).fields,
			function(d) { return (d.reqd || d.bold) ? d : null });

		var doc = frappe.model.get_new_doc(doctype);

		if(mandatory.length > 7) {
			// too many fields, show form
			frappe.set_route('Form', doctype, doc.name);
			return;
		}

		if($.map(mandatory, function(d) { return d.fieldtype==='Table' ? d : null }).length) {
			// has mandatory table, quit!
			frappe.set_route('Form', doctype, doc.name);
			return;
		}


		var dialog = new frappe.ui.Dialog({
			title: __("New {0}", [doctype]),
			fields: mandatory,
		});

		var update_doc = function() {
			values = dialog.get_values(true);
			$.each(values, function(key, value) {
				if(value) {
					dialog.doc[key] = value;
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

		// set defaults
		mandatory.forEach(function(df) {
			var field = dialog.get_field(df.fieldname);
			field.doctype = doc.doctype;
			field.docname = doc.name;
			if(doc[df.fieldname]) {
				field.set_value(doc[df.fieldname]);
			}
		});

		dialog.set_primary_action(__('Save'), function() {
			var values = dialog.get_values();

			if(values) {
				values = update_doc();
				frappe.call({
					method: "frappe.client.insert",
					args: {
						doc: values
					},
					callback: function(r) {
						dialog.hide();
						var doc = r.message;
						if(success) success(doc);
					},
					error: function() {
						open_doc();
					},
					freeze: true
				});
			}
		});

		var $link = $('<div class="text-muted small" style="padding-left: 10px; padding-top: 15px;">\
			Ctrl+enter to save | <a class="edit-full">Edit in full page</a></div>').appendTo(dialog.body);

		$link.find('.edit-full').on('click', function() {
			// edit in form
			open_doc();
		});

		// ctrl+enter to save
		dialog.wrapper.keydown("meta+return ctrl+return", function(e) {
			if(!frappe.request.ajax_count) {
				// not already working -- double entry
				dialog.get_primary_btn().trigger("click");
			}
		});

		dialog.show();
	});
}