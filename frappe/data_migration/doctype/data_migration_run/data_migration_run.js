// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Migration Run', {
	refresh: function(frm) {
		if (frm.doc.status !== 'Success') {
			frm.add_custom_button(__('Run'), () => frm.call('run'));
		}
		if (frm.doc.status === 'Started') {
			frm.dashboard.add_progress(__('Percent Complete'), frm.doc.percent_complete,
				__('Currently updating {0}', [frm.doc.current_mapping]));
		}
	}
});
