frappe.ui.form.on("Email Domain", {
	email_id: function (frm){
		frm.set_value("domain_name",frm.doc.email_id.split("@")[1])
	},
})
