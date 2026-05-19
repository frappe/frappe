// User Status picker — opens a dialog to set/clear the current user's status.
// Operates only on `frappe.session.user` via the whitelisted endpoint
// `frappe.core.doctype.user.user.set_status`. No way to set another user's
// status through this UI.

frappe.provide("frappe.ui.toolbar");

frappe.ui.toolbar.USER_STATUS_OPTIONS = [
	{ value: "Available", color: "var(--green-500)" },
	{ value: "Away", color: "var(--yellow-500)" },
	{ value: "Busy", color: "var(--red-500)" },
	{ value: "Do Not Disturb", color: "var(--red-700)" },
	{ value: "Out of Office", color: "var(--purple-500)" },
	{ value: "Invisible", color: "var(--gray-500)" },
];

frappe.ui.toolbar.USER_STATUS_DURATIONS = [
	{ label: __("Don't clear"), minutes: null },
	{ label: __("30 min"), minutes: 30 },
	{ label: __("1 hour"), minutes: 60 },
	{ label: __("4 hours"), minutes: 240 },
	{ label: __("Today"), minutes: "end_of_day" },
	{ label: __("This week"), minutes: "end_of_week" },
];

frappe.ui.toolbar.show_user_status_picker = function () {
	const current = frappe.user_info(frappe.session.user) || {};

	const status_options = frappe.ui.toolbar.USER_STATUS_OPTIONS.map((o) => o.value).join("\n");
	const duration_options = frappe.ui.toolbar.USER_STATUS_DURATIONS.map((d) => d.label).join(
		"\n"
	);

	const dialog = new frappe.ui.Dialog({
		title: __("Set a status"),
		fields: [
			{
				fieldname: "status",
				fieldtype: "Select",
				label: __("Status"),
				options: status_options,
				default: current.user_status || "Available",
				reqd: 0,
			},
			{
				fieldname: "duration_preset",
				fieldtype: "Select",
				label: __("Clear after"),
				options: duration_options,
				default: __("Don't clear"),
			},
			{
				fieldname: "expires_at",
				fieldtype: "Datetime",
				label: __("Or pick a date/time"),
				depends_on: 'eval:doc.duration_preset === "' + __("Don't clear") + '"',
			},
		],
		primary_action_label: __("Save"),
		primary_action: (values) => {
			const expires_at = _resolve_expiry(values);
			frappe
				.xcall("frappe.core.doctype.user.user.set_status", {
					status: values.status || null,
					expires_at: expires_at,
				})
				.then((result) => {
					frappe.update_user_info({
						[frappe.session.user]: {
							user_status: result.status,
							user_status_expires_at: result.expires_at,
						},
					});
					frappe.show_alert({
						message: result.status
							? __("Status set to {0}", [__(result.status)])
							: __("Status cleared"),
						indicator: "green",
					});
					dialog.hide();
				});
		},
		secondary_action_label: __("Clear status"),
		secondary_action: () => {
			frappe
				.xcall("frappe.core.doctype.user.user.set_status", {
					status: null,
					expires_at: null,
				})
				.then(() => {
					frappe.update_user_info({
						[frappe.session.user]: {
							user_status: null,
							user_status_expires_at: null,
						},
					});
					frappe.show_alert({ message: __("Status cleared"), indicator: "green" });
					dialog.hide();
				});
		},
	});

	dialog.show();
};

function _resolve_expiry(values) {
	if (values.expires_at) {
		return values.expires_at;
	}
	const preset = frappe.ui.toolbar.USER_STATUS_DURATIONS.find(
		(d) => d.label === values.duration_preset
	);
	if (!preset || preset.minutes == null) {
		return null;
	}
	const now = frappe.datetime.now_datetime();
	if (preset.minutes === "end_of_day") {
		return frappe.datetime.get_today() + " 23:59:59";
	}
	if (preset.minutes === "end_of_week") {
		const m = moment().endOf("week");
		return m.format("YYYY-MM-DD HH:mm:ss");
	}
	return moment(now).add(preset.minutes, "minutes").format("YYYY-MM-DD HH:mm:ss");
}
