// bind events

frappe.ui.form.on("ToDo", "refresh", function(frm) {
	if(frm.doc.reference_type && frm.doc.reference_name) {
		frm.add_custom_button(__(frm.doc.reference_name), function() {
			frappe.set_route("Form", frm.doc.reference_type, frm.doc.reference_name);
		}, frappe.boot.doctype_icons[frm.doc.reference_type]);
	}

	if (!frm.doc.__islocal) {
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
	}
});
