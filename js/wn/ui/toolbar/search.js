wn.ui.toolbar.Search = wn.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: "Search",
			execute: function(val) {
				selector.set_search(val);
				selector.show();
			},
		});
		
		// get new types
		this.set_values(profile.can_read.join(',').split(','));
		
		// global search selector
		makeselector();
	}
});