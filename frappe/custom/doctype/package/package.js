// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Package', {
	refresh: function(frm) {
		frappe.realtime.on("exporting_package", (data) => {
			if (data.progress !== (data.total-1)) {
				frm.dashboard.show_progress("Exporting", data.progress / data.total * 100, __("{0}", [data.message]));
			} else {
				frm.dashboard.hide_progress();
			}
		});

		frappe.realtime.on("importing_package", (data) => {
			if (data.progress !== (data.total-1)) {
				frm.dashboard.show_progress("Importing", data.progress / data.total * 100, __("{0}", [data.message]));
			} else {
				frm.dashboard.hide_progress();
			}
		});
	},
	export: function(frm) {
		frappe.call({
			method: 'frappe.custom.doctype.package.package.export_package',
			callback: function(r) {
				if (r.message) {
					const args = {
						cmd: 'frappe.custom.doctype.package.package.download_package',
						data: r.message.data
					};
					open_url_post(frappe.request.url, args, true);
				}
			}
		});
	},
	import: function(frm) {
		frappe.call({
			method: 'frappe.custom.doctype.package.package.import_package',
			callback: function() {
				frappe.msgprint(__("Package Imported."));
			}
		});
	}
});
