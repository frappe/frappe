import { __ } from "frappe/i18n";

export default {
	onRefresh(page) {
		page.columns.update("user", {
			badge: (row) =>
				!row.user && {
					label: __("Site"),
					theme: "blue",
					filters: [["user", "is", "not set"]],
				},
		});
	},
};
