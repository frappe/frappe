frappe.ui.form.on("Print Format", "onload", function(frm) {
	frm.add_fetch("doc_type", "module", "module");
});

frappe.ui.form.on("Print Format", "refresh", function(frm) {
	frm.set_intro("");
	frm.toggle_enable(["html", "doc_type", "module"], false);
	if (user==="Administrator" || frm.doc.standard==="No") {
		frm.toggle_enable(["html", "doc_type", "module"], true);
		frm.enable_save();
	}

	if(frm.doc.standard==="Yes" && user !== "Administrator") {
		frm.set_intro(__("Please duplicate this to make changes"));
	}

	if(!frm.is_new()) {
		frm.add_custom_button(__("Edit Format"), function() {
			if(!frm.doc.doc_type) {
				msgprint(__("Please select DocType first"));
				return;
			}
			frappe.set_route("print-format-builder", frm.doc.name);
		});

		frm.add_custom_button(__("Make Default"), function() {
			frappe.call({
				method: "frappe.print.doctype.print_format.print_format.make_default",
				args: {
					name: frm.doc.name
				}
			})
		});
	}
});
