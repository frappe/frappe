nts.pages["backups"].on_page_load = function (wrapper) {
	var page = nts.ui.make_app_page({
		parent: wrapper,
		title: __("Download Backups"),
		single_column: true,
	});

	page.add_inner_button(__("Set Number of Backups"), function () {
		nts.set_route("Form", "System Settings").then(() => {
			cur_frm.scroll_to_field("backup_limit");
		});
	});

	page.add_inner_button(__("Download Files Backup"), function () {
		nts.call({
			method: "nts.desk.page.backups.backups.schedule_files_backup",
			args: { user_email: nts.session.user_email },
		});
	});

	page.add_inner_button(__("Get Backup Encryption Key"), function () {
		if (nts.user.has_role("System Manager")) {
			nts.verify_password(function () {
				nts.call({
					method: "nts.utils.backups.get_backup_encryption_key",
					callback: function (r) {
						nts.msgprint({
							title: __("Backup Encryption Key"),
							message: __(r.message),
							indicator: "blue",
						});
					},
				});
			});
		} else {
			nts.msgprint({
				title: __("Error"),
				message: __("System Manager privileges required."),
				indicator: "red",
			});
		}
	});

	nts.breadcrumbs.add("Setup");

	$(nts.render_template("backups")).appendTo(page.body.addClass("no-border"));
};
