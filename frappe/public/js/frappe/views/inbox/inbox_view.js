/**
 * frappe.views.EmailInboxView
 */

 frappe.provide("frappe.views");

frappe.views.InboxView = frappe.views.ListRenderer.extend({
	name: 'Inbox',
	render_view: function(values) {
		var me = this;
		var email_account = this.get_email_account();
		this.emails = values;
		// save email account in user_settings
		frappe.model.user_settings.save("Communication", 'Inbox', {
			last_email_account: email_account
		});

		this.render_inbox_view();
	},
	render_inbox_view: function() {
		var html = this.emails.map(this.render_email_row.bind(this)).join("");
		this.container = $('<div>')
			.addClass('inbox-container')
			.appendTo(this.wrapper);
		this.container.append(html);
	},
	render_email_row: function(email) {
		if(!email.css_seen && email.seen)
			email.css_seen = "seen"
		if(email.has_attachment)
			email.attachment_html = '<span class="text-muted"><i class="fa fa-paperclip fa-large"></i></span>'

		return frappe.render_template("inbox_view_item_row", {
			data: email,
			is_sent_emails: this.is_sent_emails,
		});
	},
	set_defaults: function() {
		this._super();
		this.show_no_result = false;
		this.page_title = __("Email Inbox");
	},

	init_settings: function() {
		this._super();
		this.filters = this.get_inbox_filters();
	},
	should_refresh: function() {
		var to_refresh = this._super();
		if(!to_refresh) {
			this.last_email_account = this.current_email_account || '';
			this.current_email_account = this.get_email_account();
			this.is_sent_emails = this.current_email_account === "Sent"? true: false

			to_refresh = this.current_email_account !== this.last_email_account;
		}

		if(to_refresh){
			this.list_view.page.main.find(".list-headers").empty();
			this.list_view.init_headers();
		}
		return to_refresh;
	},
	get_inbox_filters: function() {
		var email_account = this.get_email_account();
		var default_filters = [
			["Communication", "communication_type", "=", "Communication", true],
			["Communication", "communication_medium", "=", "Email", true],
			
		]
		var filters = []
		if (email_account === "Sent")
			filters = default_filters.concat([
				["Communication", "sent_or_received", "=", "Sent", true]
			])
		else
			filters = default_filters.concat([
				["Communication", "sent_or_received", "=", "Received", true],
				["Communication", "email_account", "=", email_account, true]
			])

		return filters
	},
	get_header_html: function() {
		var header = frappe.render_template('inbox_view_item_main_head', {
			_checkbox: ((frappe.model.can_delete(this.doctype) || this.settings.selectable)
				&& !this.no_delete),
			is_sent_emails: this.is_sent_emails
		});
		return header;
	},
	get_email_account: function() {
		var route = frappe.get_route();
		if(!route[3] || !frappe.boot.email_accounts.find(b => b.email_account === route[3])) {
			frappe.throw(__(`Email Account <b>${route[3] || ''}</b> not found`));
			return;
		}
		return route[3];
	}
});
