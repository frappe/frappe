import { __ } from "frappe/i18n";

const THEMES = { Active: "green", Disabled: "red", Completed: "blue" };

export default {
	onRefresh(page) {
		page.columns.update("status", {
			badge: (row) =>
				row.status && {
					label: __(row.status),
					theme: THEMES[row.status],
					filters: [["status", "=", row.status]],
				},
		});
	},
};
