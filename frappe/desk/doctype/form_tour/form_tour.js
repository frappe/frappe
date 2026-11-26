// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Form Tour", {
	refresh(frm) {
		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.trigger("disable_form");
		}
		frm.set_query("reference_doctype", () => {
			return { filters: { istable: 0 } };
		});
		frm.trigger("reference_doctype");
		frm.set_query("report_name", () => {
			if (frm.doc.reference_doctype) {
				return {
					filters: {
						ref_doctype: frm.doc.reference_doctype,
					},
				};
			}
			return {};
		});
		!frm.is_new() && add_custom_button(frm);
	},
	async report_name(frm) {
		if (!frm.doc.ui_tour || !frm.doc.report_name) return;
		let { message } = await frappe.db.get_value("Report", frm.doc.report_name, "ref_doctype");
		frm.set_value("reference_doctype", message?.ref_doctype || "");
	},
	async before_save(frm) {
		if (
			frm.doc.select_view == "List" &&
			frm.doc.list_name == "Dashboard" &&
			frm.doc.dashboard_name &&
			frm.doc.reference_doctype
		) {
			frappe.throw(
				__("Referance Doctype and Dashboard Name both can't be used at the same time.")
			);
		}
	},
	disable_form: function (frm) {
		frm.set_read_only();
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},

	reference_doctype(frm) {
		if (!frm.doc.reference_doctype) return;

		frm.set_fields_as_options("fieldname", frm.doc.reference_doctype, (df) => !df.hidden).then(
			(options) => {
				frm.fields_dict.steps.grid.update_docfield_property(
					"fieldname",
					"options",
					[""].concat(options)
				);
			}
		);

		frm.set_fields_as_options(
			"parent_fieldname",
			frm.doc.reference_doctype,
			(df) => df.fieldtype == "Table" && !df.hidden
		).then((options) => {
			frm.fields_dict.steps.grid.update_docfield_property(
				"parent_fieldname",
				"options",
				[""].concat(options)
			);
		});
		if (!frm.doc.ui_tour) {
			// remove report name if reference doctype is changed and report name is not valid.
			frappe.db
				.get_list(
					"Report",
					{
						filters: {
							ref_doctype: frm.doc.reference_doctype,
						},
					},
					{ fields: ["name"] }
				)
				.then((reports) => {
					if (reports.findIndex((r) => r.name == frm.doc.report_name) == -1) {
						frm.set_value("report_name", "");
						frm.refresh_field("report_name");
					}
				});
		}
	},
});

let add_custom_button = (frm) => {
	if (frm.doc.ui_tour) {
		frm.add_custom_button(__("Reset"), function () {
			frappe.confirm(
				__("This will reset this tour and show it to all users. Are you sure?"),
				function () {
					frappe.call({
						method: "frappe.desk.doctype.form_tour.form_tour.reset_tour",
						args: {
							tour_name: frm.doc.name,
						},
					});
					delete frappe.boot.user.onboarding_status[frm.doc.name];
				}
			);
		});
	} else {
		frm.add_custom_button(__("Show Tour"), async () => {
			const issingle = await check_if_single(frm.doc.reference_doctype);
			let route_changed = null;

			if (issingle) {
				route_changed = frappe.set_route("Form", frm.doc.reference_doctype);
			} else if (frm.doc.first_document) {
				const name = await get_first_document(frm.doc.reference_doctype);
				route_changed = frappe.set_route("Form", frm.doc.reference_doctype, name);
			} else {
				route_changed = frappe.set_route("Form", frm.doc.reference_doctype, "new");
			}
			route_changed.then(() => {
				const tour_name = frm.doc.name;
				cur_frm.tour.init({ tour_name }).then(() => cur_frm.tour.start());
			});
		});
	}
};

frappe.ui.form.on("Form Tour Step", {
	form_render(frm, cdt, cdn) {
		if (locals[cdt][cdn].is_table_field) {
			frm.trigger("parent_fieldname", cdt, cdn);
		}
	},
	parent_fieldname(frm, cdt, cdn) {
		const child_row = locals[cdt][cdn];

		const parent_fieldname_df = frappe
			.get_meta(frm.doc.reference_doctype)
			.fields.find((df) => df.fieldname == child_row.parent_fieldname);

		frm.set_fields_as_options(
			"fieldname",
			parent_fieldname_df.options,
			(df) => !df.hidden
		).then((options) => {
			frm.fields_dict.steps.grid.update_docfield_property(
				"fieldname",
				"options",
				[""].concat(options)
			);
			if (child_row.fieldname) {
				frappe.model.set_value(cdt, cdn, "fieldname", child_row.fieldname);
			}
		});
	},
});

async function check_if_single(doctype) {
	const { message } = await frappe.db.get_value("DocType", doctype, "issingle");
	return message.issingle || 0;
}

async function get_first_document(doctype) {
	let docname;

	await frappe.db.get_list(doctype, { order_by: "creation" }).then((res) => {
		if (Array.isArray(res) && res.length) docname = res[0].name;
	});

	return docname || "new";
}
