// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt



frappe.ui.form.Share = class Share {
	constructor(opts) {
		$.extend(this, opts);
		this.shares = this.parent.find('.shares');
		this.share_link = this.parent.find('.share-link');
	}
	refresh() {
		this.render_sidebar();
	}
	render_sidebar() {
		const shared = this.shared || this.frm.get_docinfo().shared;
		const shared_users = shared.filter(Boolean).map(s => s.user);
		this.share_link.click(() => {
			this.share_modal();
		});

		if (this.frm.is_new()) {
			this.parent.find(".share-doc-btn").hide();
		}

		this.parent.find(".share-doc-btn").on("click", () => {
			this.frm.share_doc();
		});

		this.shares.empty();

		if (!shared_users.length) {
			this.shares.hide();
			return;
		}

		this.shares.show();
		// REDESIGN-TODO: handle "shared with everyone"
		this.shares.append(frappe.avatar_group(shared_users, 5, {'align': 'left', 'overlap': true}));
	}
	show() {
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
			if(me.dirty) me.frm.sidebar.reload_docinfo();
		}

		d.show();
	}
	render_shared(shared) {
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
	}
	make_user_input() {
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

	}
	add_share_button() {
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
					submit: $(d.body).find(".add-share-submit").prop("checked") ? 1 : 0,
					share: $(d.body).find(".add-share-share").prop("checked") ? 1 : 0,
					notify: 1,
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
	}
	set_edit_share_events() {
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
	}
	async share_modal() {
		const default_expiry = frappe.boot.sysdefaults.document_share_key_expiry;
		const share_modal = new frappe.ui.Dialog({
			title: __("Share Link"),
			fields: [{
				fieldname: "link_expiration_date",
				label: __("Link Expiration Date"),
				fieldtype: "Date",
				default: frappe.datetime.add_days(moment(), default_expiry),
				min_date: new Date(),
				description: __("The default expiration date is {0} days from today.", [default_expiry]),
				read_only_depends_on: "eval: doc.link"
			}, {
				fieldtype: "Check",
				label: __("No Expiry"),
				fieldname: "no_expiry",
				change: () => {
					const no_expiry_warning = `<span style="color: var(--red-500);">
						${__('It is not recommended to send links without expiry')}
					</span>`;
					const no_expiry = share_modal.get_value('no_expiry');
					share_modal.get_field('link_expiration_date').toggle(!no_expiry);
					share_modal.get_field('no_expiry')
						.set_description(`${no_expiry ? no_expiry_warning : ''}`);
				},
			}, {
				fieldtype: "Button",
				label: __("Get Link"),
				click: () => {
					this.frm.call("get_new_document_share_key", {
						expires_on: share_modal.get_value("link_expiration_date"),
						no_expiry: share_modal.get_value("no_expiry")
					}).then(res => {
						let key = res.message;
						share_modal.set_value("link", this.frm.get_share_link(key));
					});
				}
			}, {
				fieldname: "link",
				label: __("Link"),
				fieldtype: "Data",
				depends_on: "eval: doc.link",
				with_copy_button: true
			}],
		});

		share_modal.show();
	}
};
