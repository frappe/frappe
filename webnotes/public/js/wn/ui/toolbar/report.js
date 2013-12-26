// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.ui.toolbar.Report = wn.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: wn._("Start Report For"),
			execute: function(val) {
				wn.set_route('Report', val);
			},
		});
		
		// get new types
		this.set_values(profile.can_get_report.join(',').split(','));
	}
});

