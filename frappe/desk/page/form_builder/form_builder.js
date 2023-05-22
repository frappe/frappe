frappe.pages["form-builder"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Form Builder"),
		single_column: true,
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_form_builder(wrapper));
	}
};

frappe.pages["form-builder"].on_page_show = function (wrapper) {
	load_form_builder(wrapper);
};

function load_form_builder(wrapper) {
	let route = frappe.get_route();
	route = route.filter((a) => a);
	if (route.length > 1) {
		let doctype = route[1];
		let is_customize_form = route[2] === "customize";

		if (frappe.form_builder?.doctype) {
			frappe.form_builder.doctype = frappe.form_builder.store.doctype = doctype;
			frappe.form_builder.customize = frappe.form_builder.store.is_customize_form =
				is_customize_form;
			frappe.form_builder.init(true);
			frappe.form_builder.store.fetch();
			return;
		}

		let $parent = $(wrapper).find(".layout-main-section");
		$parent.empty();

		frappe.require("form_builder.bundle.js").then(() => {
			frappe.form_builder = new frappe.ui.FormBuilder({
				wrapper: $parent,
				page: wrapper.page,
				doctype: doctype,
				customize: is_customize_form,
			});
		});
	} else {
		let d = new frappe.ui.Dialog({
			title: __("Select DocType"),
			fields: [
				{
					label: __("Select DocType"),
					fieldname: "doctype",
					fieldtype: "Link",
					options: "DocType",
					only_select: 1,
				},
				{
					label: __("Customize"),
					fieldname: "customize",
					fieldtype: "Check",
				},
			],
			primary_action_label: __("Edit"),
			primary_action({ doctype, customize }) {
				if (customize) {
					frappe.model.with_doctype(doctype).then(() => {
						let meta = frappe.get_meta(doctype);
						if (in_list(frappe.model.core_doctypes_list, this.doctype))
							frappe.throw(__("Core DocTypes cannot be customized."));

						if (meta.issingle)
							frappe.throw(__("Single DocTypes cannot be customized."));

						if (meta.custom)
							frappe.throw(
								__(
									"Only standard DocTypes are allowed to be customized from Customize Form."
								)
							);
						frappe.set_route("form-builder", doctype, "customize");
					});
				} else {
					frappe.set_route("form-builder", doctype);
				}
			},
			secondary_action_label: __("Create New DocType"),
			secondary_action() {
				let doctype = d.get_value("doctype") || "";
				let non_developer =
					frappe.session.user !== "Administrator" || !frappe.boot.developer_mode;
				d.hide();
				let new_d = new frappe.ui.Dialog({
					title: __("Create New DocType"),
					fields: [
						{
							label: __("DocType Name"),
							fieldname: "doctype_name",
							fieldtype: "Data",
							default: doctype,
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
										fieldname: "title",
										fieldtype: "Data",
									},
								],
							})
							.then((doc) => {
								frappe.set_route("form-builder", doc.name);
							});
					},
					secondary_action_label: __("Back"),
					secondary_action() {
						new_d.hide();
						d.show();
					},
				});
				new_d.show();
			},
		});

		d.show();
	}
}
