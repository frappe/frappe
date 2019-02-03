frappe.ready(function() {
	// bind events here
	setTimeout(() => {
		var form = frappe.web_form.field_group.fields_dict;
		form.user.set_input(frappe.session.user);
	}, 1000);
});