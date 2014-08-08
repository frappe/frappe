// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("Event", "refresh", function(frm) {
	if(frm.doc.ref_type && frm.doc.ref_name) {
		frm.add_custom_button(__(frm.doc.ref_name), function() {
			frappe.set_route("Form", frm.doc.ref_type, frm.doc.ref_name);
		}, frappe.boot.doctype_icons[frm.doc.ref_type]);
	}
});


cur_frm.cscript.repeat_on = function(doc, cdt, cdn) {
	if(doc.repeat_on==="Every Day") {
		$.each(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], function(i,v) {
			cur_frm.set_value(v, 1);
		})
	}
}

