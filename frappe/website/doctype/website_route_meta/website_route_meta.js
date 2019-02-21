// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Website Route Meta', {
	refresh: function(frm) {
		frm.get_field('__newname').set_label('Route');
	}
});
