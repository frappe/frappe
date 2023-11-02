// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Audit Trail", {
	refresh(frm) {
		let prev_route = frappe.get_prev_route();
		if (
			prev_route.length > 2 &&
			prev_route[0] == "Form" &&
			!prev_route.includes("Audit Trail")
		) {
			frm.set_value("doctype_name", prev_route[1]);
			frm.set_value("document", prev_route[2]);
			frm.set_value("start_date", "");
			frm.set_value("end_date", "");
			if (frm.doc.doctype_name && frm.doc.document)
				frm.events.get_audit_trail_for_document(frm);
		}

		frm.page.clear_indicator();

		frm.disable_save();

		frm.set_query("doctype_name", () => {
			return {
				filters: {
					track_changes: 1,
					is_submittable: 1,
				},
			};
		});

		frm.set_query("document", () => {
			let filters = {
				amended_from: ["!=", ""],
			};
			if (frm.doc.start_date && frm.doc.end_date)
				filters["creation"] = ["between", [frm.doc.start_date, frm.doc.end_date]];
			else if (frm.doc.start_date) filters["creation"] = [">=", frm.doc.start_date];
			else if (frm.doc.end_date) filters["creation"] = ["<=", frm.doc.end_date];
			return {
				filters: filters,
			};
		});

		frm.page.set_primary_action("Compare", () => {
			frm.events.get_audit_trail_for_document(frm);
		});
	},

	start_date(frm) {
		if (frm.doc.start_date > frm.doc.end_date) {
			frm.doc.end_date = "";
			frm.refresh_fields();
		}

		frappe.db
			.get_value(frm.doc.doctype_name, frm.doc.document, "creation")
			.then((creation) => {
				if (frappe.datetime.obj_to_str(creation) < frm.doc.start_date) {
					frm.doc.document = "";
					frm.refresh_fields();
				}
			});
	},

	end_date(frm) {
		frappe.db
			.get_value(frm.doc.doctype_name, frm.doc.document, "creation")
			.then((creation) => {
				if (frappe.datetime.obj_to_str(creation) > frm.doc.end_date) {
					frm.doc.document = "";
					frm.refresh_fields();
				}
			});
	},

	get_audit_trail_for_document(frm) {
		frm.call({
			doc: frm.doc,
			method: "compare_document",
			callback: function (r) {
				let document_names = r.message[0];
				let changed_fields = r.message[1];
				frm.events.render_changed_fields(frm, document_names, changed_fields);
				frm.events.render_rows_added_or_removed(frm, changed_fields);
			},
		});
	},

	render_changed_fields(frm, document_names, changed_fields) {
		let render_dict = {
			documents: document_names,
			changed: changed_fields.changed,
			row_changed: changed_fields.row_changed,
		};
		$(frappe.render_template("audit_trail", render_dict)).appendTo(
			frm.fields_dict.version_table.$wrapper.empty()
		);
		frm.set_df_property("version_table", "hidden", 0);
	},

	render_rows_added_or_removed(frm, changed_fields) {
		let added_or_removed = {
			rows_added: changed_fields.added,
			rows_removed: changed_fields.removed,
		};

		let hide_section = 0;
		let section_dict = {};

		for (let key in added_or_removed) {
			hide_section = 0;
			section_dict = {
				added_or_removed: added_or_removed[key],
			};
			$(frappe.render_template("audit_trail_rows_added_removed", section_dict)).appendTo(
				frm.fields_dict[key].$wrapper.empty()
			);

			if (!frm.fields_dict[key].disp_area.innerHTML.includes("<table")) hide_section = 1;
			frm.set_df_property(key + "_section", "hidden", hide_section);
		}
	},
});
