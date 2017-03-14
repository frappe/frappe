/**
 * frappe.views.EmailInboxView
 */

 frappe.provide("frappe.views");

frappe.views.InboxView = frappe.views.ListRenderer.extend({
	name: 'Inbox',
	render_view: function(values) {
		var me = this;

		this.emails = values;
		// save email account in user_settings
		frappe.model.user_settings.save("Communication", 'Inbox', {
			last_email_account: this.current_email_account
		});

		this.render_inbox_view();
	},
	render_inbox_view: function() {
		var html = ""

		email_account = this.get_current_email_account()
		if(email_account)
			html = this.emails.map(this.render_email_row.bind(this)).join("");
		else
			html = this.get_inbox_selector_html()

		this.container = $('<div>')
			.addClass('inbox-container')
			.appendTo(this.wrapper);
		this.container.append(html);

		if(!this.current_email_account)
			this.bind_email_inbox_selector()
	},
	render_email_row: function(email) {
		if(!email.css_seen && email.seen)
			email.css_seen = "seen"

		return frappe.render_template("inbox_view_item_row", {
			data: email,
			is_sent_emails: this.is_sent_emails,
		});
	},
	set_defaults: function() {
		this._super();
		this.page_title = __("Email Inbox");
	},

	init_settings: function() {
		this._super();
		// this.show_no_result = false;
		this.filters = this.get_inbox_filters();
	},
	should_refresh: function() {
		var to_refresh = this._super();
		if(!to_refresh) {
			this.last_email_account = this.current_email_account || '';
			this.current_email_account = this.get_current_email_account();
			this.is_sent_emails = this.current_email_account === "Sent"? true: false

			to_refresh = this.current_email_account !== this.last_email_account;
		}

		if(to_refresh){
			this.list_view.page.main.find(".list-headers").empty();
		}
		return to_refresh;
	},
	get_inbox_filters: function() {
		var email_account = this.get_current_email_account();
		var default_filters = [
			["Communication", "communication_type", "=", "Communication", true],
			["Communication", "communication_medium", "=", "Email", true],
			
		]
		var filters = []
		if (email_account === "Sent") {
			filters = default_filters.concat([
				["Communication", "sent_or_received", "=", "Sent", true],
				["Communication", "email_status", "not in", "Spam,Trash", true],
			])
		}
		else if (inList(["Spam", "Trash"], email_account)) {
			filters = default_filters.concat([
				["Communication", "email_status", "=", email_account, true],
				["Communication", "email_account", "in", frappe.boot.all_accounts, true]
			])
		}
		else {
			filters = default_filters.concat([
				["Communication", "sent_or_received", "=", "Received", true],
				["Communication", "email_account", "=", email_account, true],
				["Communication", "email_status", "not in", "Spam,Trash", true],
			])
		}

		return filters
	},
	get_header_html: function() {
		var header = ""
		if(this.current_email_account) {
			header = frappe.render_template('inbox_view_item_main_head', {
				_checkbox: ((frappe.model.can_delete(this.doctype) || this.settings.selectable)
					&& !this.no_delete),
				is_sent_emails: this.is_sent_emails
			});
		}

		return header;
	},
	get_current_email_account: function() {
		var route = frappe.get_route();
		if(!route[3] || !frappe.boot.email_accounts.find(b => b.email_account === route[3])) {
			// frappe.throw(__(`Email Account <b>${route[3] || ''}</b> not found`));
			return "";
		}
		return route[3];
	},
	make_no_result: function () {
		var no_result_message = ""
		email_account = this.get_current_email_account();	
		if (inList(["Spam", "Trash"], email_account)) {
			return __("No {0} mail", [email_account])
		} else if(!email_account) {
			// email account is not configured
			this.no_result_doctype = "Email Account"
			args = {
				doctype: "Email Account",
				label: "New Email Account"
			}
		} else {
			// no sent mail
			this.no_result_doctype = "Communication";
			args = {
				doctype: "Communication",
				label: "Compose Email"
			}
		}
		var no_result_message = frappe.render_template("inbox_no_result", args)
		return no_result_message;
	},

	get_inbox_selector_html: function() {
		email_account_map = {}
		$.each(frappe.boot.email_accounts, function(idx, account){
			email_account_map[account.email_id] = account.email_account
		});
		html = frappe.render_template("select_email_inbox", {
			email_accounts: email_account_map,
			current_email_account: this.current_email_account,
			is_system_manager: has_common(["System Manager", "Administrator"], roles),
			is_inbox_configured: Object.keys(email_account_map).length
		})

		if(!Object.keys(email_account_map).length)
			this.no_result_doctype = "Email Account"

		return html
	},
	bind_email_inbox_selector: function() {
		// bind email_account on_change event
		var me = this;
		this.container.find('select[data-fieldname="email_inbox"]').on("change", function(event) {
			inbox = $(event.target).val();
			frappe.set_route("List", "Communication", "Inbox", inbox)
		})
	},
	make_new_doc: function() {
		if (this.no_result_doctype == "Communication") {
			new frappe.views.CommunicationComposer({
				doc: {}
			})
		} else {
			frappe.new_doc(this.no_result_doctype)
		}
	}
});
