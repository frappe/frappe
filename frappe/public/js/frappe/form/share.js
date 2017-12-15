// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.Share = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	},
	refresh: function() {
		this.render_sidebar();
	},
	render_sidebar: function() {
		var me = this;
		this.parent.empty();

		var shared = this.shared || this.frm.get_docinfo().shared;
		shared = shared.filter(function(d) { return d });
		var users = [];
		for (var i=0, l=shared.length; i < l; i++) {
			var s = shared[i];

			if (s.everyone) {
				users.push({
					icon: "octicon octicon-megaphone text-muted",
					avatar_class: "avatar-empty share-doc-btn shared-with-everyone",
					title: __("Shared with everyone")
				});
			} else {
				var user_info = frappe.user_info(s.user);
				users.push({
					image: user_info.image,
					fullname: user_info.fullname,
					abbr: user_info.abbr,
					color: user_info.color,
					title: __("Shared with {0}", [user_info.fullname])
				});
			}
		}

		if (!me.frm.doc.__islocal) {
			users.push({
				icon: "octicon octicon-plus text-muted",
				avatar_class: "avatar-empty share-doc-btn",
				title: __("Share")
			});
		}

		this.parent.append(frappe.render_template("users_in_sidebar", {"users": users}));
		this.parent.find(".avatar").on("click", function() {
			me.frm.share_doc();
		});
	},
	show: function() {
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __("Share {0} with", [this.frm.doc.name]),
		});

		this.dialog = d;
		this.dirty = false;

		frappe.call({
			method: "frappe.share.get_users",
			args: {
				doctype: this.frm.doctype,
				name: this.frm.doc.name
			},
			callback: function(r) {
				me.render_shared(r.message || []);
			}
		});

		$(d.body).html('<p class="text-muted">' + __("Loading...") + '</p>');

		d.onhide = function() {
			// reload comments
			if(me.dirty) me.frm.reload_docinfo();
		}

		d.show();
	},
	render_shared: function(shared) {
		if(shared)
			this.shared = shared;
		var d = this.dialog;
		$(d.body).empty();

		var everyone = {};
		$.each(this.shared, function(i, s) {
			// pullout everyone record from shared list
			if (s && s.everyone) {
				everyone = s;
			}
		});

		$(frappe.render_template("set_sharing", {frm: this.frm, shared: this.shared, everyone: everyone}))
			.appendTo(d.body);

		if(frappe.model.can_share(null, this.frm)) {
			this.make_user_input();
			this.add_share_button();
			this.set_edit_share_events();
		} else {
			// if cannot share, disable sharing settings.
			$(d.body).find(".edit-share").prop("disabled", true);
		}
	},
	make_user_input: function() {
		// make add-user input
		this.dialog.share_with = frappe.ui.form.make_control({
			parent: $(this.dialog.body).find(".input-wrapper-add-share"),
			df: {
				fieldtype: "Link",
				label: __("Share With"),
				fieldname: "share_with",
				options: "User",
				filters: {
					"user_type": "System User",
					"name": ["!=", frappe.session.user]
				}
			},
			only_input: true,
			render_input: true
		});

	},
	add_share_button: function() {
		var me = this, d = this.dialog;
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
					share: $(d.body).find(".add-share-share").prop("checked") ? 1 : 0,
					notify: $(d.body).find(".add-share-notify").prop("checked") ? 1 : 0
				},
				btn: this,
				callback: function(r) {
					$.each(me.shared, function(i, s) {
						if(s && s.user===r.message.user) {
							// re-adding / remove the old share rule.
							delete me.shared[i];
						}
					})
					me.dirty = true;
					me.shared.push(r.message);
					me.render_shared();
					me.frm.shared.refresh();
				}
			});
		});
	},
	set_edit_share_events: function() {
		var me = this, d = this.dialog;
		$(d.body).find(".edit-share").on("click", function() {
			var user = $(this).parents(".shared-user:first").attr("data-user") || "",
				value = $(this).prop("checked") ? 1 : 0,
				property = $(this).attr("name"),
				everyone = cint($(this).parents(".shared-user:first").attr("data-everyone"));

			frappe.call({
				method: "frappe.share.set_permission",
				args: {
					doctype: me.frm.doctype,
					name: me.frm.doc.name,
					user: user,
					permission_to: property,
					value: value,
					everyone: everyone
				},
				callback: function(r) {
					var found = null;
					$.each(me.shared, function(i, s) {
						// update shared object
						if(s && (s.user===user || (everyone && s.everyone===1))) {
							if(!r.message) {
								delete me.shared[i];
							} else {
								me.shared[i] = $.extend(s, r.message);
							}
							found = true;
							return false;
						}
					});

					if (!found) {
						me.shared.push(r.message);
					}

					me.dirty = true;
					me.render_shared();
					me.frm.shared.refresh();
				}
			});
		});
	},
});
