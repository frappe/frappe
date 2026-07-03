frappe.doctype_settings.register("email-template", function (panel, doctype) {
	// Current default, read from the Property Setter (same mechanism Customize Form uses).
	let default_template = null;

	const open = (name) => {
		panel.dialog.hide();
		frappe.set_route("Form", "Email Template", name);
	};
	const create = () => {
		panel.dialog.hide();
		frappe.new_doc("Email Template", { reference_doctype: doctype });
	};

	frappe.doctype_settings.render_list(panel, {
		title: __("Email Templates"),
		description: __("Reuse email templates when emailing {0}.", [doctype]),
		primary_action: { label: __("New"), icon: "plus", onclick: create },
		load: () =>
			Promise.all([
				frappe.db.get_list("Email Template", {
					filters: { reference_doctype: doctype },
					fields: ["name", "subject"],
					order_by: "name asc",
					limit: 0,
				}),
				frappe.db.get_value(
					"Property Setter",
					{ doc_type: doctype, property: "default_email_template" },
					"value"
				),
			]).then(([templates, ps]) => {
				default_template = ps && ps.message ? ps.message.value : null;
				return templates;
			}),
		title_column: {
			primary: (r) => r.name,
			secondary: (r) => r.subject,
			onclick: (r) => open(r.name),
			tags: (r) =>
				r.name === default_template ? [{ label: __("Default"), color: "green" }] : [],
		},
		actions: (r) => {
			const items = [];
			if (r.name !== default_template) {
				items.push({
					label: __("Set as Default"),
					icon: "star",
					onclick: (list) => set_default(doctype, r.name).then(() => list.reload()),
				});
			}
			items.push({ label: __("Edit"), icon: "pencil", onclick: () => open(r.name) });
			items.push({
				label: __("Delete"),
				icon: "trash-2",
				danger: true,
				onclick: (list) =>
					frappe.model.delete_doc("Email Template", r.name, () => {
						frappe.show_alert({ message: __("Deleted"), indicator: "green" });
						list.reload();
					}),
			});
			return items;
		},
		empty_state: {
			icon: frappe.doctype_settings.tab_icon("email-template"),
			title: __("No Email Templates found"),
			description: __("Create a template to reuse when emailing {0}.", [doctype]),
			action: { label: __("New Template"), onclick: create },
		},
	});
});

function set_default(doctype, template) {
	return frappe.doctype_settings.set_property(doctype, "default_email_template", template);
}
