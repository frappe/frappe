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
 */
frappe.doctype_settings.builders = {};

frappe.doctype_settings.register = function (tab_id, builder) {
	frappe.doctype_settings.builders[tab_id] = builder;
};

frappe.doctype_settings.groups = [
	{
		group: __("Document"),
		items: [
			{ id: "workflow", label: __("Workflow"), icon: "workflow" },
			{ id: "permissions", label: __("Permissions"), icon: "shield-check" },
		],
	},
	{
		group: __("Communication"),
		items: [
			{ id: "print-format", label: __("Print Format"), icon: "printer" },
			{ id: "notifications", label: __("Notifications"), icon: "bell" },
			{ id: "email-template", label: __("Email Template"), icon: "mail" },
		],
	},
	{
		group: __("Data"),
		items: [
			{ id: "global-search", label: __("Global Search"), icon: "search" },
			{ id: "data-import", label: __("Data Import & Export"), icon: "database" },
		],
	},
];
