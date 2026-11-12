import { currentSession } from "@framework/ui";
import { dayjs } from "frappe-ui";
import { __ } from "frappe/i18n";

export default {
	onRefresh(page) {
		page.columns.update("first_used_on", {
			label: __("Status"),
			fields: ["expires_on"],
			badge: requestStatus,
		});
	},
};

function requestStatus(row) {
	if (row.first_used_on)
		return { label: __("Used"), theme: "green", filters: [["first_used_on", "is", "set"]] };
	const zone = currentSession()?.timezone;
	const now = zone ? dayjs().tz(zone) : dayjs();
	if (
		row.expires_on &&
		(zone ? dayjs.tz(row.expires_on, zone) : dayjs(row.expires_on)).isBefore(now)
	)
		return {
			label: __("Expired"),
			theme: "red",
			filters: [
				["first_used_on", "is", "not set"],
				["expires_on", "<", now.format("YYYY-MM-DD HH:mm:ss")],
			],
		};
	return { label: __("Not Used"), theme: "gray", filters: [["first_used_on", "is", "not set"]] };
}
