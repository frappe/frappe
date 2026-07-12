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

/**
 * Shared overflow "…" menu used by list rows and custom tabs.
 *
 * Uses Bootstrap's native dropdown (`data-toggle="dropdown"`), which handles
 * open/close and outside-click on its own — no manual toggling.
 *
 * `items`: [{ label, icon, danger, onclick() }] — falsy entries are skipped.
 * Returns the actions cell ($div) ready to append to a row. Callers that need a
 * controller/row in the handler should bind it into `onclick` themselves.
 */
frappe.doctype_settings.overflow_menu = function (items) {
	items = (items || []).filter(Boolean);
	const $cell = $('<div class="dts-list-cell dts-list-cell-actions"></div>');
	if (!items.length) return $cell;

	const $wrap = $('<div class="dropdown dts-actions"></div>').appendTo($cell);
	frappe.ui
		.button({
			icon: "ellipsis",
			size: "xs",
			variant: "ghost",
			title: __("More actions"),
			css_class: "dts-actions-btn",
			attrs: {
				"data-toggle": "dropdown",
				"aria-haspopup": "menu",
				"aria-expanded": "false",
			},
		})
		.appendTo($wrap);
	const $menu = $('<div class="dropdown-menu dropdown-menu-right" role="menu"></div>').appendTo(
		$wrap
	);

	items.forEach((item) => {
		const $a = $(
			'<button type="button" class="dropdown-item dts-action-item" role="menuitem"></button>'
		);
		if (item.icon) $a.append(frappe.utils.icon(item.icon, "sm"));
		$a.append($("<span></span>").text(item.label));
		if (item.danger) $a.addClass("text-danger");
		$a.on("click", () => item.onclick());
		$menu.append($a);
	});

	return $cell;
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

frappe.doctype_settings.render_error = function (panel, retry_fn) {
	const $err = panel.body.empty();
	$('<div class="text-muted small"></div>').text(__("Could not load this tab.")).appendTo($err);
	frappe.ui.button({ label: __("Retry"), size: "xs", onclick: () => retry_fn() }).appendTo($err);
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

frappe.doctype_settings.groups = [
	{
		group: __("Document"),
		items: [
			{ id: "naming", label: __("Naming"), icon: "tag" },
			{ id: "workflow", label: __("Workflow"), icon: "workflow" },
			{
				id: "permissions",
				label: __("Permissions"),
				icon: "shield-check",
				// Role permission APIs are System-Manager-only; hide the tab otherwise.
				condition: () => frappe.user.has_role("System Manager"),
			},
			{ id: "print-format", label: __("Print Formats"), icon: "printer" },
		],
	},
	{
		group: __("Communication"),
		items: [
			{ id: "notifications", label: __("Notifications"), icon: "bell" },
			{ id: "email-template", label: __("Email Templates"), icon: "mail" },
		],
	},
	{
		group: __("Data"),
		items: [{ id: "global-search", label: __("Global Search"), icon: "search" }],
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
