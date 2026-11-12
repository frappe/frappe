import { __ } from "frappe/i18n";

const ERROR_LOG = "frappe.core.doctype.error_log.error_log";

export default {
	onRefresh(page) {
		const isSystemManager = (page) => page.roles.includes("System Manager");
		page.header.add({
			name: "clear_error_logs",
			label: __("Clear Error Logs"),
			when: isSystemManager,
			run: async (page) => {
				const sure = await page.dialog.danger({
					title: __("Clear Error Logs"),
					message: __("Delete every Error Log?"),
					confirmLabel: __("Clear"),
				});
				if (!sure) return;
				await page.call(`${ERROR_LOG}.clear_error_logs`);
				page.reload();
			},
		});
		page.header.add({
			name: "flush_error_logs",
			label: __("Flush Queued Error Logs"),
			when: isSystemManager,
			run: async (page) => {
				await page.call(`${ERROR_LOG}.flush_error_logs`);
				page.toast.success(__("Queued Error Logs flushed"));
				page.reload();
			},
		});
	},
};
