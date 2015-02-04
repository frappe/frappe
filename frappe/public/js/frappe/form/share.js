// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.Share = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	},
	show: function() {
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __("Share {0} with", [this.frm.doc.name]),
		});

		frappe.call({
			method: "frappe.share.get_users",
			args: {
				doctype: this.frm.doctype,
				name: this.frm.doc.name
			},
			callback: function(r) {
				d.shared = r.message || [];
				d.render_shared();
			}
		});

		d.render_shared = function() {
			$(d.body).empty();
			$(frappe.render_template("set_sharing", {frm: me.frm, shared: d.shared}))
				.appendTo(d.body);

			if(!frappe.model.can_share(null, me.frm)) {
				return;
			}

			// make add-user input
			d.share_with = frappe.ui.form.make_control({
				parent: $(d.body).find(".input-wrapper-add-share"),
				df: {
					fieldtype: "Link",
					label: __("Share With"),
					fieldname: "share_with",
					options: "User",
					filters: {
						"user_type": "System User",
						"name": ["!=", user]
					}
				},
				only_input: true,
				render_input: true
			});

			// add share action
			$(d.body).find(".btn-add-share").on("click", function() {
				var user = d.share_with.get_value();
				if(!user) {
					return;
				}
				frappe.call({
					method: "frappe.share.add",
					args: {
						doctype: me.frm.doctype,
						name: me.frm.doc.name,
						user: user,
						read: $(d.body).find(".add-share-read").prop("checked") ? 1 : 0,
						write: $(d.body).find(".add-share-write").prop("checked") ? 1 : 0,
						share: $(d.body).find(".add-share-share").prop("checked") ? 1 : 0
					},
					callback: function(r) {
						d.shared.push(r.message);
						d.render_shared();
					}
				});
			});
		}

		$(d.body).html('<p class="text-muted">' + __("Loading...") + '</p>');

		d.show();
	}
});
