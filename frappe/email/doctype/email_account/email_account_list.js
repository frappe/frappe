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
			const provider = frappe.route_options.email_oauth_provider;
			delete frappe.route_options.email_oauth;
			delete frappe.route_options.email_oauth_mailbox;
			delete frappe.route_options.email_oauth_provider;
			show_email_oauth_result(code, mailbox, provider);
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

function add_email_account_dialog() {
	const tiles = {
		GMail: ["Gmail", "gmail.png"],
		"Outlook.com": ["Outlook", "outlook.png"],
		"Frappe Mail": ["Frappe Mail", "frappe-mail.svg"],
		"Yahoo Mail": ["Yahoo", "yahoo.png"],
		"Yandex.Mail": ["Yandex", "yandex.png"],
		Sendgrid: ["SendGrid", "sendgrid.png"],
		SparkPost: ["SparkPost", "sparkpost.webp"],
	};
	const order = Object.keys(tiles);
	const rank = (service) => (order.includes(service) ? order.indexOf(service) : order.length);
	const services = frappe.meta
		.get_docfield("Email Account", "service")
		.options.split("\n")
		.filter(Boolean)
		.sort((a, b) => rank(a) - rank(b));
	const one_click = frappe.boot.one_click_email_services || {};

	const open_form = (service) => {
		d.hide();
		frappe.new_doc("Email Account", service === "Other" ? {} : { service });
	};
	const sign_in = (service, label) => {
		const $others = d.get_secondary_btn().add(d.$wrapper.find(".email-provider-tiles button"));
		$others.prop("disabled", true);
		return frappe
			.xcall("frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect", {
				service,
			})
			.then((url) => {
				if (url) {
					window.location.href = url;
					return new Promise(() => {}); // Continue stays busy until the sign-in page opens
				}
				d.set_message(
					__(
						"{0} sign-in isn't available right now. You can still set it up manually.",
						[label]
					)
				);
				d.get_secondary_btn().addClass("hide");
				d.set_primary_action(__("Set up manually"), () => open_form(service));
			})
			.finally(() => $others.prop("disabled", false));
	};
	const set_actions = (service, label) => {
		if (!one_click[service]) {
			d.get_secondary_btn().addClass("hide");
			d.set_primary_action(__("Continue"), () => open_form(service));
			return;
		}
		const primary_btn = d.set_primary_action(__("Continue"), () => sign_in(service, label));
		frappe.ui.button.dress(primary_btn, {
			label: __("Continue"),
			variant: "solid",
			icon_right: "arrow-up-right",
		});
		d.set_secondary_action_label(__("Set up manually"));
		d.set_secondary_action(() => open_form(service));
	};
	const tile = (service, label, logo) => {
		const $tile = $(
			frappe.ui.button.html({
				label,
				variant: "outline",
				icon: logo ? undefined : "mail",
				attrs: { "aria-pressed": "false" },
			})
		);
		if (logo) {
			$tile
				.find(".es-button__label")
				.before(
					$("<img alt=''>").attr("src", `/assets/frappe/images/email-providers/${logo}`)
				);
		}
		return $tile.on("click", () => {
			$tile.siblings().attr("aria-pressed", "false");
			$tile.attr("aria-pressed", "true");
			set_actions(service, label);
			d.enable_primary_action();
		});
	};

	const d = new frappe.ui.Dialog({
		title: __("Add Email Account"),
		fields: [{ fieldtype: "HTML", fieldname: "providers" }],
	});
	const label_id = frappe.utils.get_random(8);
	d.fields_dict.providers.$wrapper.append(
		$("<div class='control-label'>")
			.attr("id", label_id)
			.text(__("Choose your email provider")),
		$("<div class='email-provider-tiles' role='group'>")
			.attr("aria-labelledby", label_id)
			.append(
				services.map((service) => tile(service, ...(tiles[service] || [service]))),
				tile("Other", __("Custom email"))
			)
	);
	d.set_primary_action(__("Continue"));
	d.disable_primary_action();
	d.show();
}

function show_email_oauth_result(code, mailbox, provider) {
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
	const provider_error_messages = {
		microsoft: {
			admin_approval: __("Your Microsoft 365 admin must approve Frappe first."),
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
		},
	};
	const error_messages = {
		cancelled: __("Sign-in was cancelled."),
		admin_approval: __("Your admin must approve Frappe first."),
		expired: __("Sign-in took too long. Please try again."),
		smtp_disabled: __("SMTP is turned off for this mailbox. Ask your admin to turn it on."),
		smtp_disabled_personal: __(
			"This mailbox can't send email from other apps. Please use a work mailbox."
		),
		imap_disabled: __(
			"IMAP is turned off for this mailbox. Turn it on in your mail settings or ask your admin."
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
		message:
			provider_error_messages[provider]?.[code] ||
			error_messages[code] ||
			__("Couldn't connect. Please try again."),
		indicator: "red",
	});
}

frappe.help.youtube_id["Email Account"] = "YFYe0DrB95o";
