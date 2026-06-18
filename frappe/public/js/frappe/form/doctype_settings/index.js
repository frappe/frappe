import "./registry";
import "./list_panel";

// Tabs self-register via frappe.doctype_settings.register(id, builder); each is
// imported here as it's added.
import "./tabs/email_template";

/**
 * Open the DocType Settings dialog scoped to `doctype`.
 *
 * Builds a `frappe.ui.SettingsDialog` from the registry: each item's `render`
 * delegates to the registered builder, partially applied with the doctype. Items
 * without a registered builder are omitted, and groups left empty are dropped.
 */
frappe.doctype_settings.open = function (doctype) {
	if (!doctype) return;

	const builders = frappe.doctype_settings.builders;
	const tabs = [];

	for (const group of frappe.doctype_settings.groups) {
		const items = (group.items || [])
			.filter((item) => builders[item.id])
			.map((item) => ({
				...item,
				render: (panel) => builders[item.id](panel, doctype),
			}));
		if (items.length) tabs.push({ group: group.group, items });
	}

	if (!tabs.length) return;

	const dialog = new frappe.ui.SettingsDialog({
		title: __("DocType Settings"),
		tabs,
	});
	dialog.doctype = doctype;
	dialog.show();
	return dialog;
};
