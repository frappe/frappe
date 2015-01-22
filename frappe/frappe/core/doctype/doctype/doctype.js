// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// -------------
// Menu Display
// -------------

$(cur_frm.wrapper).on("grid-row-render", function(e, grid_row) {
	if(grid_row.doc && grid_row.doc.fieldtype=="Section Break") {
		$(grid_row.row).css({"font-weight": "bold"});
	}
})

cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	if(in_list(user_roles, 'System Manager') && !in_list(user_roles, 'Administrator')) {
		// make the document read-only
		cur_frm.set_read_only();

		// make help heading
		msgprint($.format())
		msgprint(__('Cannot Edit {0} directly: To edit {0} properties, create / update {1}, {2} and {3}', [
				'DocType',
				'<a href="#!List/Custom%20Field">'+ __('Custom Field')+'</a>',
				'<a href="#!List/Custom%20Script">'+ __('Custom Script')+'</a>',
				'<a href="#!List/Property%20Setter">'+ __('Property Setter')+'</a>',
			]));
	}
}

cur_frm.cscript.validate = function(doc, cdt, cdn) {
	doc.server_code_compiled = null;
}
