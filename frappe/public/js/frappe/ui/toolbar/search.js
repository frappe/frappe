// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.toolbar.Search = frappe.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: __("Search"),
			execute: function(val) {
				frappe.set_route("List", val, {"name": "%"});
			},
			help: __("Shortcut") + ": Ctrl+G"
		});
		
		// get new types
		this.set_values(frappe.boot.user.can_search.join(',').split(','));
	}
});
