frappe.ui.form.on("Print Format", "onload", function(frm) {
	frm.add_fetch("doc_type", "module", "module");
});

frappe.ui.form.on("Print Format", "refresh", function(frm) {
	frm.set_intro("");
	if (user!="Administrator") {
		if (frm.doc.standard == 'Yes') {
			frm.toggle_enable(["html", "doc_type", "module"], false);
			frm.disable_save();
		} else {
			frm.toggle_enable(["html", "doc_type", "module"], true);
			frm.enable_save();
		}
		frm.toggle_enable("standard", false);
	} else {
		if(frm.doc.standard==="Yes") {
			frm.set_intro(__("This is a standard format. To make changes, please copy it make make a new format."))
		}
	}
})
