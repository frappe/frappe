/* eslint semi: "never" */
frappe.ui.form.on('Chat Profile', {
	refresh: (form) => {
		if ( form.doc.user !== frappe.session.user ) {
			form.disable_save(true)
			form.set_read_only(true)
		}
	}
});
