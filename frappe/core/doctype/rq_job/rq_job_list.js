frappe.listview_settings["RQ Job"] = {
	hide_name_column: true,

	onload(listview) {
		if (!has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;

		listview.page.add_inner_button(__("Remove Failed Jobs"), () => {
			frappe.confirm(__("Are you sure you want to remove all failed jobs?"), () => {
				frappe.xcall("frappe.core.doctype.rq_job.rq_job.remove_failed_jobs");
			});
		});

		if (listview.list_view_settings) {
			listview.list_view_settings.disable_count = 1;
			listview.list_view_settings.disable_sidebar_stats = 1;
		}

		frappe.xcall("frappe.utils.scheduler.get_scheduler_status").then(({ status }) => {
			if (status === "active") {
				listview.page.set_indicator(__("Scheduler: Active"), "green");
			} else {
				listview.page.set_indicator(__("Scheduler: Inactive"), "red");
			}
		});

		setInterval(() => {
			if (!listview.list_view_settings.disable_auto_refresh) {
				listview.refresh();
			}
		}, 5000);
	},
};
