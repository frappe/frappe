frappe.provide("frappe.ui");

frappe.ui.show_user_settings = async function (default_tab) {
	if (!frappe.all_timezones) {
		const { message } = await frappe.call("frappe.core.doctype.user.user.get_timezones");
		frappe.all_timezones = message.timezones;
	}

	const { message: user_data } = await frappe.db.get_value("User", frappe.session.user, [
		"first_name",
		"middle_name",
		"last_name",
		"username",
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
					_profile_tab(user_data || {}),
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

function _profile_tab(user_data) {
	return {
		id: "profile",
		label: __("Profile"),
		icon: "user",
		title: __("Profile"),
		description: __("Your name, email and account settings."),
		actions: [
			{
				label: __("Save"),
				primary: true,
				click(panel) {
					const values = panel.get_values();
					if (!values) return;
					_save_user({
						first_name: values.first_name,
						middle_name: values.middle_name,
						last_name: values.last_name,
						username: values.username,
					}).then(() => {
						Object.assign(user_data, {
							first_name: values.first_name,
							middle_name: values.middle_name,
							last_name: values.last_name,
							username: values.username,
						});
						const fn = [values.first_name, values.middle_name, values.last_name]
							.filter(Boolean)
							.join(" ");
						if (frappe.boot.user_info?.[frappe.session.user]) {
							frappe.boot.user_info[frappe.session.user].fullname =
								fn || frappe.session.user;
						}
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
						panel.refresh();
					});
				},
			},
		],
		render(panel) {
			const user = frappe.session.user;
			const full_name = frappe.user_info(user).fullname || user;
			const email = frappe.session.user_email || user;

			panel.body.html(`
				<div class="user-settings-profile-header">
					<div class="profile-avatar-upload" title="${__("Upload Photo")}">
						${frappe.avatar(user, "avatar-large")}
						<div class="profile-avatar-overlay">${frappe.utils.icon("camera", "md")}</div>
					</div>
					<div class="profile-user-info">
						<div class="profile-full-name">${frappe.utils.escape_html(full_name)}</div>
						<div class="profile-email">${frappe.utils.escape_html(email)}</div>
					</div>
					<button class="btn btn-sm btn-default change-password-btn">
						${frappe.utils.icon("lock", "xs")} ${__("Change Password")}
					</button>
				</div>
			`);

			panel.add_fields([
				{
					fieldtype: "Data",
					fieldname: "first_name",
					label: __("First Name"),
					reqd: 1,
					default: user_data.first_name || "",
				},
				{ fieldtype: "Column Break" },
				{
					fieldtype: "Data",
					fieldname: "middle_name",
					label: __("Middle Name"),
					default: user_data.middle_name || "",
				},
				{ fieldtype: "Section Break" },
				{
					fieldtype: "Data",
					fieldname: "last_name",
					label: __("Last Name"),
					default: user_data.last_name || "",
				},
				{ fieldtype: "Column Break" },
				{
					fieldtype: "Data",
					fieldname: "username",
					label: __("Username"),
					default: user_data.username || "",
				},
			]);

			panel.body
				.find(".profile-avatar-upload")
				.on("click", () => _upload_user_image(user, panel));
			panel.body
				.find(".change-password-btn")
				.on("click", () => frappe.ui.show_change_password_dialog(user));
		},
	};
}

function _upload_user_image(user, panel) {
	new frappe.ui.FileUploader({
		doctype: "User",
		docname: user,
		fieldname: "user_image",
		allow_multiple: false,
		restrictions: {
			allowed_file_types: ["image/*"],
		},
		on_success: (file) => {
			if (frappe.boot.user_info?.[user]) {
				frappe.boot.user_info[user].image = file.file_url;
			}
			panel.refresh();
		},
	});
}

// ─── Email ────────────────────────────────────────────────────────────────────

function _email_tab(user_data) {
	return {
		id: "email",
		label: __("Email"),
		icon: "mail",
		title: __("Email"),
		description: __("Configure your email settings"),
		fields: [
			{
				fieldtype: "Switch",
				fieldname: "thread_notify",
				label: __("Send Notifications For Email Threads"),
				description: __(
					"Get notified when there's a new reply in an email thread you're part of."
				),
				default: user_data.thread_notify,
			},
			{
				fieldtype: "Switch",
				fieldname: "send_me_a_copy",
				label: __("Send Me A Copy of Outgoing Emails"),
				description: __("Receive a copy of every email you send in your inbox."),
				default: user_data.send_me_a_copy,
			},
			{ fieldtype: "Section Break", label: __("Email Signature") },
			{
				fieldtype: "Text Editor",
				fieldname: "email_signature",
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
			panel.body.append(
				_section_heading(__("Theme"), __("Switch between light, dark, or system theme"))
			);

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
			{
				fieldtype: "Switch",
				fieldname: "notifications",
				label: __("Allow Notifications"),
				description: __(
					"Show desktop and in-app notifications for activity on your account."
				),
				default: user_data.notifications,
			},
			{
				fieldtype: "Switch",
				fieldname: "search_bar",
				label: __("Show Search Bar"),
				description: __("Display the search bar in the navigation area for quick access."),
				default: user_data.search_bar,
			},
			{
				fieldtype: "Switch",
				fieldname: "mute_sounds",
				label: __("Mute Sounds"),
				description: __(
					"Disable all notification and alert sounds across the application."
				),
				default: user_data.mute_sounds,
			},
		],
		render(panel) {
			_bind_switch_autosave(panel, ["notifications", "search_bar", "mute_sounds"]);

			panel.body.append(_section_heading(__("Locale")));

			const $lang = _add_preference_row(panel.body, {
				label: __("Language"),
				value: user_data.language,
				button_label: __("Change Language"),
				onClick() {
					_change_user_field({
						field: {
							fieldtype: "Link",
							fieldname: "language",
							label: __("Language"),
							options: "Language",
							default: user_data.language,
							reqd: 1,
						},
						title: __("Change Language"),
						on_save(value) {
							user_data.language = value;
							_set_language_label($lang, value);
						},
					});
				},
			});
			_set_language_label($lang, user_data.language);

			const $tz = _add_preference_row(panel.body, {
				label: __("Time Zone"),
				value: user_data.time_zone,
				button_label: __("Change Time Zone"),
				onClick() {
					_change_user_field({
						field: {
							fieldtype: "Autocomplete",
							fieldname: "time_zone",
							label: __("Time Zone"),
							options: frappe.all_timezones,
							default: user_data.time_zone,
							reqd: 1,
						},
						title: __("Change Time Zone"),
						on_save(value) {
							user_data.time_zone = value;
							$tz.find(".preference-value").text(value || "");
						},
					});
				},
			});
		},
	};
}

function _add_preference_row(parent, { label, value, button_label, onClick }) {
	const $row = $(`
		<div class="preference-row">
			<div>
				<div class="preference-label">${label}</div>
				<div class="preference-value">${frappe.utils.escape_html(value || "")}</div>
			</div>
			<button class="btn btn-sm btn-default">${button_label}</button>
		</div>
	`);
	$row.find("button").on("click", onClick);
	parent.append($row);
	return $row;
}

function _set_language_label($row, code) {
	if (!code) {
		$row.find(".preference-value").text("");
		return;
	}
	frappe.db.get_value("Language", code, "language_name").then((r) => {
		$row.find(".preference-value").text(r.message?.language_name || code);
	});
}

function _change_user_field({ field, title, on_save }) {
	const dialog = new frappe.ui.Dialog({
		title,
		fields: [field],
		primary_action_label: __("Save"),
		primary_action(values) {
			const new_value = values[field.fieldname];
			return _save_user(field.fieldname, new_value).then(() => {
				frappe.show_alert({
					message: __("Saved. Refresh to see changes."),
					indicator: "green",
				});
				on_save(new_value);
				dialog.hide();
			});
		},
	});
	dialog.show();
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
			{
				fieldtype: "Switch",
				fieldname: "list_sidebar",
				label: __("Show Sidebar"),
				description: __("Display the filter and group-by sidebar in list views."),
				default: user_data.list_sidebar,
			},
			{
				fieldtype: "Switch",
				fieldname: "bulk_actions",
				label: __("Allow Bulk Actions"),
				description: __(
					"Enable checkboxes to select multiple records and perform bulk operations."
				),
				default: user_data.bulk_actions,
			},
			{
				fieldtype: "Switch",
				fieldname: "view_switcher",
				label: __("Show View Switcher"),
				description: __(
					"Show the toolbar to switch between List, Kanban, Report and other views."
				),
				default: user_data.view_switcher,
			},
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
			{
				fieldtype: "Switch",
				fieldname: "form_sidebar",
				label: __("Show Sidebar"),
				description: __(
					"Display the attachments, comments and connections sidebar in forms."
				),
				default: user_data.form_sidebar,
			},
			{
				fieldtype: "Switch",
				fieldname: "timeline",
				label: __("Show Timeline"),
				description: __("Show the activity timeline with comments, emails and history."),
				default: user_data.timeline,
			},
			{
				fieldtype: "Switch",
				fieldname: "dashboard",
				label: __("Show Dashboard"),
				description: __(
					"Show the summary dashboard with charts and statistics at the top of forms."
				),
				default: user_data.dashboard,
			},
			{
				fieldtype: "Switch",
				fieldname: "show_absolute_datetime_in_timeline",
				label: __("Show Absolute Datetime in Timeline"),
				description: __(
					"Display exact timestamps instead of relative time in the activity timeline."
				),
				default: user_data.show_absolute_datetime_in_timeline,
			},
			{
				fieldtype: "Switch",
				fieldname: "form_navigation_buttons",
				label: __("Show Navigation Buttons"),
				description: __("Show previous and next navigation buttons in the form toolbar."),
				default: user_data.form_navigation_buttons,
			},
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
										frappe.show_alert({
											message: __("Session Defaults Saved"),
											indicator: "green",
										});
										frappe.ui.toolbar.clear_cache();
									} else {
										frappe.show_alert({
											message: __(
												"An error occurred while setting Session Defaults"
											),
											indicator: "red",
										});
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
					panel.body.html(
						`<div class="text-muted">${__("No session defaults configured.")}</div>`
					);
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
				`<div class="text-muted mt-3">${__(
					"Press Alt Key to trigger additional shortcuts in Menu and Sidebar"
				)}</div>`
			);
		},
	};
}
