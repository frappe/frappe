frappe.provide('frappe.ui.form');

frappe.ui.form.quick_entry = function(doctype, success) {
	frappe.model.with_doctype(doctype, function() {
		var mandatory = $.map(frappe.get_meta(doctype).fields,
			function(d) { return (d.reqd || d.bold && !d.read_only) ? d : null });
		var meta = frappe.get_meta(doctype);

		var doc = frappe.model.get_new_doc(doctype, null, null, true);

		if(meta.quick_entry != 1) {
			frappe.set_route('Form', doctype, doc.name);
			return;
		}

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

		var set_defaults = function() {
			if(!dialog.default_fields) {
				dialog.default_fields = []
				$.each(dialog.fields_dict, function(fieldname, field) {
					field.doctype = doc.doctype;
					field.docname = doc.name;

					if(!is_null(doc[fieldname])) {
						dialog.default_fields.push([field, fieldname]);
					}
				});
			}

			dialog.default_fields.map(([field, fieldname]) => {
				field.set_input(doc[fieldname]);
			});
		}

		dialog.doc = doc;

		// refresh dependencies etc
		dialog.refresh();

		var save_doc = function(add_next = 0) {
			if(dialog.working) return;
			var data = dialog.get_values();

			if(data) {
				dialog.working = true;
				var values = update_doc();
				frappe.call({
					method: "frappe.client.insert",
					args: {
						doc: values
					},
					callback: function(r) {
						var doc = r.message;

						if(!add_next) {
							dialog.hide();
						} else {
							dialog.clear();
							dialog.focus_on_first_input();
							set_defaults();

							frappe.show_alert({message: __(doctype + " " + doc.name + " saved"),
								indicator: 'green'});
						}

						// delete the old doc
						frappe.model.clear_doc(dialog.doc.doctype, dialog.doc.name);
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
					freeze: add_next ? false : true
				});
			}
		}

		dialog.set_primary_action(__('Save'), function() {
			save_doc(0);
		});

		var $footer = $(`<div class="small quick-entry-footer" style="padding: 5px 10px;
				display: flex; align-items: baseline; justify-content: space-between;">
				<span>
					<span class="text-muted hidden-xs">${__("Ctrl+Enter to save, Ctrl+Shift+Enter to add next")} |</span>
					<a class="edit-full">${__("Edit in full page")}</a>
				</span>
				<button type="button" class="btn btn-default btn-sm add-next">Add Next</button>
			</div>`).appendTo(dialog.body);

		$footer.find('.edit-full').on('click', function() {
			// edit in form
			open_doc();
		});

		$footer.find('.add-next').on('click', function() {
			save_doc(1);
		});

		// ctrl+enter to save, ctrl+shift+enter to save and add next
		dialog.wrapper.keydown(function(e) {
			if((e.ctrlKey || e.metaKey) && e.which==13) {
				if(!frappe.request.ajax_count) {
					// not already working -- double entry
					if(!e.shiftKey) {
						dialog.get_primary_btn().trigger("click");
					} else {
						// ctrl+shift+enter to save and add next
						$footer.find('.add-next').trigger("click");
					}
					e.preventDefault();
					return false;
				}
			}
		});

		dialog.show();

		set_defaults();

	});
}
