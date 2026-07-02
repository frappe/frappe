// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("DocType Settings Map", {
	refresh(frm) {
		// Only Single ("Settings") doctypes can be a source of mapped settings.
		frm.set_query("settings_doctype", "mappings", () => ({
			filters: { issingle: 1 },
		}));
	},

	// `module` is derived from the doctype this map applies to (read-only) — it decides which
	// app a standard map is exported to.
	applies_to_doctype(frm) {
		if (!frm.doc.applies_to_doctype) {
			frm.set_value("module", null);
			return;
		}
		frappe.db.get_value("DocType", frm.doc.applies_to_doctype, "module").then((r) => {
			frm.set_value("module", (r.message && r.message.module) || null);
		});
	},
});

// Each row names a `settings_doctype.setting_field` to surface for this record's doctype.
// The setting_field autocomplete depends on the chosen single, so it's populated per row.
frappe.ui.form.on("DocType Settings Map Item", {
	form_render(frm, cdt, cdn) {
		set_setting_field_options(frm, cdn);
	},
	settings_doctype(frm, cdt, cdn) {
		// Different single → different fields; clear the stale value and refresh suggestions.
		frappe.model.set_value(cdt, cdn, "setting_field", "");
		set_setting_field_options(frm, cdn);
	},
});

// Suggest the chosen single's value-bearing fields for `setting_field` on the given row.
function set_setting_field_options(frm, cdn) {
	const row = locals["DocType Settings Map Item"][cdn];
	const grid_row = frm.fields_dict.mappings.grid.grid_rows_by_docname[cdn];
	const control = grid_row && grid_row.get_field && grid_row.get_field("setting_field");
	if (!control) return;

	if (!row.settings_doctype) {
		control.set_data([]);
		return;
	}

	frappe.model.with_doctype(row.settings_doctype, () => {
		const data = frappe.meta
			.get_docfields(row.settings_doctype)
			.filter((df) => df.fieldname && !frappe.model.no_value_type.includes(df.fieldtype))
			.map((df) => ({
				value: df.fieldname,
				label: `${__(df.label || df.fieldname)} (${df.fieldname})`,
			}));
		control.set_data(data);
	});
}
