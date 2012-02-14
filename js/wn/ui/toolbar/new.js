wn.ui.toolbar.NewDialog = wn.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: "New Record",
			execute: function(val) {
				new_doc(val);
			},
		});
		
		// get new types
		this.set_values(profile.can_create.join(',').split(','));
	}
});
