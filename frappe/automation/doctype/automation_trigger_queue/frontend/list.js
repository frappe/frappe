import { currentSession } from "@framework/ui";
import { dayjs } from "frappe-ui";
import { __ } from "frappe/i18n";

// v1 drew Scheduled purple; a badge has no purple theme.
const THEMES = {
	Pending: "orange",
	Scheduled: "blue",
	Running: "blue",
	Done: "green",
	Failed: "red",
	Skipped: "gray",
};

export default {
	onRefresh(page) {
		page.columns.update("status", {
			fields: ["run_after"],
			badge: (row) =>
				row.status && {
					label: statusLabel(row),
					theme: THEMES[row.status],
					filters: [["status", "=", row.status]],
				},
		});
	},
};

function statusLabel(row) {
	if (row.status !== "Scheduled" || !row.run_after) return __(row.status);
	const zone = currentSession()?.timezone;
	const runAfter = (zone ? dayjs.tz(row.run_after, zone) : dayjs(row.run_after)).toDate();
	const when = runAfter.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
	return __("Scheduled for {0}", [when]);
}
