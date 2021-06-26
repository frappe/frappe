// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Form Tour', {
	setup: function(frm) {
		if (!frm.doc.is_standard || frappe.boot.developer_mode) {
			frm.trigger('setup_queries');
		}
	},

	refresh(frm) {
		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.trigger("disable_form");
		}

		frm.add_custom_button(__('Show Tour'), async () => {
			const issingle = await check_if_single(frm.doc.reference_doctype);

			if (issingle) {
				frappe.set_route('Form', frm.doc.reference_doctype);
			} else {
				const new_name =  'new-' + frappe.scrub(frm.doc.reference_doctype) + '-1';
				frappe.set_route('Form', frm.doc.reference_doctype, new_name);
			}
			frappe.utils.sleep(500).then(() => {
				const tour_name = frm.doc.name;
				cur_frm.tour
					.init({ tour_name })
					.then(() => cur_frm.tour.start());
			});
		});
	},

	disable_form: function(frm) {
		frm.set_read_only();
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},

	setup_queries(frm) {
		frm.set_query("reference_doctype", function() {
			return {
				filters: {
					istable: 0
				}
			};
		});

		frm.set_query("field", "steps", function() {
			return {
				query: "frappe.desk.doctype.form_tour.form_tour.get_docfield_list",
				filters: {
					doctype: frm.doc.reference_doctype,
					hidden: 0
				}
			};
		});

		frm.set_query("parent_field", "steps", function() {
			return {
				query: "frappe.desk.doctype.form_tour.form_tour.get_docfield_list",
				filters: {
					doctype: frm.doc.reference_doctype,
					fieldtype: "Table",
					hidden: 0,
				}
			};
		});

		frm.trigger('reference_doctype');
	},

	reference_doctype(frm) {
		if (!frm.doc.reference_doctype) return;

		frappe.db.get_list('DocField', {
			filters: {
				parent: frm.doc.reference_doctype,
				parenttype: 'DocType',
				fieldtype: 'Table'
			},
			fields: ['options']
		}).then(res => {
			if (Array.isArray(res)) {
				frm.child_doctypes = res.map(r => r.options);
			}
		});

	}
});

frappe.ui.form.on('Form Tour Step', {
	parent_field(frm, cdt, cdn) {
		const child_row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'field', '');
		const field_control = get_child_field("steps", cdn, "field");
		field_control.get_query = function() {
			return {
				query: "frappe.desk.doctype.form_tour.form_tour.get_docfield_list",
				filters: {
					doctype: child_row.child_doctype,
					hidden: 0
				}
			};
		};
	}
});

function get_child_field(child_table, child_name, fieldname) {
	// gets the field from grid row form
	const grid = cur_frm.fields_dict[child_table].grid;
	const grid_row = grid.grid_rows_by_docname[child_name];
	return grid_row.grid_form.fields_dict[fieldname];
}

async function check_if_single(doctype) {
	const { message } = await frappe.db.get_value('DocType', doctype, 'issingle');
	return message.issingle || 0;
}