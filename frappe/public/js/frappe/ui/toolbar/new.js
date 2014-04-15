// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

frappe.ui.toolbar.NewDialog = frappe.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: __("New Record"),
			execute: function(val) {
				new_doc(val);
			},
		});
		
		// get new types
		this.set_values(frappe.boot.user.can_create.join(',').split(','));
	}
});
