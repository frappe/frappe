frappe.listview_settings["DocType"] = {
	primary_action: function () {
		let non_developer = frappe.session.user !== "Administrator" || !frappe.boot.developer_mode;
		let new_d = new frappe.ui.Dialog({
			title: __("Create New DocType"),
			fields: [
				{
					label: __("DocType Name"),
					fieldname: "doctype_name",
					fieldtype: "Data",
					reqd: 1,
				},
				{ fieldtype: "Column Break" },
				{
					label: __("Module"),
					fieldname: "module",
					fieldtype: "Link",
					options: "Module Def",
					reqd: 1,
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
				},
				{
					label: __("Is Child Table"),
					fieldname: "istable",
					fieldtype: "Check",
					description: __("Child Tables are shown as a Grid in other DocTypes"),
					depends_on: "eval:!doc.is_submittable && !doc.issingle",
				},
				{
					label: __("Editable Grid"),
					fieldname: "editable_grid",
					fieldtype: "Check",
					depends_on: "istable",
					default: 1,
				},
				{
					label: __("Is Single"),
					fieldname: "issingle",
					fieldtype: "Check",
					description: __(
						"Single Types have only one record no tables associated. Values are stored in tabSingles"
					),
					depends_on: "eval:!doc.istable && !doc.is_submittable",
				},
				{
					label: __("Custom?"),
					fieldname: "custom",
					fieldtype: "Check",
					default: non_developer,
					read_only: non_developer,
				},
			],
			primary_action_label: __("Create & Continue"),
			primary_action(values) {
				if (!values.istable) values.editable_grid = 0;
				frappe.db
					.insert({
						doctype: "DocType",
						name: values.doctype_name,
						module: values.module,
						istable: values.istable,
						editable_grid: values.editable_grid,
						issingle: values.issingle,
						custom: values.custom,
						is_submittable: values.is_submittable,
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
							},
						],
						fields: [
							{
								label: "Title",
								fieldtype: "Data",
							},
						],
					})
					.then((doc) => {
						frappe.set_route("Form", "DocType", doc.name);
					});
			},
			secondary_action_label: __("Cancel"),
			secondary_action() {
				new_d.hide();
			},
		});
		new_d.show();
	},
};
