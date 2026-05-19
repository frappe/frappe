// User Status picker — opens a dialog to set/clear the current user's
// status. Operates only on `frappe.session.user` via the whitelisted
// endpoint `frappe.core.doctype.user.user.set_status`. There is no way to
// set another user's status through this UI.
//
// The status options come from the `User Status Type` doctype, fetched
// lazily on first open and cached for the session. Apps that install their
// own types show up here automatically.

frappe.provide("frappe.ui.toolbar");

frappe.ui.toolbar.USER_STATUS_DURATIONS = [
	{ label: __("Don't clear"), minutes: null },
	{ label: __("30 min"), minutes: 30 },
	{ label: __("1 hour"), minutes: 60 },
	{ label: __("4 hours"), minutes: 240 },
	{ label: __("Today"), minutes: "end_of_day" },
	{ label: __("This week"), minutes: "end_of_week" },
];

let _status_types_cache = null;

function _load_status_types() {
	if (_status_types_cache) {
		return Promise.resolve(_status_types_cache);
	}
	return frappe
		.xcall("frappe.core.doctype.user_status_type.user_status_type.get_status_types_for_picker")
		.then((types) => {
			_status_types_cache = types;
			return types;
		});
}

// Allow callers to invalidate the cache (e.g. when a Type was just created
// elsewhere in the same session).
frappe.ui.toolbar.invalidate_status_types_cache = function () {
	_status_types_cache = null;
};

frappe.ui.toolbar.show_user_status_picker = function () {
	_load_status_types().then((types) => {
		_show_dialog(types);
	});
};

function _show_dialog(types) {
	const current = frappe.user_info(frappe.session.user) || {};

	const option_lines = types.map((t) => `${t.label} (${t.master})`).join("\n");
	const label_by_option = {};
	for (const t of types) {
		label_by_option[`${t.label} (${t.master})`] = t.name;
	}

	const duration_options = frappe.ui.toolbar.USER_STATUS_DURATIONS.map((d) => d.label).join(
		"\n"
	);

	let default_option = "";
	if (current.user_status) {
		const matched = types.find((t) => t.name === current.user_status);
		if (matched) {
			default_option = `${matched.label} (${matched.master})`;
		}
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Set a status"),
		fields: [
			{
				fieldname: "status_option",
				fieldtype: "Select",
				label: __("Status"),
				options: option_lines,
				default: default_option,
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
			},
		],
		primary_action_label: __("Save"),
		primary_action: (values) => {
			const status_name = label_by_option[values.status_option] || null;
			const expires_at = _resolve_expiry(values);
			frappe
				.xcall("frappe.core.doctype.user.user.set_status", {
					status: status_name,
					expires_at: expires_at,
				})
				.then((result) => {
					frappe.update_user_info({
						[frappe.session.user]: {
							user_status: result.status,
							user_status_master: result.master,
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
							user_status_master: null,
							user_status_expires_at: null,
						},
					});
					frappe.show_alert({ message: __("Status cleared"), indicator: "green" });
					dialog.hide();
				});
		},
	});

	dialog.show();
}

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
		return moment().endOf("week").format("YYYY-MM-DD HH:mm:ss");
	}
	return moment(now).add(preset.minutes, "minutes").format("YYYY-MM-DD HH:mm:ss");
}
