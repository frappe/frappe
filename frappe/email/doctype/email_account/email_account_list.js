frappe.listview_settings["Email Account"] = {
	onload(listview) {
		// "+ Add" (and the empty-list button) offers one-click provider sign-in on Frappe Cloud
		if (frappe.boot.is_v2_site) {
			listview.settings.primary_action = add_email_account_dialog;
		}

		// set by the provider sign-in callback; Desk drops it from the URL itself
		const code = frappe.route_options?.email_oauth;
		if (code) {
			const mailbox = frappe.route_options.email_oauth_mailbox;
			delete frappe.route_options.email_oauth;
			delete frappe.route_options.email_oauth_mailbox;
			show_email_oauth_result(code, mailbox);
		}
	},
	add_fields: ["default_incoming", "default_outgoing", "enable_incoming", "enable_outgoing"],
	get_indicator: function (doc) {
		if (doc.default_incoming && doc.default_outgoing) {
			var color = doc.enable_incoming && doc.enable_outgoing ? "blue" : "gray";
			return [
				__("Default Sending and Inbox"),
				color,
				"default_incoming,=,Yes|default_outgoing,=,Yes",
			];
		} else if (doc.default_incoming) {
			color = doc.enable_incoming ? "blue" : "gray";
			return [__("Default Inbox"), color, "default_incoming,=,Yes"];
		} else if (doc.default_outgoing) {
			color = doc.enable_outgoing ? "blue" : "gray";
			return [__("Default Sending"), color, "default_outgoing,=,Yes"];
		} else {
			color = doc.enable_incoming ? "blue" : "gray";
			return [__("Inbox"), color, "default_outgoing,=,No|default_incoming=No"];
		}
	},
};

// providers the Frappe Cloud broker signs in with
const EMAIL_OAUTH_PROVIDERS = ["Microsoft"];

function add_email_account_dialog() {
	// Microsoft sign-in replaces the password-based Outlook.com service
	const services = frappe.meta
		.get_docfield("Email Account", "service")
		.options.split("\n")
		.filter((s) => s && s !== "Outlook.com");

	const d = new frappe.ui.Dialog({
		title: __("Add Email Account"),
		fields: [
			{
				fieldname: "provider",
				fieldtype: "Select",
				label: __("Email provider"),
				options: [
					...EMAIL_OAUTH_PROVIDERS,
					...services,
					{ label: __("Other (IMAP/SMTP)"), value: "Other" },
				],
				default: EMAIL_OAUTH_PROVIDERS[0],
				reqd: 1,
			},
		],
		primary_action_label: __("Proceed"),
		primary_action: ({ provider }) => {
			if (EMAIL_OAUTH_PROVIDERS.includes(provider)) {
				frappe
					.call({
						method: "frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect",
						args: { provider: provider.toLowerCase() },
						freeze: true,
					})
					.then((r) => (window.location.href = r.message));
				return;
			}
			d.hide();
			frappe.new_doc("Email Account", provider === "Other" ? {} : { service: provider });
		},
	});
	d.show();
}

function show_email_oauth_result(code, mailbox) {
	if (code === "connected" || code === "reconnected") {
		const named = mailbox?.length <= 254 && frappe.utils.validate_type(mailbox, "email");
		const name = named && frappe.utils.escape_html(mailbox);
		frappe.show_alert({
			message:
				code === "connected"
					? named
						? __("Connected {0}", [name])
						: __("Mailbox connected")
					: named
					? __("Reconnected {0}", [name])
					: __("Mailbox reconnected"),
			indicator: "green",
		});
		return;
	}
	const messages = {
		cancelled: __("Sign-in was cancelled."),
		admin_approval: __("Your Microsoft 365 admin must approve Frappe first."),
		expired: __("Sign-in took too long. Please try again."),
		smtp_disabled:
			__(
				"SMTP AUTH is turned off for this mailbox. Ask your Microsoft 365 admin to turn on Authenticated SMTP for it."
			) +
			` <a href="https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission#enable-smtp-auth-for-specific-mailboxes" target="_blank">${__(
				"How to turn it on"
			)}</a>`,
		smtp_disabled_personal: __(
			"Microsoft doesn't let this Outlook.com mailbox send email from other apps. Please use a Microsoft 365 work mailbox."
		),
		imap_disabled: __(
			"IMAP is turned off for this mailbox. Turn it on in Outlook settings or ask your admin."
		),
		already_connected: __("This mailbox is already connected."),
		wrong_mailbox: __(
			"You signed in to a different mailbox. Sign in to this account's mailbox."
		),
		not_team_member: __(
			"Only members of this site's Frappe Cloud team can connect a mailbox. Log in to Frappe Cloud in this browser, then try again."
		),
	};
	frappe.msgprint({
		title: __("Connect mailbox"),
		message: messages[code] || __("Couldn't connect. Please try again."),
		indicator: "red",
	});
}

frappe.help.youtube_id["Email Account"] = "YFYe0DrB95o";
