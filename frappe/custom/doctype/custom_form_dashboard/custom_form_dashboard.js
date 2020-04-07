// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Custom Form Dashboard', {
	refresh: function(frm) {
		frm.set_query("document_type", function () {
			return {
				filters: {
					istable: 0,
					module: ['not in', ["Email", "Core", "Custom", "Event Streaming", "Social", "Data Migration",
						"Desk", "Geo", "Desk"]]
				}
			}
		});

		frm.set_query("document_type", "transactions", function () {
			return {
				filters: {
					istable: 0,
					module: ['not in', ["Email", "Core", "Custom", "Event Streaming", "Social", "Data Migration",
						"Desk", "Geo", "Desk"]]
				}
			}
		});
	},
	document_type: function(frm) {
		if (!frm.doc.document_type || !frm.doc.__islocal)
			return;

		frm.call("get_form_fields_and_dashboard_field", {doctype: frm.doc.document_type}).then((r) => {
			frm.set_value("custom", r.message.custom);

			if (r.message.fields) {
				frm.set_df_property("custom_fieldname", "options", r.message.fields);
				frm.set_df_property("custom_fieldname", "reqd", 1);
			}

			if (r.message.fieldname) {
				frm.set_value("fieldname", r.message.fieldname);
			}
		});
	},
});
