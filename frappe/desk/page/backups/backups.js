frappe.pages["backups"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Download Backups"),
		single_column: true,
	});

	page.add_inner_button(__("Set Number of Backups"), function () {
		frappe.set_route("Form", "System Settings").then(() => {
			cur_frm.scroll_to_field("backup_limit");
		});
	});

	page.add_inner_button(__("Download Files Backup"), function () {
		frappe.call({
			method: "frappe.desk.page.backups.backups.schedule_files_backup",
			args: { user_email: frappe.session.user_email },
		});
	});

	page.add_inner_button(__("Get Backup Encryption Key"), function () {
		if (frappe.user.has_role("System Manager")) {
			frappe.confirm_sensitive_action(function () {
				frappe.call({
					method: "frappe.utils.backups.get_backup_encryption_key",
					callback: function (r) {
						frappe.msgprint({
							title: __("Backup Encryption Key"),
							message: __(r.message),
							indicator: "blue",
						});
					},
				});
			});
		} else {
			frappe.msgprint({
				title: __("Error"),
				message: __("System Manager privileges required."),
				indicator: "red",
			});
		}
	});

	page.body.addClass("no-border");
};

frappe.pages["backups"].on_page_show = function (wrapper) {
	frappe.call("frappe.desk.page.backups.backups.get_backup_files").then((r) => {
		wrapper.page.body.html(frappe.render_template("backups", { files: r.message }));
	});
};
