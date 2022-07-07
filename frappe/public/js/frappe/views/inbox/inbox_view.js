/**
 * frappe.views.InboxView
 */

frappe.provide("frappe.views");

frappe.views.InboxView = class InboxView extends frappe.views.ListView {

	get view_name() {
		return 'Inbox';
	}

	load_settings() {
		return {
			...super.load_settings(),
		}
	}

	get_default_args() {
		return {
			...super.get_default_args(),
			sort_by: 'communication_date',
			sort_order: 'desc'
		}
	}

	get_settings_args() {

		let email_account = this.email_account;
		const default_filters = [
			["Communication", "communication_type", "=", "Communication", true],
			["Communication", "communication_medium", "=", "Email", true],
		];
		let filters = [];
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
				["Communication", "status", "=", "Open", true],
				["Communication", "email_account", op, email_account, true],
				["Communication", "email_status", "not in", "Spam,Trash", true],
			]);
		}

		return {
			...super.get_settings_args(),
			filters
		}
	}

	setup_defaults() {
		super.setup_defaults();
		this.email_account = frappe.get_route()[3];
		this.page_title = this.email_account;
	}

	setup_columns() {
		// setup columns for list view
		this.columns = [];
		this.columns.push({
			type: 'Subject',
			df: {
				label: __('Subject'),
				fieldname: 'subject'
			}
		});
		this.columns.push({
			type: 'Field',
			df: {
				label: this.is_sent_emails ? __("To") : __("From"),
				fieldname: this.is_sent_emails ? 'recipients' : 'sender'
			}
		});
	}

	get_seen_class(doc) {
		const seen =
			Boolean(doc.seen) || JSON.parse(doc._seen || '[]').includes(frappe.session.user)
				? ''
				: 'bold';
		return seen;
	}

	get is_sent_emails() {
		const f = this.filter_area.get()
			.find(filter => filter[1] === 'sent_or_received');
		return f && f[3] === 'Sent';
	}

	render_header() {
		this.$result.find('.list-row-head').remove();
		this.$result.prepend(this.get_header_html());
	}

	render() {
		this.setup_columns();
		this.render_header();
		this.render_list();
		this.on_row_checked();
		this.render_count();
	}

	get_meta_html(email) {
		const attachment = email.has_attachment ?
			`<span class="fa fa-paperclip fa-large" title="${__('Has Attachments')}"></span>` : '';

		let link = "";
		if (email.reference_doctype && email.reference_doctype !== this.doctype) {
			link = `<a class="text-muted grey"
				href="${frappe.utils.get_form_link(email.reference_doctype, email.reference_name)}"
				title="${__('Linked with {0}', [email.reference_doctype])}">
				<i class="fa fa-link fa-large"></i>
			</a>`;
		}

		const communication_date = comment_when(email.communication_date, true);
		const status =
			email.status == "Closed" ? `<span class="fa fa-check fa-large" title="${__(email.status)}"></span>` :
				email.status == "Replied" ? `<span class="fa fa-mail-reply fa-large" title="${__(email.status)}"></span>` :
					"";

		return `
			<div class="level-item list-row-activity">
				${link}
				${attachment}
				${status}
				${communication_date}
			</div>
		`;
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
			const route_options = {
				'email_id': frappe.session.user_email
			};
			frappe.new_doc('Email Account', route_options);
		} else {
			new frappe.views.CommunicationComposer();
		}
	}
};
