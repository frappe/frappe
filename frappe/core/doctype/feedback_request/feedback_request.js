// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Feedback Request', {
	refresh: function(frm) {
		var rating_icons = frappe.render_template("rating_icons", {rating: frm.doc.rating, show_label: false});
		$(frm.fields_dict.feedback_rating.wrapper).html(rating_icons);

		if(frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__(frm.doc.reference_name), function() {
				frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
			});
		}

		if(frm.doc.reference_communication){
			frm.add_custom_button(__("Communication"), function() {
				frappe.set_route("Form", "Communication", frm.doc.reference_communication);
			});
		}
	}
});
