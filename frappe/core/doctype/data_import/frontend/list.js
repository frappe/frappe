import { __ } from "frappe/i18n";

const STATUS_THEMES = {
	Pending: "orange",
	"Partial Success": "orange",
	Success: "green",
	"In Progress": "orange",
	Error: "red",
	"Timed Out": "orange",
};

export default {
	onRefresh(page) {
		page.columns.update("status", {
			badge: (row) =>
				row.status && {
					label: __(row.status),
					theme: STATUS_THEMES[row.status],
					filters: [["status", "=", row.status]],
				},
		});
	},
};
