frappe.listview_settings["DocType"] = {
	primary_action: function () {
		this.new_doctype_dialog();
	},

<<<<<<< HEAD
	new_doctype_dialog() {
=======
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

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		let non_developer = frappe.session.user !== "Administrator" || !frappe.boot.developer_mode;
		let fields = [
			{
				label: __("Name"),
				fieldname: "name",
				fieldtype: "Data",
				reqd: 1,
<<<<<<< HEAD
=======
				default: doctype_name,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			},
			{ fieldtype: "Column Break" },
			{
				label: __("Module"),
				fieldname: "module",
				fieldtype: "Link",
				options: "Module Def",
				reqd: 1,
<<<<<<< HEAD
=======
				default: doctype_module,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
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
<<<<<<< HEAD
=======
				default: is_submittable,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			},
			{
				label: __("Is Child Table"),
				fieldname: "istable",
				fieldtype: "Check",
				description: __("Child Tables are shown as a Grid in other DocTypes"),
				depends_on: "eval:!doc.is_submittable && !doc.issingle",
<<<<<<< HEAD
=======
				default: is_child,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			},
			{
				label: __("Editable Grid"),
				fieldname: "editable_grid",
				fieldtype: "Check",
				depends_on: "istable",
<<<<<<< HEAD
				default: 1,
=======
				default: editable_grid,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			},
			{
				label: __("Is Single"),
				fieldname: "issingle",
				fieldtype: "Check",
				description: __(
					"Single Types have only one record no tables associated. Values are stored in tabSingles"
				),
				depends_on: "eval:!doc.istable && !doc.is_submittable",
<<<<<<< HEAD
=======
				default: is_single,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			},
			{
				label: "Is Tree",
				fieldname: "is_tree",
				fieldtype: "Check",
<<<<<<< HEAD
				default: "0",
=======
				default: is_tree,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
				depends_on: "eval:!doc.istable",
				description: "Tree structures are implemented using Nested Set",
			},
			{
				label: __("Custom?"),
				fieldname: "custom",
				fieldtype: "Check",
<<<<<<< HEAD
				default: non_developer,
=======
				default: non_developer || is_custom,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
				read_only: non_developer,
			},
		];

		if (!non_developer) {
			fields.push({
				label: "Is Virtual",
				fieldname: "is_virtual",
				fieldtype: "Check",
<<<<<<< HEAD
				default: "0",
=======
				default: is_virtual,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			});
		}

		let new_d = new frappe.ui.Dialog({
			title: __("Create New DocType"),
			fields: fields,
			primary_action_label: __("Create & Continue"),
			primary_action(values) {
				if (!values.istable) values.editable_grid = 0;
				frappe.db
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
				if (frappe.get_route()[0] === "Form") {
					frappe.set_route("List", "DocType");
				}
			},
		});
		new_d.show();
	},
};
