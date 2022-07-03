frappe.ui.form.on("Email Domain", {
	onload: function(frm) {
		if (!frm.doc.__islocal) {
			frm.dashboard.clear_headline();
			let msg = __("Changing any setting will reflect on all the email accounts associated with this domain.");
			frm.dashboard.set_headline_alert(msg);
		}
	}
})
