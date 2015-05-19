frappe.ui.form.on("Contact Us Settings", {
	"refresh": function(frm) {
		frm.sidebar.add_user_action("See on Website").attr("href", "/contact").attr("target", "_blank");
	}
});
