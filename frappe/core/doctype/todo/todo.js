// bind events

frappe.ui.form.on("ToDo", "refresh", function(frm) {
	if(frm.doc.status=="Open") {
		frm.add_custom_button(__("Close"), function() {
			frm.set_value("status", "Closed");
			frm.save();
		}, "icon-ok", "btn-success");
	} else {
		frm.add_custom_button(__("Re-open"), function() {
			frm.set_value("status", "Open");
			frm.save();
		}, null, "btn-default");
	}

	if(frm.doc.reference_type && frm.doc.reference_name) {
		frm.set_intro('Reference: <a href="#Form/'+frm.doc.reference_type+'/'+frm.doc.reference_name+'">'
			+ frm.doc.reference_name + '</a>');
	} else {
		frm.set_intro();
	}
});
