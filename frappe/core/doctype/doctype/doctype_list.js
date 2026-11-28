frappe.listview_settings["DocType"] = {
	primary_action: function () {
		this.new_doctype_dialog();
	},

	onload(listview) {
		// the actions menu is built before onload, so rebuild it with the wrapped Delete
		const get_actions_menu_items = listview.get_actions_menu_items.bind(listview);
		listview.get_actions_menu_items = () => {
			const items = get_actions_menu_items();
			const delete_item = items.find(
				(item) => item.label === __("Delete", null, "Button in list view actions menu")
			);
			if (delete_item) {
				const delete_action = delete_item.action;
				delete_item.action = () => {
					const doctypes = listview.get_checked_items(true);
					frappe.listview_settings["DocType"].confirm_delete(
						doctypes,
						() =>
							frappe
								.call({
									method: "frappe.desk.reportview.delete_items",
									args: { items: doctypes, doctype: "DocType" },
									freeze: true,
								})
								.then(() => {
									listview.clear_checked_items();
									listview.refresh();
								}),
						delete_action
					);
				};
			}
			return items;
		};
		listview.page.clear_actions_menu();
		listview.set_actions_menu_items();
	},

	// Web Forms of a deleted DocType stop working, so name them before deleting
	confirm_delete(doctypes, delete_doctypes, delete_without_web_forms) {
		if (!frappe.model.can_read("Web Form")) return delete_without_web_forms();

		frappe.db
			.get_list("Web Form", {
				filters: { doc_type: ["in", doctypes] },
				fields: ["name", "doc_type"],
				limit: 0,
			})
			.then((web_forms) => {
				if (!web_forms.length) return delete_without_web_forms();
				frappe.warn(
					__("Confirm"),
					get_delete_message(doctypes, web_forms),
					delete_doctypes,
					__("Delete")
				);
			});
	},

	new_doctype_dialog(args) {
		const {
			doctype_name = "",
			doctype_module = "",
			is_submittable = 0,
			is_child = 0,
			is_virtual = 0,
			is_single = 0,
			is_tree = 0,
			is_custom = 0,
			editable_grid = 1,
		} = args || {};

		let non_developer = frappe.session.user !== "Administrator" || !frappe.boot.developer_mode;
		let fields = [
			{
				label: __("Name"),
				fieldname: "name",
				fieldtype: "Data",
				reqd: 1,
				default: doctype_name,
				length: 61,
			},
			{ fieldtype: "Column Break" },
			{
				label: __("Module"),
				fieldname: "module",
				fieldtype: "Link",
				options: "Module Def",
				reqd: 1,
				default: doctype_module,
			},
			{ fieldtype: "Section Break" },
			{
				label: __("Is Submittable"),
				fieldname: "is_submittable",
				fieldtype: "Check",
				description: __(
					"Once submitted, submittable documents cannot be changed. They can only be Cancelled and Amended."
				),
				depends_on: "eval:!doc.istable && !doc.issingle",
				default: is_submittable,
			},
			{
				label: __("Is Child Table"),
				fieldname: "istable",
				fieldtype: "Check",
				description: __("Child Tables are shown as a Grid in other DocTypes"),
				depends_on: "eval:!doc.is_submittable && !doc.issingle",
				default: is_child,
			},
			{
				label: __("Editable Grid"),
				fieldname: "editable_grid",
				fieldtype: "Check",
				depends_on: "istable",
				default: editable_grid,
			},
			{
				label: __("Is Single"),
				fieldname: "issingle",
				fieldtype: "Check",
				description: __(
					"Single Types have only one record no tables associated. Values are stored in tabSingles"
				),
				depends_on: "eval:!doc.istable && !doc.is_submittable",
				default: is_single,
			},
			{
				label: "Is Tree",
				fieldname: "is_tree",
				fieldtype: "Check",
				default: is_tree,
				depends_on: "eval:!doc.istable",
				description: "Tree structures are implemented using Nested Set",
			},
			{
				label: __("Custom?"),
				fieldname: "custom",
				fieldtype: "Check",
				default: non_developer || is_custom,
				read_only: non_developer,
			},
		];

		if (!non_developer) {
			fields.push({
				label: "Is Virtual",
				fieldname: "is_virtual",
				fieldtype: "Check",
				default: is_virtual,
			});
		}

		let new_d = new frappe.ui.Dialog({
			title: __("Create New DocType"),
			fields: fields,
			primary_action_label: __("Create & Continue"),
			primary_action(values) {
				if (!values.istable) values.editable_grid = 0;
				return frappe.db
					.insert({
						doctype: "DocType",
						...values,
						permissions: [
							{
								create: 1,
								delete: 1,
								email: 1,
								export: 1,
								print: 1,
								read: 1,
								report: 1,
								role: "System Manager",
								share: 1,
								write: 1,
								submit: values.is_submittable ? 1 : 0,
							},
						],
						fields: [{ fieldtype: "Section Break" }],
					})
					.then((doc) => {
						frappe.set_route("Form", "DocType", doc.name);
					});
			},
			secondary_action_label: __("Cancel"),
			secondary_action() {
				new_d.hide();
				const [view, doctype, name] = frappe.get_route();
				if (view === "Form" && doctype === "DocType" && name?.startsWith("new-doctype-")) {
					frappe.set_route("List", "DocType");
				}
			},
		});
		new_d.show();
	},
};

function get_delete_message(doctypes, web_forms) {
	const link = (web_form) => frappe.utils.get_form_link("Web Form", web_form.name, true);

	if (doctypes.length === 1 && web_forms.length === 1) {
		return __(
			"{0} uses this DocType. Deleting it also deletes all its records and the Web Form stops working.",
			[`<strong>${__("Web Form {0}", [link(web_forms[0])])}</strong>`]
		);
	}

	// like the linked documents list on delete, long lists end with a count
	const max = 10;
	const more = (count) => (count > max ? __("and {0} more", [count - max]) : "");
	let list;
	if (doctypes.length === 1) {
		list = web_forms
			.slice(0, max)
			.map((web_form) => `<li>${link(web_form)}</li>`)
			.join("");
		if (web_forms.length > max) list += `<li>${more(web_forms.length)}</li>`;
	} else {
		list = [...new Set(web_forms.map((web_form) => web_form.doc_type))]
			.map((doctype) => {
				const of_doctype = web_forms.filter((web_form) => web_form.doc_type === doctype);
				const names = [...of_doctype.slice(0, max).map(link), more(of_doctype.length)]
					.filter(Boolean)
					.join(", ");
				return `<li><strong>${frappe.utils.escape_html(doctype)}</strong>: ${names}</li>`;
			})
			.join("");
	}

	return doctypes.length === 1
		? __(
				"These Web Forms use this DocType: {0}Deleting it also deletes all its records and these Web Forms stop working.",
				[`<ul>${list}</ul>`]
		  )
		: __(
				"These Web Forms use the selected DocTypes: {0}Deleting them also deletes all their records and these Web Forms stop working.",
				[`<ul>${list}</ul>`]
		  );
}
