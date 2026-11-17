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
	let one_click = {};
	let loaded = false;
	let picked;
	let gmail_company;

	const open_form = (service, email_id) => {
		d.hide();
		frappe.new_doc(
			"Email Account",
			service === "Other" ? {} : { service, ...(email_id && { email_id }) }
		);
	};
	const sign_in = (service, label, email) => {
		const $others = d
			.get_secondary_btn()
			.add(
				d.$wrapper.find(
					".email-provider-tiles button, .modal-footer .custom-actions button"
				)
			);
		$others.prop("disabled", true);
		return frappe
			.xcall("frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect", {
				service,
				...(email && { email }),
			})
			.then((url) => {
				if (url) {
					sessionStorage.setItem(SIGN_IN_STARTED, "1");
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
				d.set_primary_action(__("Set up manually"), () => open_form(service, email));
			})
			.finally(() => $others.prop("disabled", false));
	};
	const set_actions = (service, label) => {
		if (service === "GMail" && one_click.GMail) {
			d.get_secondary_btn().addClass("hide");
			d.set_primary_action(__("Continue"), () => show_gmail_step());
			return;
		}
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
			picked = [service, label];
			set_actions(service, label);
			if (loaded) d.enable_primary_action();
		});
	};

	const show_gmail_step = (email = "", wrong_mailbox = false) => {
		d.set_title(__("Connect Gmail"));
		d.set_df_property("providers", "hidden", 1);
		d.set_df_property("gmail_address", "hidden", 0);
		d.custom_actions.children().removeClass("hide");
		d.$wrapper
			.find(".gmail-wrong-mailbox")
			.toggleClass("hide", !wrong_mailbox)
			.find("span")
			.text(
				__(
					"You signed in with another Google account. Sign in with {0}, or set up manually.",
					[email]
				)
			);
		gmail_company = undefined;
		d.set_value("gmail_address", email).then(() => {
			update_gmail_step();
			d.fields_dict.gmail_address.$input.trigger("focus");
		});
	};
	const show_tiles = () => {
		d.clear_message();
		d.set_title(__("Add Email Account"));
		d.set_df_property("providers", "hidden", 0);
		d.set_df_property("gmail_address", "hidden", 1);
		d.set_df_property("gmail_steps", "hidden", 1);
		d.custom_actions.children().addClass("hide");
		d.$wrapper.find(".gmail-wrong-mailbox").addClass("hide");
		set_actions(...picked);
		d.enable_primary_action();
	};
	const gmail_address = () => (d.fields_dict.gmail_address.$input.val() || "").trim();
	const gmail_kind = (email) => {
		if (!frappe.utils.validate_type(email, "email")) return null;
		return /@(gmail|googlemail)\.com$/i.test(email) ? "personal" : "company";
	};
	const continue_gmail = () => {
		const email = gmail_address();
		const kind = gmail_kind(email);
		if (kind === "personal") return open_form("GMail", email);
		if (kind === "company") return sign_in("GMail", "Google", email);
	};
	const mark_gmail_invalid = (invalid) => {
		const field = d.fields_dict.gmail_address;
		field.df.invalid = invalid;
		field.set_invalid();
	};
	const toggle_gmail_continue = () => {
		const valid = Boolean(gmail_kind(gmail_address()));
		valid ? d.enable_primary_action() : d.disable_primary_action();
		if (valid) mark_gmail_invalid(false);
	};
	const update_gmail_step = () => {
		const email = gmail_address();
		mark_gmail_invalid(Boolean(email) && !gmail_kind(email));
		const company = gmail_kind(email) === "company";
		d.set_df_property("gmail_steps", "hidden", company ? 0 : 1);
		if (company) {
			d.fields_dict.gmail_steps.$wrapper.html(gmail_admin_steps(one_click.GMail.client_id));
		}
		// rebuilding the buttons mid-click (blur fires on mousedown) would swallow that click
		if (company !== gmail_company) {
			gmail_company = company;
			const primary_btn = d.set_primary_action(__("Continue"), continue_gmail);
			if (company) {
				frappe.ui.button.dress(primary_btn, {
					label: __("Continue"),
					variant: "solid",
					icon_right: "arrow-up-right",
				});
				d.set_secondary_action_label(__("Set up manually"));
				d.set_secondary_action(() => open_form("GMail", gmail_address()));
			} else {
				d.get_secondary_btn().addClass("hide");
			}
		}
		toggle_gmail_continue();
	};

	const d = new frappe.ui.Dialog({
		title: __("Add Email Account"),
		fields: [
			{ fieldtype: "HTML", fieldname: "providers" },
			{
				fieldtype: "Data",
				fieldname: "gmail_address",
				label: __("Email Address"),
				description: __("The Gmail or Google Workspace email ID you're connecting."),
				hidden: 1,
			},
			{ fieldtype: "HTML", fieldname: "gmail_steps", hidden: 1 },
		],
	});
	d.add_custom_action(__("Back"), show_tiles);
	d.custom_actions.children().addClass("hide");
	d.fields_dict.gmail_address.$wrapper.before(
		$(`<div class="gmail-wrong-mailbox alert alert-danger hide"><span></span></div>`)
	);
	d.fields_dict.gmail_address.$wrapper
		.on("input", "input", toggle_gmail_continue)
		.on("change", "input", update_gmail_step);
	d.fields_dict.gmail_steps.$wrapper.on("click", "[data-copy]", (e) => {
		const copy = $(e.currentTarget).attr("data-copy");
		frappe.utils.copy_to_clipboard(
			copy === "steps"
				? gmail_admin_steps_text(one_click.GMail.client_id)
				: one_click.GMail.client_id,
			copy === "steps" ? __("Steps copied") : __("Client ID copied")
		);
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
	return frappe
		.xcall("frappe.integrations.frappe_providers.email_oauth.get_one_click_services")
		.then((services) => (one_click = services))
		.finally(() => {
			loaded = true;
			if (!picked) return;
			set_actions(...picked);
			d.enable_primary_action();
		})
		.then(() => ({
			connect_gmail(email, wrong_mailbox) {
				if (!one_click.GMail) return;
				picked = ["GMail", "Gmail"];
				show_gmail_step(email, wrong_mailbox);
			},
		}));
}

const SIGN_IN_STARTED = "email_oauth_sign_in_started";
const GOOGLE_ADMIN_CONSOLE = "https://admin.google.com/ac/owl/list?tab=configuredApps";

function gmail_admin_steps(client_id) {
	const esc = frappe.utils.escape_html;
	const steps = [
		[
			__("Open API controls in the Admin console"),
			__("Sign in as a Google Workspace admin."),
			frappe.ui.button.html({
				label: __("Open Google Admin console"),
				variant: "outline",
				icon_right: "arrow-up-right",
				href: GOOGLE_ADMIN_CONSOLE,
				attrs: { target: "_blank", rel: "noopener" },
			}),
		],
		[
			__("Add Frappe as an app"),
			__("Click Configure new app and search for this client ID."),
			client_id
				? `<div class="gmail-client-id"><code>${esc(
						client_id
				  )}</code>${frappe.ui.button.html({
						icon: "copy",
						variant: "ghost",
						title: __("Copy client ID"),
						attrs: { "data-copy": "client-id" },
				  })}</div>`
				: "",
		],
		[
			__("Choose who can connect mailboxes"),
			__("All users, or the group that has the support mailbox."),
			"",
		],
		[
			__("Set access to Trusted"),
			__("Select Trusted and click Continue, then click Finish on the review screen."),
			"",
		],
	];
	return `<div class="gmail-admin-steps">
		<div class="gmail-admin-steps__head">
			<div>
				<div class="gmail-admin-steps__title">${esc(
					__("Your Google Workspace admin must allow Frappe first")
				)}</div>
				<p class="text-muted">${esc(
					__(
						"This is a one-time step. Send these steps to your admin, or follow them if you are the admin."
					)
				)}</p>
			</div>
			${frappe.ui.button.html({
				icon: "copy",
				variant: "ghost",
				title: __("Copy steps for your admin"),
				attrs: { "data-copy": "steps" },
			})}
		</div>
		<ol>${steps
			.map(
				([title, description, extra]) =>
					`<li><div class="gmail-admin-steps__title">${esc(
						title
					)}</div><p class="text-muted">${esc(description)}</p>${extra}</li>`
			)
			.join("")}</ol>
	</div>`;
}

function gmail_admin_steps_text(client_id) {
	return [
		__("Please allow Frappe to access Gmail for our team (one-time, about 2 minutes):"),
		"1. " +
			__("Open {0} (Security > API controls > Manage Third-Party App Access)", [
				GOOGLE_ADMIN_CONSOLE,
			]),
		"2. " +
			(client_id
				? __("Click Configure new app and search for this client ID: {0}", [client_id])
				: __("Click Configure new app and search for Frappe")),
		"3. " +
			__(
				"Choose who can connect mailboxes (all users, or the group with the support mailbox)"
			),
		"4. " + __("Select Trusted and click Continue, then click Finish on the review screen"),
	].join("\n");
}

function show_email_oauth_result(code, mailbox, provider) {
	const started = sessionStorage.getItem(SIGN_IN_STARTED) === "1";
	sessionStorage.removeItem(SIGN_IN_STARTED);
	const named = mailbox?.length <= 254 && frappe.utils.validate_type(mailbox, "email");
	if (code === "connected" || code === "reconnected") {
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
		google: {
			admin_approval: __("Your Google Workspace admin hasn't allowed Frappe yet."),
			imap_disabled:
				__(
					"IMAP is turned off for this mailbox. Turn it on in Gmail settings under Forwarding and POP/IMAP, or ask your Google Workspace admin."
				) +
				` <a href="https://mail.google.com/mail/u/0/#settings/fwdandpop" target="_blank">${__(
					"Open Gmail settings"
				)}</a>`,
		},
		yandex: {
			imap_disabled:
				__(
					'IMAP is turned off for this mailbox. In Yandex Mail settings, under Email clients, turn on IMAP and "App passwords and OAuth tokens".'
				) +
				` <a href="https://mail.yandex.com/#setup/client" target="_blank">${__(
					"Open Yandex Mail settings"
				)}</a>`,
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
		missing_permission: __(
			"Frappe wasn't allowed to read and send your email. Sign in again and allow access to your mail."
		),
		already_connected: __("This mailbox is already connected."),
		wrong_mailbox: __(
			"You signed in to a different mailbox. Sign in to this account's mailbox."
		),
		not_team_member: __(
			"Only members of this site's Frappe Cloud team can connect a mailbox. Log in to Frappe Cloud in this browser, then try again."
		),
	};
	const wrong_new_mailbox = code === "wrong_mailbox" && started && named;
	const gmail_action =
		provider === "google" &&
		(code === "admin_approval" || wrong_new_mailbox) &&
		frappe.boot.is_v2_site;
	frappe.msgprint({
		title: __("Connect mailbox"),
		message: wrong_new_mailbox
			? __(
					"You signed in with another account. That isn't {0}, so it wasn't added. Sign in with {0}, or set up manually.",
					[frappe.utils.escape_html(mailbox)]
			  )
			: provider_error_messages[provider]?.[code] ||
			  error_messages[code] ||
			  __("Couldn't connect. Please try again."),
		indicator: "red",
		...(gmail_action && {
			primary_action: {
				label:
					code === "admin_approval" ? __("Show what your admin needs") : __("Try again"),
				action() {
					frappe.hide_msgprint();
					add_email_account_dialog().then((dialog) =>
						dialog.connect_gmail(named ? mailbox : "", code === "wrong_mailbox")
					);
				},
			},
		}),
	});
}

frappe.help.youtube_id["Email Account"] = "YFYe0DrB95o";
