import "./registry";
import "./list_panel";

// Tabs self-register via frappe.doctype_settings.register(id, builder); each is
// imported here as it's added.
import "./tabs/email_template";
import "./tabs/notification";
import "./tabs/naming";
import "./tabs/global_search";
import "./tabs/workflow";
import "./tabs/print_format";
import "./tabs/permissions";
import "./tabs/settings_map";

/**
 * Open the DocType Settings dialog scoped to `doctype`.
 *
 * A cheap existence check decides whether this doctype has a settings map; if so,
 * the "General" tab is shown first and opened by default (it resolves its own data on
 * render). The remaining tabs come from the registry (items without a builder are dropped,
 * empty groups removed).
 */
frappe.doctype_settings.open = function (doctype) {
	if (!doctype) return;

	return (
		frappe
			.call({
				method: "frappe.desk.doctype_settings.settings_map.has_settings_map",
				args: { doctype },
			})
			.then((r) => build_dialog(doctype, !!(r && r.message)))
			// A failure on the check must not block the whole dialog.
			.catch(() => build_dialog(doctype, false))
	);
};

function build_dialog(doctype, has_general) {
	const builders = frappe.doctype_settings.builders;
	const tabs = [];

	frappe.doctype_settings.groups.forEach((group, idx) => {
		const items = (group.items || [])
			.filter((item) => builders[item.id])
			.filter((item) => (item.condition ? item.condition(doctype) : true))
			.map((item) => ({
				...item,
				render: (panel) => builders[item.id](panel, doctype),
			}));

		// Lead the first group (Document) with the data-driven General tab when present.
		if (idx === 0 && has_general && builders["general"]) {
			items.unshift({
				id: "general",
				label: __("General"),
				icon: "settings",
				render: (panel) => builders["general"](panel, doctype),
			});
		}

		if (items.length) tabs.push({ group: group.group, items });
	});

	if (!tabs.length) return;

	const default_tab = has_general ? "general" : undefined;
	let dialog = frappe.doctype_settings._dialog;

	if (!dialog) {
		dialog = new frappe.ui.SettingsDialog({
			title: __("DocType Settings"),
			tabs,
			default_tab,
		});
		frappe.doctype_settings._dialog = dialog;
	} else {
		dialog.reset(tabs, default_tab);
	}

	dialog.doctype = doctype;
	dialog.show();
	return dialog;
}
