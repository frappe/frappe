frappe.ui.form.ControlImage = frappe.ui.form.Control.extend({
	make: function() {
		this._super();
		this.$wrapper.css({"margin": "0px"});
		this.$body = $("<div></div>").appendTo(this.$wrapper)
			.css({"margin-bottom": "10px"});
		$('<div class="clearfix"></div>').appendTo(this.$wrapper);
	},
	refresh_input: function() {
		this.$body.empty();

		var doc = this.get_doc();
		if(doc && this.df.options && doc[this.df.options]) {
			this.$img = $("<img src='"+doc[this.df.options]+"' class='img-responsive'>")
				.appendTo(this.$body);
		} else {
			this.$buffer = $(`<div class='missing-image'>${frappe.utils.icon('restriction', 'md')}</div>`)
				.appendTo(this.$body);
		}
		return false;
	}
});
