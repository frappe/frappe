wn.ui.toolbar.Report = wn.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: "Start Report For",
			execute: function(val) {
				loadreport(val, null, null, null, 1);
			},
		});
		
		// get new types
		this.set_values(profile.can_get_report.join(',').split(','));
	}
});

wn.ui.toolbar.report = new wn.ui.toolbar.Report();