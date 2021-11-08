frappe.ui.form.ControlReadOnly = class ControlReadOnly extends frappe.ui.form.ControlData {
	get_status(explain) {
		var status = super.get_status(explain);
		if(status==="Write")
			status = "Read";
		return;
	}
};
