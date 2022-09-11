frappe.listview_settings["RQ Job"] = {
	hide_name_column: true,

	refresh(listview) {
		if (!has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;

		listview.page.add_inner_button(__("Remove Failed Jobs"), () => {
			frappe.confirm(__("Are you sure you want to remove all failed jobs?"), () => {
				frappe.xcall("frappe.core.doctype.rq_job.rq_job.remove_failed_jobs");
			});
		});
	},
};
