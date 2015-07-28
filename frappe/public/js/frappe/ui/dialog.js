// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.ui');

var cur_dialog;

frappe.ui.open_dialogs = [];
frappe.ui.Dialog = frappe.ui.FieldGroup.extend({
	init: function(opts) {
		this.display = false;
		this.is_dialog = true;

		$.extend(this, opts);
		this._super();
		this.make();
	},
	make: function() {
		this.$wrapper = frappe.get_modal("", "");
		this.wrapper = this.$wrapper.find('.modal-dialog')
			.get(0);
		this.make_head();
		this.body = this.$wrapper.find(".modal-body").get(0);

		// make fields (if any)
		this._super();

		// show footer
		if(this.primary_action) {
			this.set_primary_action(this.primary_action_label || __("Submit"), this.primary_action);
		}

		var me = this;
		this.$wrapper
			.on("hide.bs.modal", function() {
				me.display = false;
				if(frappe.ui.open_dialogs[frappe.ui.open_dialogs.length-1]===me) {
					frappe.ui.open_dialogs.pop();
					if(frappe.ui.open_dialogs.length)
						cur_dialog = frappe.ui.open_dialogs[frappe.ui.open_dialogs.length-1];
					else
						cur_dialog = null;
				}
				me.onhide && me.onhide();
			})
			.on("shown.bs.modal", function() {
				// focus on first input
				me.display = true;
				cur_dialog = me;
				frappe.ui.open_dialogs.push(me);
				me.focus_on_first_input();
				me.on_page_show && me.on_page_show();
			});

	},
	focus_on_first_input: function() {
		var first = $(this.body).find(':input:first');
		if(first.length && first.attr("data-fieldtype")!="Date") {
			try {
				first.get(0).focus();
			} catch(e) {
				console.log("Dialog: unable to focus on first input: " + e);
			}
		}
	},
	get_primary_btn: function() {
		return this.$wrapper.find(".modal-header .btn-primary");
	},
	set_primary_action: function(label, click) {
		this.has_primary_action = true;
		var me = this;
		return this.get_primary_btn()
			.removeClass("hide")
			.html(label)
			.click(function() {
				me.primary_action_fulfilled = true;
				click();
			});
	},
	make_head: function() {
		var me = this;
		this.set_title(this.title);
	},
	set_title: function(t) {
		this.$wrapper.find(".modal-title").html(t);
	},
	show: function() {
		// show it
		this.$wrapper.modal("show");
		this.primary_action_fulfilled = false;
	},
	hide: function(from_event) {
		this.$wrapper.modal("hide");
	},
	get_close_btn: function() {
		return this.$wrapper.find(".btn-modal-close");
	},
	no_cancel: function() {
		this.get_close_btn().toggle(false);
	},
	cancel: function() {
		this.get_close_btn().trigger("click");
	}
});

// close open dialogs on ESC
$(document).bind('keydown', function(e) {
	if(cur_dialog && !cur_dialog.no_cancel_flag && e.which==27) {
		cur_dialog.cancel();
	}
});
