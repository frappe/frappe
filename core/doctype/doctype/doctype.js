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

cur_frm.cscript.allow_attach = function(doc, cdt, cdn) {
	if(doc.allow_attach) {
		unhide_field('max_attachments');
	} else {
		hide_field('max_attachments');
	}
}

cur_frm.cscript.onload = function(doc, cdt, cdn) {
	this.allow_attach(doc, cdt, cdn);
}

cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	if(in_list(user_roles, 'System Manager') && !in_list(user_roles, 'Administrator')) {
		// make the document read-only
		cur_frm.perm = [[1,0,0]]
		
		// make help heading
		msgprint('<b>Cannot Edit DocType directly</b>: \
			To edit DocType properties, \
			create / update <a href="#!List/Custom%20Field">Custom Field</a>, \
			<a href="#!List/Custom%20Script">Custom Script</a> \
			and <a href="#!List/Property%20Setter">Property Setter</a>')
	}
}

cur_frm.cscript.validate = function(doc, cdt, cdn) {
	doc.server_code_compiled = null;
}