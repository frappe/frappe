// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.ui.toolbar.Search = wn.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: wn._("Search"),
			execute: function(val) {
				new wn.ui.Search({doctype:val});
			},
			help: wn._("Shortcut") + ": Ctrl+G"
		});
		
		// get new types
		this.set_values(wn.boot.profile.can_search.join(',').split(','));
	}
});
