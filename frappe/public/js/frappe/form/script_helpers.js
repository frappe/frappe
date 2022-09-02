// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
/* eslint-disable no-console */

window.refresh_many = function (flist, dn, table_field) {
	for (var i in flist) {
		if (table_field) refresh_field(flist[i], dn, table_field);
		else refresh_field(flist[i]);
	}
};

window.refresh_field = function (n, docname, table_field) {
	// multiple
	if (typeof n == typeof []) refresh_many(n, docname, table_field);

	if (n && typeof n === "string" && table_field) {
		var grid = cur_frm.fields_dict[table_field].grid,
			field = frappe.utils.filter_dict(grid.docfields, { fieldname: n }),
			grid_row = grid.grid_rows_by_docname[docname];

		if (field && field.length) {
			field = field[0];
			var meta = frappe.meta.get_docfield(field.parent, field.fieldname, docname);
			$.extend(field, meta);
			if (grid_row) {
				grid_row.refresh_field(n);
			} else {
				grid.refresh();
			}
		}
	} else if (cur_frm) {
		cur_frm.refresh_field(n);
	}
};

window.set_field_options = function (n, txt) {
	cur_frm.set_df_property(n, "options", txt);
};

window.toggle_field = function (n, hidden) {
	var df = frappe.meta.get_docfield(cur_frm.doctype, n, cur_frm.docname);
	if (df) {
		df.hidden = hidden;
		refresh_field(n);
	} else {
		console.log((hidden ? "hide_field" : "unhide_field") + " cannot find field " + n);
	}
};

window.hide_field = function (n) {
	if (cur_frm) {
		if (n.substr) toggle_field(n, 1);
		else {
			for (var i in n) toggle_field(n[i], 1);
		}
	}
};

window.unhide_field = function (n) {
	if (cur_frm) {
		if (n.substr) toggle_field(n, 0);
		else {
			for (var i in n) toggle_field(n[i], 0);
		}
	}
};
