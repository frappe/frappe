// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Form Tour", {
	setup: function (frm) {
		if (!frm.doc.is_standard || frappe.boot.developer_mode) {
			frm.trigger("setup_queries");
		}
	},

	refresh(frm) {
		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.trigger("disable_form");
		}

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

	setup_queries(frm) {
		frm.set_query("reference_doctype", function () {
			return {
				filters: {
					istable: 0,
				},
			};
		});

		frm.trigger("reference_doctype");
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
	},
});

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
