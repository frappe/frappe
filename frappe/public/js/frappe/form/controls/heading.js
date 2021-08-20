frappe.ui.form.ControlHeading = frappe.ui.form.ControlHTML.extend({
	get_content: function() {
		return "<h4>" + __(this.df.label) + "</h4>";
	}
});
