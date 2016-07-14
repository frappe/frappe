// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// -------------
// Menu Display
// -------------

// $(cur_frm.wrapper).on("grid-row-render", function(e, grid_row) {
// 	if(grid_row.doc && grid_row.doc.fieldtype=="Section Break") {
// 		$(grid_row.row).css({"font-weight": "bold"});
// 	}
// })

cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	if(doc.__islocal && (user !== "Administrator" || !frappe.boot.developer_mode)) {
		cur_frm.set_value("custom", 1);
		cur_frm.toggle_enable("custom", 0);
	}

	if(!frappe.boot.developer_mode && !doc.custom) {
		// make the document read-only
		cur_frm.set_read_only();
	}
}

cur_frm.cscript.validate = function(doc, cdt, cdn) {
	doc.server_code_compiled = null;
}
