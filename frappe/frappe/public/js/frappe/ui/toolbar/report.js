// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

frappe.ui.toolbar.Report = frappe.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: __("Start Report For"),
			execute: function(val) {
				frappe.set_route('Report', val);
			},
		});
		
		// get new types
		this.set_values(frappe.boot.user.can_get_report.join(',').split(','));
	}
});

