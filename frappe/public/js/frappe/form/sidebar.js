frappe.provide("frappe.ui.form");
frappe.ui.form.Sidebar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.parent.addClass("hidden-xs");
		this.wrapper = $(frappe.render_template("form_sidebar",
			{doctype: this.frm.doctype, frm:this.frm}))
			.appendTo(this.parent);
		this.$user_actions = this.wrapper.find(".user-actions");
	},
	add_user_action: function(label, click) {
		$('<a>').html(label).appendTo($('<li>')
			.appendTo(this.$user_actions.removeClass("hide"))).on("click", click);
	},
	clear_user_actions: function() {
		this.$user_actions.empty().addClass("hide");
	},
	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.wrapper.toggle(false);
		} else {
			this.wrapper.toggle(true);
			this.wrapper.find(".created-by").html(frappe.user.full_name(this.frm.doc.owner) +
				"<br>" + comment_when(this.frm.doc.creation));
			this.wrapper.find(".modified-by").html(frappe.user.full_name(this.frm.doc.modified_by) +
				"<br>" + comment_when(this.frm.doc.modified));
		}
	}
})
