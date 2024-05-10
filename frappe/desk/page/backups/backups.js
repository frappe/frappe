frappe.pages["backups"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Download Backups"),
		single_column: true,
	});

	page.add_inner_button(__("Set Number of Backups"), function () {
		frappe.set_route("Form", "System Settings");
	});

	page.add_inner_button(__("Download Files Backup"), function () {
		frappe.call({
			method: "frappe.desk.page.backups.backups.schedule_files_backup",
			args: { user_email: frappe.session.user_email },
		});
	});

	page.add_inner_button(__("Get Backup Encryption Key"), function () {
		if (frappe.user.has_role("System Manager")) {
			frappe.verify_password(function () {
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

	frappe.breadcrumbs.add("Setup");

	$(frappe.render_template("backups")).appendTo(page.body.addClass("no-border"));
};
