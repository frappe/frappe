// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Manage Customization', {
	refresh: function(frm) {
		frappe.realtime.on("exporting_progress", (data) => {
			if (data.progress !== data.total) {
				frm.dashboard.show_progress("Exporting", data.progress / data.total * 100, __("{0}", [data.message]));
			} else {
				frm.dashboard.hide_progress();
			}
		});

		frappe.realtime.on("importing_progress", (data) => {
			if (data.progress !== data.total) {
				frm.dashboard.show_progress("Importing", data.progress / data.total * 100, __("{0}", [data.message]));
			} else {
				frm.dashboard.hide_progress();
			}
		});
	},
	export: function(frm) {
		frappe.call({
			method: 'frappe.custom.doctype.manage_customization.manage_customization.export_customizations',
			callback: function(r) {
				if (r.message) {
					const args = {
						cmd: 'frappe.custom.doctype.manage_customization.manage_customization.export_customizations',
						data: r.message.data
					};
					open_url_post(frappe.request.url, args);
				}
			}
		});
	},
	import: function(frm) {
		frappe.call({
			method: 'frappe.custom.doctype.manage_customization.manage_customization.import_customizations',
			callback: function(r) {
				if (r.message) {
					console.log("done")
				}
			}
		});
	}
});
