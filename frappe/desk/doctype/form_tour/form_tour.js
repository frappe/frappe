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
			const name = await get_first_document(frm.doc.reference_doctype);
			let route_changed = null;

			if (issingle) {
				route_changed = frappe.set_route('Form', frm.doc.reference_doctype);
			} else if (frm.doc.first_document) {
				route_changed = frappe.set_route('Form', frm.doc.reference_doctype, name);
			} else {
				route_changed = frappe.set_route('Form', frm.doc.reference_doctype, 'new');
			}
			route_changed.then(() => {
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

async function get_first_document(doctype) {
	let docname;

	await frappe.db.get_list(doctype, { order_by: "creation" }).then(res => {
		if (Array.isArray(res) && res.length)
			docname = res[0].name;
	});

	return docname || 'new';
}
