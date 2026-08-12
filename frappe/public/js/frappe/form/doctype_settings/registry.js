frappe.provide("frappe.doctype_settings");

/**
 * Tab registry for the DocType Settings dialog.
 *
 * A tab module registers a builder for its id with
 * `frappe.doctype_settings.register(id, builder)`. The builder is
 * `function(panel, doctype)` and receives a `frappe.ui.SettingsDialogPanel`
 * (see settings_dialog.js) plus the doctype the dialog was opened for.
 *
 * `groups` is the sidebar layout — ordered groups of tab items. Items whose
 * builder has not been registered are skipped when the dialog is built, so the
 * remaining tabs (workflow, notifications, email template, permissions, data
 * import) can be rolled out incrementally without touching this file's order.
 *
 * An item may carry an optional `condition()` predicate; when it returns false
 * the tab is hidden (e.g. Permissions, which is System-Manager-only).
 */
frappe.doctype_settings.builders = {};

frappe.doctype_settings.register = function (tab_id, builder) {
	frappe.doctype_settings.builders[tab_id] = builder;
};

frappe.doctype_settings.get_list = function (doctype, args) {
	args = Object.assign({ fields: ["name"], limit: 20 }, args, { doctype });
	return frappe
		.call({ method: "frappe.desk.reportview.get_list", args, type: "GET" })
		.then((r) => r.message);
};

/**
 * Shared overflow "…" menu used by list rows and custom tabs, built on the
 * espresso Dropdown component (open/close, positioning, keyboard handling all
 * come from it).
 *
 * `items`: [{ label, icon, danger, onclick() }] — falsy entries are skipped.
 * Returns the actions cell ($div) ready to append to a row. Callers that need a
 * controller/row in the handler should bind it into `onclick` themselves.
 */
frappe.doctype_settings.overflow_menu = function (items) {
	items = (items || []).filter(Boolean);
	const $cell = $('<div class="dts-list-cell dts-list-cell-actions"></div>');
	if (!items.length) return $cell;

	frappe.ui
		.dropdown({
			button: {
				label: "",
				icon: "ellipsis",
				size: "xs",
				variant: "ghost",
				title: __("More actions"),
			},
			align: "end",
			options: items.map((item) => ({
				label: item.label,
				icon: item.icon,
				theme: item.danger ? "red" : undefined,
				onclick: () => item.onclick(),
			})),
		})
		.appendTo($cell);

	return $cell;
};

// Shared loading placeholder: a few skeleton lines instead of bare "Loading" text.
// Layout via utility classes — no custom CSS.
frappe.doctype_settings.render_loading = function ($container) {
	const $wrap = $('<div class="flex flex-col gap-3 py-4"></div>').attr(
		"aria-label",
		__("Loading")
	);
	["40%", "70%", "55%"].forEach((width) => {
		$wrap.append(frappe.ui.skeleton({ width, height: "14px" }));
	});
	return $wrap.appendTo($container);
};

/**
 * Shared empty state — thin wrapper over frappe.ui.empty_state so every
 * settings tab gets the standard component. Same signature as before, so
 * callers don't change; its single `action` maps to the component's actions
 * array. Renders into `$container` (cleared by the caller).
 * `opts`: { icon, title, description, action: { label, onclick() } }.
 */
frappe.doctype_settings.empty_state = function ($container, opts) {
	opts = opts || {};
	const actions = opts.action
		? [{ label: opts.action.label, variant: "subtle", onclick: () => opts.action.onclick() }]
		: [];
	const $empty = frappe.ui.empty_state({
		icon: opts.icon || "list",
		title: opts.title || __("Nothing here yet"),
		description: opts.description,
		actions,
	});
	$empty.appendTo($container);
	return $empty;
};

frappe.doctype_settings.section = function ($parent, { title, description } = {}) {
	const $section = $('<div class="dts-section"></div>').appendTo($parent);
	const $header = $(`
		<div class="flex justify-between items-start gap-4 mb-4">
			<div class="flex flex-col gap-1 w-full min-w-0">
				<div class="dts-section-title text-xl-semibold"></div>
				<div class="dts-section-description text-base text-ink-gray-6"></div>
			</div>
			<div class="dts-section-actions flex items-center gap-2 shrink-0"></div>
		</div>
	`).appendTo($section);
	$header.find(".dts-section-title").text(title || "");
	const $desc = $header.find(".dts-section-description");
	description ? $desc.text(description) : $desc.remove();
	const $body = $('<div class="dts-section-body"></div>').appendTo($section);
	return { $section, $body, $actions: $header.find(".dts-section-actions") };
};

frappe.doctype_settings.render_error = function (panel, retry_fn, err) {
	if (frappe.doctype_settings.is_permission_error(err)) {
		panel.body.empty();
		frappe.doctype_settings.empty_state(panel.body, {
			icon: "lock",
			title: __("No access"),
			description: __("You don't have permission to view this."),
		});
		return;
	}
	const $err = panel.body.empty();
	$('<div class="text-ink-gray-5 text-p-sm"></div>')
		.text(__("Could not load this tab."))
		.appendTo($err);
	frappe.ui.button({ label: __("Retry"), size: "xs", onclick: () => retry_fn() }).appendTo($err);
};

frappe.doctype_settings.is_permission_error = function (err) {
	if (!err) return false;
	return (
		err.status === 403 ||
		err.exc_type === "PermissionError" ||
		(err.responseJSON || {}).exc_type === "PermissionError" ||
		(typeof err === "string" && err.includes("PermissionError"))
	);
};

// Shared helper: write a DocType-level Property Setter (same mechanism Customize Form uses).
// Deduplication is handled server-side by Property Setter's own validation.
frappe.doctype_settings.set_property = function (doctype, property, value) {
	return frappe.db
		.insert({
			doctype: "Property Setter",
			doctype_or_field: "DocType",
			doc_type: doctype,
			property,
			property_type: "Data",
			value,
		})
		.then(() => frappe.show_alert({ message: __("Default updated"), indicator: "green" }));
};

// Each `condition` hides a tab the user could never load anyway (boot perms are a
// client-side hint; the server still enforces). A tab that is guaranteed to 403
// shouldn't be offered at all — see render_error for the residual failure path.
frappe.doctype_settings.groups = [
	{
		group: __("Document"),
		items: [
			{
				id: "naming",
				label: __("Naming"),
				icon: "tag",
				condition: () => frappe.model.can_read("Document Naming Rule"),
			},
			{
				id: "workflow",
				label: __("Workflow"),
				icon: "workflow",
				condition: () => frappe.model.can_read("Workflow"),
			},
			{
				id: "permissions",
				label: __("Permissions"),
				icon: "shield-check",
				// Role permission APIs are System-Manager-only; hide the tab otherwise.
				condition: () => frappe.user.has_role("System Manager"),
			},
			{
				id: "print-format",
				label: __("Print Formats"),
				icon: "printer",
				condition: () => frappe.model.can_read("Print Format"),
			},
		],
	},
	{
		group: __("Communication"),
		items: [
			{
				id: "notifications",
				label: __("Notifications"),
				icon: "bell",
				condition: () => frappe.model.can_read("Notification"),
			},
			{
				id: "email-template",
				label: __("Email Templates"),
				icon: "mail",
				condition: () => frappe.model.can_read("Email Template"),
			},
		],
	},
	{
		group: __("Data"),
		items: [
			{
				id: "global-search",
				label: __("Global Search"),
				icon: "search",
				condition: () => frappe.model.can_read("Global Search Settings"),
			},
		],
	},
];

// The sidebar icon for a tab id — so empty states (etc.) reuse the same glyph as the
// sidebar instead of hardcoding their own.
frappe.doctype_settings.tab_icon = function (id) {
	for (const group of frappe.doctype_settings.groups) {
		const item = group.items.find((i) => i.id === id);
		if (item) return item.icon;
	}
};
