// bind events

frappe.ui.form.on("ToDo", "refresh", function(frm) {
	frm.add_custom_button((frm.doc.status=="Open" ? __("Close") : __("Re-open")), function() {
		frm.set_value("status", frm.doc.status=="Open" ? "Closed" : "Open");
		frm.save();
	});
	
	if(frm.doc.reference_type && frm.doc.reference_name) {
		frm.set_intro('Reference: <a href="#Form/'+frm.doc.reference_type+'/'+frm.doc.reference_name+'">' 
			+ frm.doc.reference_name + '</a>');
	}
});