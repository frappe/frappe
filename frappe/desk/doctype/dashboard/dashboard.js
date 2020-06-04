// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dashboard', {
	refresh: function(frm) {
		frm.add_custom_button(__("Show Dashboard"), () => frappe.set_route('dashboard', frm.doc.name));

		if (!frappe.boot.developer_mode) {
			frm.disable_form();
		} else {
			frm.add_custom_button(__("Export"), () => {
				frappe.call({
					method: 'frappe.desk.doctype.dashboard.dashboard.export_dashboard',
					freeze: true,
					args: {
						doc: frm.doc
					}
				});
			});
		}

		frm.set_query("chart", "charts", function() {
			return {
				filters: {
					is_public: 1
				}
			};
		});

		frm.set_query("card", "cards", function() {
			return {
				filters: {
					is_public: 1
				}
			};
		});
	}
});
