// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// Refresh
// --------

frappe.ui.form.on('Custom Field', {
	setup: function(frm) {
		frm.set_query('dt', function(doc) {
			var filters = [
				['DocType', 'issingle', '=', 0],
				['DocType', 'custom', '=', 0],
				['DocType', 'name', 'not in', frappe.model.core_doctypes_list],
				['DocType', 'restrict_to_domain', 'in', frappe.boot.active_domains]
			];
			if(frappe.session.user!=="Administrator") {
				filters.push(['DocType', 'module', 'not in', ['Core', 'Custom']])
			}
			return {
				"filters": filters
			}
		});
	},
	refresh: function(frm) {
		frm.toggle_enable('dt', frm.doc.__islocal);
		frm.trigger('dt');
		frm.toggle_reqd('label', !frm.doc.fieldname);
	},
	dt: function(frm) {
		if(!frm.doc.dt) {
			set_field_options('insert_after', '');
			return;
		}
		var insert_after = frm.doc.insert_after || null;
		return frappe.call({
			method: 'frappe.custom.doctype.custom_field.custom_field.get_fields_label',
			args: { doctype: frm.doc.dt, fieldname: frm.doc.fieldname },
			callback: function(r) {
				if(r) {
					if(r._server_messages && r._server_messages.length) {
						frm.set_value("dt", "");
					} else {
						set_field_options('insert_after', r.message);
						var fieldnames = $.map(r.message, function(v) { return v.value; });

						if(insert_after==null || !in_list(fieldnames, insert_after)) {
							insert_after = fieldnames[-1];
						}

						frm.set_value('insert_after', insert_after);
					}
				}
			}
		});

	},
	label: function(frm) {
		if(frm.doc.label && frappe.utils.has_special_chars(frm.doc.label)) {
			frm.fields_dict['label_help'].disp_area.innerHTML =
				'<font color = "red">'+__('Special Characters are not allowed')+'</font>';
			frm.set_value('label', '');
		} else {
			frm.fields_dict['label_help'].disp_area.innerHTML = '';
		}
	},
	fieldtype: function(frm) {
		if(frm.doc.fieldtype == 'Link') {
			frm.fields_dict['options_help'].disp_area.innerHTML =
				__('Name of the Document Type (DocType) you want this field to be linked to. e.g. Customer');
		} else if(frm.doc.fieldtype == 'Select') {
			frm.fields_dict['options_help'].disp_area.innerHTML =
				__('Options for select. Each option on a new line.')+' '+__('e.g.:')+'<br>'+__('Option 1')+'<br>'+__('Option 2')+'<br>'+__('Option 3')+'<br>';
		} else if(frm.doc.fieldtype == 'Dynamic Link') {
			frm.fields_dict['options_help'].disp_area.innerHTML =
				__('Fieldname which will be the DocType for this link field.');
		} else {
			frm.fields_dict['options_help'].disp_area.innerHTML = '';
		}
	}
});


frappe.utils.has_special_chars = function(t) {
	var iChars = "!@#$%^&*()+=-[]\\\';,./{}|\":<>?";
	for (var i = 0; i < t.length; i++) {
		if (iChars.indexOf(t.charAt(i)) != -1) {
			return true;
		}
	}
	return false;
}
