frappe.ui.form.ControlReadOnly = frappe.ui.form.ControlData.extend({
	get_status: function(explain) {
		var status = this._super(explain);
		if(status==="Write")
			status = "Read";
		return;
	},
});
