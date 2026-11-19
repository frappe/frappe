import { __ } from "frappe/i18n";

export default {
	onRefresh(page) {
		page.header.add({
			name: "remove_failed_jobs",
			label: __("Remove Failed Jobs"),
			when: (page) => page.roles.includes("System Manager"),
			run: async (page) => {
				const sure = await page.dialog.danger({
					title: __("Remove Failed Jobs"),
					message: __("Are you sure you want to remove all failed jobs?"),
					confirmLabel: __("Remove"),
				});
				if (!sure) return;
				await page.call("frappe.core.doctype.rq_job.rq_job.remove_failed_jobs");
				page.reload();
			},
		});
	},
};
