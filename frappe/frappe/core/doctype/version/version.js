frappe.ui.form.on("Version", "refresh", function(frm) {
	frm.add_custom_button("Restore", function() {
		frappe.call({
			method:"frappe.core.doctype.version.version.restore",
			args: {
				version: frm.doc.name
			},
			callback: function(r) {
				if(!r.exc) {
					msgprint(__("Version restored"));
				}
			}
		})
	});
})
