// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Website Route Meta', {
	refresh: function(frm) {
		frm.get_field('__newname').set_label('Route');
		frm.add_custom_button(__('Visit Web Page'), () => {
			let route = frm.doc.name;
			if (!route.startsWith('/')) {
				route = '/' + route;
			}
			window.open(route, '_blank');
		});
	}
});
