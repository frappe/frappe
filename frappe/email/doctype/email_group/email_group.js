// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Email Group", {
	refresh: function (frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Import Subscribers"),
				function () {
					open_import_dialog(frm);
				},
				__("Action")
			);

			frm.add_custom_button(
				__("Add Subscribers"),
				function () {
					frappe.prompt(
						{
							fieldtype: "Text",
							label: __("Email Addresses"),
							fieldname: "email_list",
							reqd: 1,
						},
						function (data) {
							frappe.call({
								method: "frappe.email.doctype.email_group.email_group.add_subscribers",
								args: {
									name: frm.doc.name,
									email_list: data.email_list,
								},
								callback: function (r) {
									frm.set_value("total_subscribers", r.message);
								},
							});
						},
						__("Add Subscribers"),
						__("Add")
					);
				},
				__("Action")
			);
		}

		frm.trigger("preview_welcome_url");
	},
	welcome_url(frm) {
		frm.trigger("preview_welcome_url");
	},
	add_query_parameters: function (frm) {
		frm.trigger("preview_welcome_url");
	},
	preview_welcome_url: function (frm) {
		if (frm.doc.add_query_parameters && frm.doc.welcome_url) {
			frm.call("preview_welcome_url", { email: "mail@example.org" }).then((r) => {
				frm.set_df_property(
					"add_query_parameters",
					"description",
					`${__("Preview:")} ${r.message}`
				);
			});
		} else {
			frm.set_df_property("add_query_parameters", "description", "");
		}
	},
});

function open_import_dialog(frm) {
	const allowed_doctypes = (frm.doc.__onload.import_types || []).map((d) => d.value);

	const d = new frappe.ui.Dialog({
		title: __("Import Subscribers"),
		fields: [
			{
				fieldtype: "Select",
				fieldname: "doctype",
				label: __("Import Email From"),
				options: allowed_doctypes,
				reqd: 1,
				onchange: () => on_doctype_change(d),
			},
			{ fieldtype: "Select", fieldname: "email_field", label: __("Email Field"), reqd: 1 },
			{ fieldtype: "Section Break" },
			{ fieldtype: "HTML", fieldname: "filter_area" },
		],
		primary_action_label: __("Import"),
		primary_action: (values) => {
			const filters = d.filter_group ? d.filter_group.get_filters() : [];
			frappe.call({
				method: "frappe.email.doctype.email_group.email_group.import_from",
				args: {
					name: frm.doc.name,
					doctype: values.doctype,
					email_field: values.email_field,
					filters: filters,
				},
				freeze: true,
				callback() {
					d.hide();
					frm.reload_doc();
				},
			});
		},
	});

	d.show();
	if (allowed_doctypes.length) {
		d.set_value("doctype", allowed_doctypes[0]);
		on_doctype_change(d);
	}
}

function on_doctype_change(d) {
	const dt = d.get_value("doctype");
	if (!dt) return;

	frappe.model.with_doctype(dt, () => {
		const email_fields = frappe.get_meta(dt).fields
			.filter((df) => df.options === "Email")
			.map((df) => ({ value: df.fieldname, label: df.label}));
		d.set_df_property("email_field", "options", email_fields);
		d.set_value("email_field", email_fields[0] || "");

		if (d.filter_group) {
			d.filter_group.wrapper.empty();
		}
		d.filter_group = new frappe.ui.FilterGroup({
			parent: d.get_field("filter_area").$wrapper,
			doctype: dt,
			on_change: () => {}, 
		});
		d.filter_group.wrapper.find(".apply-filters").hide();
	});
}