// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// Common utility functions for logging doctypes.

frappe.provide("frappe.utils.logtypes");

frappe.utils.logtypes.show_log_retention_message = (doctype) => {
	if (!frappe.model.can_write("Log Settings")) {
		return;
	}

	const add_sidebar_message = (message) => {
		let sidebar_entry = $('<div class="sidebar-section></div>').appendTo(
			cur_list.page.sidebar
		);
		$(`<div>${message}</div>`).appendTo(sidebar_entry);
	};

	const log_settings_link = `<a href='/app/log-settings'>${__("Log Settings")}</a>`;
	const cta = __("You can change the retention policy from {0}.", [log_settings_link]);
	let message = __("{0} records are not automatically deleted.", [__(doctype)]);

	frappe.db
		.get_value("Logs To Clear", { ref_doctype: doctype }, "days", null, "Log Settings")
		.then((r) => {
			if (!r.exc && r.message && r.message.days) {
				message = __("{0} records are retained for {1} days.", [
					__(doctype),
					r.message.days,
				]);
			}
			add_sidebar_message(`${message} ${cta}`);
		});
};
