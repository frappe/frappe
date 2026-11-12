import { __ } from "frappe/i18n";

const LOGIN_THEMES = { Success: "green", Failed: "red" };

export default {
	onRefresh(page) {
		page.columns.update("status", {
			fields: ["operation"],
			badge: (row) =>
				row.operation === "Login" &&
				LOGIN_THEMES[row.status] && {
					label: __(row.status),
					theme: LOGIN_THEMES[row.status],
				},
		});
	},
};
