// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Custom Link', {
	refresh: function(frm) {
		frm.set_query("document_type", function () {
			return {
				filters: {
					custom: 0,
					istable: 0,
					module: ['not in', ["Email", "Core", "Custom", "Event Streaming", "Social", "Data Migration", "Geo", "Desk"]]
				}
			};
		});

		frm.add_custom_button(__('Go to {0} List', [frm.doc.document_type]), function() {
			frappe.set_route('List', frm.doc.document_type);
		});
	}
});
