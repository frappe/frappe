/**
 * frappe.views.InboxView
 */

frappe.provide("frappe.views");

frappe.views.InboxView = class InboxView extends frappe.views.ListView {
	static load_last_view() {
		const route = frappe.get_route();
		if (!route[3] && frappe.boot.email_accounts.length) {
			let email_account;
			if (frappe.boot.email_accounts[0].email_id == "All Accounts") {
				email_account = "All Accounts";
			} else {
				email_account = frappe.boot.email_accounts[0].email_account;
			}
			frappe.set_route("List", "Communication", "Inbox", email_account);
			return true;
		} else if (!route[3] || (route[3] !== "All Accounts" && !is_valid(route[3]))) {
			frappe.throw(__('No email account associated with the User. Please add an account under User > Email Inbox.'));
		}
		return false;

		function is_valid(email_account) {
			return frappe.boot.email_accounts.find(d => d.email_account === email_account);
		}
	}

	get view_name() {
		return 'Inbox';
	}

	show() {
		super.show();
		// save email account in user_settings
		this.save_view_user_settings({
			last_email_account: this.current_email_account
		});
	}

	setup_defaults() {
		super.setup_defaults();
		this.email_account = frappe.get_route()[3];
		this.page_title = this.email_account;
		this.filters = this.get_inbox_filters();
	}

	get is_sent_emails() {
		const f = this.filter_area.get()
			.find(filter => filter[1] === 'sent_or_received');
		return f && f[3] === 'Sent';
	}

	render() {
		this.emails = this.data;
		this.render_inbox_view();
	}

	render_inbox_view() {
		let html = this.emails.map(this.render_email_row.bind(this)).join("");

		this.$result.html(`
			${this.get_header_html()}
			${html}
		`);
	}

	get_header_html() {
		return this.get_header_html_skeleton(`
			<div class="list-row-col list-subject level">
				<input class="level-item list-check-all hidden-xs" type="checkbox" title="Select All">
				<span class="level-item">${__('Subject')}</span>
			</div>
			<div class="list-row-col hidden-xs">
				<span>${this.is_sent_emails ? __("To") : __("From")}</span>
			</div>
		`);
	}

	render_email_row(email) {
		if (!email.css_seen && email.seen)
			email.css_seen = "seen";

		const columns_html = `
			<div class="list-row-col list-subject level ellipsis">
				<input class="level-item list-row-checkbox hidden-xs" type="checkbox" data-name="${email.name}">
				<span class="level-item">
					<a class="${ email.seen ? '' : 'bold'} ellipsis" href="${this.get_form_link(email)}">
						${email.subject}
					</a>
				</span>
			</div>
			<div class="list-row-col hidden-xs">
				<span>${this.is_sent_emails ? email.recipients : email.sender }</span>
			</div>
		`;

		return this.get_list_row_html_skeleton(columns_html, this.get_meta_html(email));
	}

	get_meta_html(email) {
		const attachment = email.has_attachment ?
			`<span class="fa fa-paperclip fa-large" title="${__('Has Attachments')}"></span>` : '';

		const form_link = frappe.utils.get_form_link(email.reference_doctype, email.reference_name);
		const link = email.reference_doctype && email.reference_doctype !== this.doctype ?
			`<a class="text-muted grey" href="${form_link}"
				title="${__('Linked with {0}', [email.reference_doctype])}">
				<i class="fa fa-link fa-large"></i>
			</a>` : '';

		const modified = comment_when(email.modified, true);

		return `
			<div class="level-item hidden-xs list-row-activity">
				${link}
				${attachment}
				${modified}
			</div>
		`;
	}

	get_inbox_filters() {
		var email_account = this.email_account;
		var default_filters = [
			["Communication", "communication_type", "=", "Communication", true],
			["Communication", "communication_medium", "=", "Email", true],
		];
		var filters = [];
		if (email_account === "Sent") {
			filters = default_filters.concat([
				["Communication", "sent_or_received", "=", "Sent", true],
				["Communication", "email_status", "not in", "Spam,Trash", true],
			]);
		} else if (in_list(["Spam", "Trash"], email_account)) {
			filters = default_filters.concat([
				["Communication", "email_status", "=", email_account, true],
				["Communication", "email_account", "in", frappe.boot.all_accounts, true]
			]);
		} else {
			var op = "=";
			if (email_account == "All Accounts") {
				op = "in";
				email_account = frappe.boot.all_accounts;
			}

			filters = default_filters.concat([
				["Communication", "sent_or_received", "=", "Received", true],
				["Communication", "email_account", op, email_account, true],
				["Communication", "email_status", "not in", "Spam,Trash", true],
			]);
		}

		return filters;
	}

	get_no_result_message() {
		var email_account = this.email_account;
		var args;
		if (in_list(["Spam", "Trash"], email_account)) {
			return __("No {0} mail", [email_account]);
		} else if (!email_account && !frappe.boot.email_accounts.length) {
			// email account is not configured
			args = {
				doctype: "Email Account",
				msg: __("No Email Account"),
				label: __("New Email Account"),
			};
		} else {
			// no sent mail
			args = {
				doctype: "Communication",
				msg: __("No Emails"),
				label: __("Compose Email")
			};
		}

		const html = frappe.model.can_create(args.doctype) ?
			`<p>${args.msg}</p>
			<p>
				<button class="btn btn-primary btn-sm btn-new-doc">
					${args.label}
				</button>
			</p>
			` :
			`<p>${ __("No Email Accounts Assigned") }</p>`;

		return `
			<div class="msg-box no-border">
				${html}
			</div>
		`;
	}

	make_new_doc() {
		if (!this.email_account && !frappe.boot.email_accounts.length) {
			frappe.route_options = {
				'email_id': frappe.session.user_email
			};
			frappe.new_doc('Email Account');
		} else {
			new frappe.views.CommunicationComposer({
				doc: {}
			});
		}
	}
};
