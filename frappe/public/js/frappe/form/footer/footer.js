// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import './timeline.js';

frappe.ui.form.Footer = Class.extend({
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
		this.make();
		this.make_comments();
		// render-complete
		$(this.frm.wrapper).on("render_complete", function() {
			me.refresh();
		});
	},
	make: function() {
		var me = this;
		this.wrapper = $(frappe.render_template("form_footer", {}))
			.appendTo(this.parent);
		this.wrapper.find(".btn-save").click(function() {
			me.frm.save('Save', null, this);
		})

	},
	make_comments: function() {
		this.frm.timeline = new frappe.ui.form.Timeline({
			parent: this.wrapper.find(".form-comments"),
			frm: this.frm
		});
	},
	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.parent.addClass("hide");
		} else {
			this.parent.removeClass("hide");
			this.frm.timeline.refresh();
		}
	},
});
