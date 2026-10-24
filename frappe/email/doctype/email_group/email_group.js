// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Email Group", {
	refresh: function (frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Import Subscribers"),
				function () {
					let d = new frappe.ui.Dialog({
						title: __("Import Subscribers"),
						fields: [
							{
								fieldtype: "Select",
								options: frm.doc.__onload.import_types,
								label: __("Import Email From"),
								fieldname: "doctype",
								reqd: 1,
								onchange: () => {
									const doctype = d.get_value("doctype");
									const $wrapper = d.fields_dict.filter_area.$wrapper;

									d.filter_group = null;
									$wrapper.empty();

									d.set_df_property("filter_area", "hidden", !doctype);

									if (!doctype) return;

									frappe.model.with_doctype(doctype, () => {
										if (d.get_value("doctype") !== doctype) return;

										$wrapper.empty();

										d.filter_group = new frappe.ui.FilterGroup({
											parent: $wrapper,
											doctype: doctype,
											on_change: () => {},
										});
									});
								},
							},
							{
								fieldtype: "HTML",
								fieldname: "filter_area",
								hidden: 1,
							},
						],
						primary_action_label: __("Import"),
						primary_action: (data) => {
							let filters = d.filter_group ? d.filter_group.get_filters() : [];
							frappe.call({
								method: "frappe.email.doctype.email_group.email_group.import_from",
								args: {
									name: frm.doc.name,
									doctype: data.doctype,
									filters: filters,
								},
								callback: function (r) {
									frm.set_value("total_subscribers", r.message);
									d.hide();
								},
							});
						},
					});
					d.show();
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
