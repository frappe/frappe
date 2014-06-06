// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("Event", "refresh", function(frm) {
	if(frm.doc.ref_type && frm.doc.ref_name) {
		frm.set_intro('Reference: <a href="#Form/'+frm.doc.ref_type+'/'+frm.doc.ref_name+'">'
			+ frm.doc.ref_name + '</a>');
	} else {
		frm.set_intro();
	}
});


cur_frm.cscript.repeat_on = function(doc, cdt, cdn) {
	if(doc.repeat_on==="Every Day") {
		$.each(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], function(i,v) {
			cur_frm.set_value(v, 1);
		})
	}
}

