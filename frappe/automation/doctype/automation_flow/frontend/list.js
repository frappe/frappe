import { __ } from "frappe/i18n";

export default {
	onRefresh(page) {
		page.columns.update("enabled", { switch: true });
		page.rowActions.add({
			name: "duplicate",
			label: __("Duplicate"),
			icon: "lucide-copy",
			right: "create",
			run: (page, row) => page.run("shell.frappe.duplicate_automation_flow", row.name),
		});
	},
};
