// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui");

// Off on mobile, where the drawer would cover the whole viewport and routing to the form is the
// better experience. Defaults on, so an unset flag (pre-migration boot) still previews.
frappe.ui.split_view_enabled = function () {
	if (frappe.is_mobile()) return false;
	const enabled = frappe.boot.desk_settings?.report_split_view;
	return enabled === undefined || cint(enabled) === 1;
};

// Previews a clicked Link cell instead of routing to it. The ID column's anchor looks the same
// but should still route to the form, so only Link and Dynamic Link columns qualify.
frappe.ui.handle_link_cell_click = function (e, datatable) {
	if (!frappe.ui.split_view_enabled()) return false;
	if (e.which !== 1 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return false;

	const link = e.currentTarget;
	const { doctype, name } = link.dataset;
	if (!doctype || !name) return false;

	const col_index = $(link).closest(".dt-cell").attr("data-col-index");
	if (col_index == null) return false;
	const column = datatable.getColumn(Number(col_index));
	// report view keeps a docfield on the column, query reports set fieldtype on it directly
	const fieldtype = column?.docfield?.fieldtype ?? column?.fieldtype;
	if (!["Link", "Dynamic Link"].includes(fieldtype)) return false;

	e.preventDefault();
	// stopPropagation keeps router.js's delegated <a> handler on <body> from routing away.
	e.stopPropagation();

	// The panel lives in its own bundle, loaded on the first click.
	frappe.require("side_panel.bundle.js").then(() => {
		frappe.ui.get_side_panel().open(doctype, name);
	});
	return true;
};
