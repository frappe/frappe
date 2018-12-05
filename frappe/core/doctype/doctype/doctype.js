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

frappe.ui.form.on('DocType', {
	onload: function(frm) {
		frm.set_query("authorization_object", "authorization_objects", function() {
			var auth_objs = []
			$.each(frm.doc.authorization_objects, function(key, value){
						if (value.authorization_object != undefined)
							auth_objs.push(value.authorization_object)
							}) 
			return {
				query: "frappe.core.doctype.doctype.doctype.get_authorization_object",
				filters: {
					s_doctype:frm.docname,
					auth_objs: auth_objs
				}
			}
		});
	},
	
	refresh: function(frm) {
		if(frappe.session.user !== "Administrator" || !frappe.boot.developer_mode) {
			if(frm.is_new()) {
				frm.set_value("custom", 1);
			}
			frm.toggle_enable("custom", 0);
			frm.toggle_enable("beta", 0);
		}

		if(!frappe.boot.developer_mode && !frm.doc.custom) {
			// make the document read-only
			frm.set_read_only();
		}

		if(frm.is_new()) {
			if (!(frm.doc.permissions && frm.doc.permissions.length)) {
				frm.add_child('permissions', {role: 'System Manager'});
			}
		} else {
			frm.toggle_enable("engine", 0);
		}

		// set label for "In List View" for child tables
		frm.get_docfield('fields', 'in_list_view').label = frm.doc.istable ?
			__('In Grid View') : __('In List View');
	}
})

// for legacy... :)
cur_frm.cscript.validate = function(doc, cdt, cdn) {
	doc.server_code_compiled = null;
}
