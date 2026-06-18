frappe.provide("frappe.ui");

frappe.ui.show_user_settings = async function (default_tab) {
	const { message: user_data } = await frappe.db.get_value("User", frappe.session.user, [
		"thread_notify",
		"send_me_a_copy",
		"email_signature",
		"language",
		"time_zone",
		"notifications",
		"search_bar",
		"mute_sounds",
		"list_sidebar",
		"bulk_actions",
		"view_switcher",
		"form_sidebar",
		"timeline",
		"dashboard",
		"show_absolute_datetime_in_timeline",
		"form_navigation_buttons",
	]);

	const d = new frappe.ui.SettingsDialog({
		title: __("Settings"),
		default_tab: default_tab || "profile",
		tabs: [
			{
				group: __("Settings"),
				items: [
					_profile_tab(),
					_email_tab(user_data || {}),
					_appearance_tab(),
					_preferences_tab(user_data || {}),
					_lists_tab(user_data || {}),
					_forms_tab(user_data || {}),
					_workspaces_tab(),
					_session_defaults_tab(),
					_keyboard_shortcuts_tab(),
				],
			},
		],
	});

	d.show();
};

// ─── helpers ──────────────────────────────────────────────────────────────────

function _save_user(fieldname_or_dict, value) {
	return frappe.db.set_value("User", frappe.session.user, fieldname_or_dict, value);
}

// FieldGroup doesn't expose df.on_change cleanly, so we bind manually.
// Called from render(), by which point panel.fieldgroup is already set.
function _bind_switch_autosave(panel, fieldnames) {
	fieldnames.forEach((fn) => {
		const ctrl = panel.fieldgroup.fields_dict[fn];
		if (!ctrl || !ctrl.$input) return;
		ctrl.$input.on("change", () => _save_user(fn, ctrl.get_value()));
	});
}

function _section_heading(title, description) {
	const desc = description
		? `<div class="settings-dialog-section-description">${description}</div>`
		: "";
	return `<div class="settings-dialog-section-heading">
		<div class="settings-dialog-section-title">${title}</div>
		${desc}
	</div>`;
}

// ─── Profile ──────────────────────────────────────────────────────────────────

function _profile_tab() {
	return {
		id: "profile",
		label: __("Profile"),
		icon: "user",
		title: __("Profile"),
		description: __("Your name, email and account settings."),
		render(panel) {
			const user = frappe.session.user;
			const full_name = frappe.user.full_name(user) || user;

			panel.body.html(`
				<div class="user-settings-profile-header">
					${frappe.avatar(user, "avatar-xl")}
					<div class="profile-user-info">
						<div class="profile-full-name">${frappe.utils.escape_html(full_name)}</div>
						<div class="profile-email">${frappe.utils.escape_html(user)}</div>
					</div>
				</div>
				<div class="user-settings-profile-actions">
					<button class="btn btn-sm btn-default change-password-btn">
						${frappe.utils.icon("lock", "xs")} ${__("Change Password")}
					</button>
					<button class="btn btn-sm btn-default configure-email-btn">
						${frappe.utils.icon("mail", "xs")} ${__("Emails & Signature")}
					</button>
				</div>
			`);

			panel.body.find(".change-password-btn").on("click", _show_change_password_dialog);
			panel.body.find(".configure-email-btn").on("click", () => panel.dialog.activate("email"));
		},
	};
}

function _show_change_password_dialog() {
	const d = new frappe.ui.Dialog({
		title: __("Change Password"),
		fields: [
			{ fieldtype: "Password", fieldname: "old_password", label: __("Current Password"), reqd: 1 },
			{ fieldtype: "Password", fieldname: "new_password", label: __("New Password"), reqd: 1 },
			{ fieldtype: "Password", fieldname: "confirm_password", label: __("Confirm New Password"), reqd: 1 },
		],
		primary_action_label: __("Update"),
		primary_action(values) {
			if (values.new_password !== values.confirm_password) {
				frappe.msgprint(__("Passwords do not match."));
				return;
			}
			frappe.call({
				method: "frappe.core.doctype.user.user.update_password",
				args: { new_password: values.new_password, old_password: values.old_password, logout_all_sessions: 0 },
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Password updated"), indicator: "green" });
						d.hide();
					}
				},
			});
		},
	});
	d.show();
}

// ─── Email ────────────────────────────────────────────────────────────────────

function _email_tab(user_data) {
	return {
		id: "email",
		label: __("Email"),
		icon: "mail",
		title: __("Email"),
		description: __("Notifications, outgoing email and signature settings."),
		fields: [
			{
				fieldtype: "Switch",
				fieldname: "thread_notify",
				label: __("Send Notifications For Email Threads"),
				default: user_data.thread_notify,
			},
			{
				fieldtype: "Switch",
				fieldname: "send_me_a_copy",
				label: __("Send Me A Copy of Outgoing Emails"),
				default: user_data.send_me_a_copy,
			},
			{ fieldtype: "Section Break", label: __("Email Signature") },
			{
				fieldtype: "Text Editor",
				fieldname: "email_signature",
				label: __("Email Signature"),
				hide_label: 1,
				default: user_data.email_signature || "",
			},
		],
		actions: [
			{
				label: __("Save"),
				primary: true,
				click(panel) {
					_save_user("email_signature", panel.get_value("email_signature")).then(() => {
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
					});
				},
			},
		],
		render(panel) {
			_bind_switch_autosave(panel, ["thread_notify", "send_me_a_copy"]);
		},
	};
}

// ─── Appearance ───────────────────────────────────────────────────────────────

function _appearance_tab() {
	return {
		id: "appearance",
		label: __("Appearance"),
		icon: "sun",
		title: __("Appearance"),
		description: __("Theme and layout preferences."),
		render(panel) {
			panel.body.append(_section_heading(__("Theme"), __("Switch between light, dark, or system theme")));

			// Reuse the existing theme switcher: instantiate it and move its
			// already-rendered grid into our panel. The unused hidden dialog
			// it creates is the price of not duplicating the theme markup.
			const theme_switcher = new frappe.ui.ThemeSwitcher();
			panel.body.append(theme_switcher.body);

			panel.body.append(_section_heading(__("Layout")));

			// Full Width comes after the theme grid, so we add it via add_fields
			// here rather than the declarative `fields` array (which renders first).
			const fg = panel.add_fields([
				{
					fieldtype: "Switch",
					fieldname: "full_width",
					label: __("Full Width"),
					description: __("Expand content to fill the full screen width"),
					default: JSON.parse(localStorage.container_fullwidth || "false") ? 1 : 0,
				},
			]);

			const ctrl = fg.fields_dict["full_width"];
			ctrl?.$input.on("change", () => {
				localStorage.container_fullwidth = ctrl.get_value() ? "true" : "false";
				frappe.ui.toolbar.set_fullwidth_if_enabled();
				$(document.body).trigger("toggleFullWidth");
			});
		},
	};
}

// ─── Preferences ──────────────────────────────────────────────────────────────

function _preferences_tab(user_data) {
	return {
		id: "preferences",
		label: __("Preferences"),
		icon: "settings",
		title: __("Preferences"),
		description: __("Language, timezone and notification preferences."),
		fields: [
			{ fieldtype: "Switch", fieldname: "notifications", label: __("Allow Notifications"), default: user_data.notifications },
			{ fieldtype: "Switch", fieldname: "search_bar", label: __("Show Search Bar"), default: user_data.search_bar },
			{ fieldtype: "Switch", fieldname: "mute_sounds", label: __("Mute Sounds"), default: user_data.mute_sounds },
			{ fieldtype: "Section Break", label: __("Locale") },
			{ fieldtype: "Link", fieldname: "language", label: __("Language"), options: "Language", default: user_data.language || "" },
			{ fieldtype: "Autocomplete", fieldname: "time_zone", label: __("Time Zone"), default: user_data.time_zone || "" },
		],
		actions: [
			{
				label: __("Save"),
				primary: true,
				click(panel) {
					const values = panel.get_values();
					if (!values) return;
					_save_user({ language: values.language, time_zone: values.time_zone }).then(() => {
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
					});
				},
			},
		],
		render(panel) {
			_bind_switch_autosave(panel, ["notifications", "search_bar", "mute_sounds"]);
		},
	};
}

// ─── Lists ────────────────────────────────────────────────────────────────────

function _lists_tab(user_data) {
	return {
		id: "lists",
		label: __("Lists"),
		icon: "list",
		title: __("Lists"),
		description: __("Configure list view behaviour."),
		fields: [
			{ fieldtype: "Switch", fieldname: "list_sidebar", label: __("Show Sidebar"), default: user_data.list_sidebar },
			{ fieldtype: "Switch", fieldname: "bulk_actions", label: __("Allow Bulk Actions"), default: user_data.bulk_actions },
			{ fieldtype: "Switch", fieldname: "view_switcher", label: __("Show View Switcher"), default: user_data.view_switcher },
		],
		render(panel) {
			_bind_switch_autosave(panel, ["list_sidebar", "bulk_actions", "view_switcher"]);
		},
	};
}

// ─── Forms ────────────────────────────────────────────────────────────────────

function _forms_tab(user_data) {
	return {
		id: "forms",
		label: __("Forms"),
		icon: "file",
		title: __("Forms"),
		description: __("Configure form view behaviour."),
		fields: [
			{ fieldtype: "Switch", fieldname: "form_sidebar", label: __("Show Sidebar"), default: user_data.form_sidebar },
			{ fieldtype: "Switch", fieldname: "timeline", label: __("Show Timeline"), default: user_data.timeline },
			{ fieldtype: "Switch", fieldname: "dashboard", label: __("Show Dashboard"), default: user_data.dashboard },
			{ fieldtype: "Switch", fieldname: "show_absolute_datetime_in_timeline", label: __("Show Absolute Datetime in Timeline"), default: user_data.show_absolute_datetime_in_timeline },
			{ fieldtype: "Switch", fieldname: "form_navigation_buttons", label: __("Show Navigation Buttons"), default: user_data.form_navigation_buttons },
		],
		render(panel) {
			_bind_switch_autosave(panel, [
				"form_sidebar",
				"timeline",
				"dashboard",
				"show_absolute_datetime_in_timeline",
				"form_navigation_buttons",
			]);
		},
	};
}

// ─── Workspaces ───────────────────────────────────────────────────────────────

function _workspaces_tab() {
	return {
		id: "workspaces",
		label: __("Workspaces"),
		icon: "layout-grid",
		title: __("Workspaces"),
		description: __("Manage your workspaces."),
	};
}

// ─── Session Defaults ─────────────────────────────────────────────────────────

function _session_defaults_tab() {
	const fields = frappe.boot.session_defaults || [];
	return {
		id: "session-defaults",
		label: __("Session Defaults"),
		icon: "sliders-horizontal",
		title: __("Session Defaults"),
		description: __("Set default values for the current session."),
		fields: fields.length ? [...fields] : undefined,
		actions: fields.length
			? [
					{
						label: __("Save"),
						primary: true,
						click(panel) {
							const values = panel.get_values();
							if (!values) return;
							fields.forEach((f) => {
								if (!values[f.fieldname]) values[f.fieldname] = "";
							});
							frappe.call({
								method: "frappe.core.doctype.session_default_settings.session_default_settings.set_session_default_values",
								args: { default_values: values },
								callback(data) {
									if (data.message === "success") {
										frappe.show_alert({ message: __("Session Defaults Saved"), indicator: "green" });
										frappe.ui.toolbar.clear_cache();
									} else {
										frappe.show_alert({ message: __("An error occurred while setting Session Defaults"), indicator: "red" });
									}
								},
							});
						},
					},
			  ]
			: undefined,
		render: fields.length
			? undefined
			: (panel) => {
					panel.body.html(`<div class="text-muted">${__("No session defaults configured.")}</div>`);
			  },
	};
}

// ─── Keyboard Shortcuts ───────────────────────────────────────────────────────

function _keyboard_shortcuts_tab() {
	return {
		id: "keyboard-shortcuts",
		label: __("Keyboard Shortcuts"),
		icon: "keyboard",
		title: __("Keyboard Shortcuts"),
		description: __("All available keyboard shortcuts."),
		render(panel) {
			const all_shortcuts = frappe.ui.keys.standard_shortcuts || [];
			const cur_page = window.cur_page?.page;

			const groups = [
				[__("Global Shortcuts"), (s) => !s.page],
				[__("Page Shortcuts"), (s) => s.page && s.page === cur_page?.page],
				[__("Grid Shortcuts"), (s) => s.page && s.page === cur_page?.frm],
			];

			groups.forEach(([heading, filter]) => {
				const deduped = [];
				const seen = {};
				all_shortcuts
					.filter(filter)
					.filter((s) => (s.condition ? s.condition() : true))
					.filter((s) => !!s.description)
					.forEach((s) => {
						if (seen[s.description] !== undefined) {
							deduped[seen[s.description]].keys.push(s.shortcut);
						} else {
							seen[s.description] = deduped.length;
							deduped.push({ ...s, keys: [s.shortcut] });
						}
					});
				if (!deduped.length) return;

				panel.body.append(_section_heading(heading));
				const rows = deduped
					.map((s) => {
						const key_html = s.keys
							.map((k) => `<kbd>${frappe.ui.keys.get_shortcut_label(k)}</kbd>`)
							.join(" / ");
						return `<tr><td width="40%">${key_html}</td><td width="60%">${s.description}</td></tr>`;
					})
					.join("");
				panel.body.append(
					`<table class="table table-bordered settings-shortcuts-table"><tbody>${rows}</tbody></table>`
				);
			});

			panel.body.append(
				`<div class="text-muted mt-3">${__("Press Alt Key to trigger additional shortcuts in Menu and Sidebar")}</div>`
			);
		},
	};
}
