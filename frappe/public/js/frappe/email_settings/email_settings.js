frappe.provide("frappe.email_settings");

const PROVIDERS = [
	{
		service: "GMail",
		label: "Google",
		description: __("Gmail and Google Workspace"),
		image: "/assets/frappe/icons/social/google.svg",
		oauth: "Google",
		password_label: __("App Password"),
		password_help: __(
			"A 16-letter password you create in your Google Account under Security > App passwords. Your normal Google password does not work here. App passwords need 2-Step Verification."
		),
		password_url: "https://myaccount.google.com/apppasswords",
	},
	{
		service: "Outlook.com",
		label: "Microsoft",
		description: __("Outlook, Hotmail and Microsoft 365"),
		image: "/assets/frappe/icons/social/office_365.svg",
		oauth: "Microsoft",
		password_label: __("Password"),
		password_help: __(
			"Works only if your Microsoft 365 admin allows password sign-in for this mailbox. Most mailboxes need Sign in with Microsoft instead."
		),
	},
	{
		service: "Yahoo Mail",
		label: "Yahoo Mail",
		description: __("Uses an app password"),
		icon: "mail",
		password_label: __("App Password"),
		password_help: __(
			"Create an app password in your Yahoo Account under Account Security. Your normal Yahoo password does not work here."
		),
		password_url: "https://login.yahoo.com/account/security",
	},
	{
		service: "Yandex.Mail",
		label: "Yandex Mail",
		description: __("Uses an app password"),
		icon: "mail",
		password_label: __("App Password"),
		password_help: __(
			"Create an app password in Yandex ID under Security, and turn on IMAP in Yandex Mail settings."
		),
		password_url: "https://id.yandex.com/security/app-passwords",
	},
	{
		service: "Sendgrid",
		label: "SendGrid",
		description: __("Sending only, with an API key"),
		icon: "send",
		outgoing_only: true,
		password_label: __("API Key"),
		password_help: __(
			"A SendGrid API key with the Mail Send permission. The username is filled in for you."
		),
	},
	{
		service: "SparkPost",
		label: "SparkPost",
		description: __("Sending only, with an API key"),
		icon: "send",
		outgoing_only: true,
		login_id: "SMTP_Injection",
		password_label: __("API Key"),
		password_help: __(
			"A SparkPost API key with the Send via SMTP permission. The username is filled in for you."
		),
	},
	{
		service: "Frappe Mail",
		label: "Frappe Mail",
		description: __("Connect with an API key"),
		image: "/assets/frappe/icons/social/frappe.svg",
	},
	{
		service: "",
		label: __("Other"),
		description: __("Any provider, with IMAP and SMTP settings"),
		icon: "server",
		password_label: __("Password"),
	},
];

const STATUS = {
	"Not Connected": { label: __("Not signed in"), color: "orange" },
	"Password Needed": { label: __("Password needed"), color: "orange" },
	Disabled: { label: __("Turned off"), color: "gray" },
};

const OAUTH_SETUP = {
	Google: {
		description: __(
			"Let people connect Gmail and Google Workspace accounts with Sign in with Google, without an app password. You set this up once for the whole site."
		),
		client_id_label: __("Client ID"),
		steps: [
			__("Open {0} in Google Cloud Console.", [
				link("https://console.cloud.google.com/apis/credentials", __("Credentials")),
			]),
			__(
				"Set up the OAuth consent screen. Choose Internal if everyone uses your Google Workspace. With External in Testing, users must be added as test users and have to sign in again every 7 days."
			),
			__(
				"Create an OAuth client ID of type Web application, and add the Redirect URI below under Authorized redirect URIs."
			),
			__("Copy the Client ID and Client Secret into the fields below, then click Save."),
		],
	},
	Microsoft: {
		description: __(
			"Let people connect Outlook and Microsoft 365 accounts with Sign in with Microsoft. You set this up once for the whole site."
		),
		client_id_label: __("Application (client) ID"),
		steps: [
			__("Open {0} in the Microsoft Entra admin center and click New registration.", [
				link(
					"https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade",
					__("App registrations")
				),
			]),
			__("Under Redirect URI, choose Web and paste the Redirect URI below."),
			__(
				"In API permissions, add these Microsoft Graph delegated permissions: offline_access, IMAP.AccessAsUser.All, POP.AccessAsUser.All and SMTP.Send."
			),
			__(
				"In Certificates & secrets, create a client secret. Copy the Application (client) ID and the secret Value into the fields below, then click Save."
			),
			__(
				"To send email, SMTP AUTH must be turned on for each mailbox. Your Microsoft 365 admin can do this in the admin center under Mail settings."
			),
		],
	},
};

const GENERAL_FIELDS = {
	email_footer_address: null,
	disable_standard_email_footer: __(
		"Removes the footer lines that installed apps add below every email, such as a Sent via line."
	),
	hide_footer_in_auto_email_reports: __(
		"Leaves out the footer in scheduled Auto Email Reports."
	),
	attach_view_link: __(
		"When a document is emailed with a print format, adds a link to view it online."
	),
	email_retry_limit: __(
		"How many times a failed email is sent again before it is marked as Error in the Email Queue."
	),
};

let setup_promise = null;
let start_with_add = false;

function load_setup(force) {
	if (force || !setup_promise) {
		setup_promise = frappe
			.call({ method: "frappe.email.setup.get_email_setup", type: "GET" })
			.then((r) => r.message)
			.catch((e) => {
				setup_promise = null;
				throw e;
			});
	}
	return setup_promise;
}

function disable_password_checks(panel) {
	panel.fieldgroup.fields_list
		.filter((field) => field.df.fieldtype === "Password")
		.forEach((field) => field.disable_password_checks());
}

function link(url, label) {
	return `<a href="${encodeURI(
		url
	)}" target="_blank" rel="noopener noreferrer">${frappe.utils.escape_html(label)}</a>`;
}

frappe.email_settings.open = function ({ tab, add } = {}) {
	return frappe.require("doctype_settings.bundle.js").then(() => {
		setup_promise = null;
		start_with_add = Boolean(add) && (!tab || tab === "accounts");
		const tabs = [
			{
				group: __("Email"),
				items: [
					{
						id: "accounts",
						label: __("Accounts"),
						icon: "mail",
						render: render_accounts,
						on_activate: (panel) => {
							if (panel.shown_before && panel.email_view !== "list") panel.refresh();
							panel.shown_before = true;
						},
					},
					{
						id: "general",
						label: __("General"),
						icon: "settings",
						render: render_general,
					},
				],
			},
			{
				group: __("Sign-in Apps"),
				items: ["Google", "Microsoft"].map((provider) => ({
					id: provider.toLowerCase(),
					label: provider,
					icon_html: `<img src="${
						PROVIDERS.find((p) => p.oauth === provider).image
					}" alt="" class="email-settings-tab-logo">`,
					render: (panel) => render_oauth_app(panel, provider),
				})),
			},
		];

		let dialog = frappe.email_settings._dialog;
		if (!dialog) {
			dialog = new frappe.ui.SettingsDialog({
				title: __("Email Settings"),
				tabs,
				default_tab: tab || "accounts",
			});
			frappe.email_settings._dialog = dialog;
		} else {
			dialog.reset(tabs, tab || "accounts");
		}
		dialog.show();
		return dialog;
	});
};

function render_accounts(panel) {
	panel.email_view = "list";
	if (start_with_add) {
		start_with_add = false;
		show_providers(panel);
		return;
	}
	frappe.doctype_settings.render_list(panel, {
		title: __("Email Accounts"),
		description: __("The mailboxes this site uses to send and receive email."),
		primary_action: {
			label: __("Add Account"),
			icon: "plus",
			onclick: () => show_providers(panel),
		},
		load: () =>
			load_setup(true).then((setup) =>
				panel.email_view === "list" ? setup.accounts : new Promise(() => {})
			),
		title_column: {
			primary: (row) => row.email_id,
			secondary: (row) => describe_account(row),
			onclick: (row) => open_account(panel, row.name),
		},
		columns: [{ label: __("Status"), badge: (row) => STATUS[row.status] }],
		actions: (row) =>
			[
				row.status === "Not Connected" && {
					label: __("Sign In"),
					icon: "log-in",
					onclick: () => frappe.email_settings.sign_in(row.name),
				},
				{
					label: __("Test Connection"),
					icon: "plug",
					onclick: (list) =>
						frappe.email_settings.test(row.name).then(() => list.reload()),
				},
				row.enable_outgoing && {
					label: __("Send Test Email"),
					icon: "send",
					onclick: () => frappe.email_settings.send_test_email(row.name),
				},
				{
					label: __("Edit"),
					icon: "pencil",
					onclick: () => open_account(panel, row.name),
				},
				{
					label: __("Delete"),
					icon: "trash",
					danger: true,
					onclick: (list) =>
						frappe.model.delete_doc("Email Account", row.name, () => {
							frappe.ui.toast({
								message: __("Email account deleted"),
								type: "success",
							});
							list.reload();
						}),
				},
			].filter(Boolean),
		empty_state: {
			icon: "mail",
			title: __("No email accounts yet"),
			description: __(
				"Add an account so this site can send emails like password resets and notifications."
			),
			action: { label: __("Add Account"), onclick: () => show_providers(panel) },
		},
	});
}

function describe_account(row) {
	const usage =
		row.enable_incoming && row.enable_outgoing
			? __("Sends and receives")
			: row.enable_outgoing
			? __("Sends only")
			: row.enable_incoming
			? __("Receives only")
			: __("Not used");
	const provider = PROVIDERS.find((p) => p.service === (row.service || ""));
	const parts = [usage];
	if (row.default_outgoing && row.default_incoming)
		parts.push(__("Default for sending and inbox"));
	else if (row.default_outgoing) parts.push(__("Default for sending"));
	else if (row.default_incoming) parts.push(__("Default inbox"));
	if (row.auth_method === "OAuth" && provider && provider.oauth) {
		parts.push(__("Sign in with {0}", [provider.label]));
	} else if (provider && provider.service) {
		parts.push(provider.label);
	}
	return parts.join(" · ");
}

function open_account(panel, name) {
	panel.dialog.hide();
	frappe.set_route("Form", "Email Account", name);
}

function show_providers(panel) {
	panel.email_view = "add";
	panel.set_view({
		title: __("Add Email Account"),
		description: __("Where is this mailbox hosted?"),
		actions: [{ label: __("Back"), icon: "arrow-left", click: () => panel.refresh() }],
		render: (p) => {
			const $grid = $('<div class="email-provider-grid"></div>').appendTo(p.body);
			PROVIDERS.forEach((provider) => {
				const $card = $(`
					<button type="button" class="email-provider-card">
						<span class="email-provider-logo"></span>
						<span class="email-provider-text">
							<span class="email-provider-name"></span>
							<span class="email-provider-description"></span>
						</span>
					</button>
				`).appendTo($grid);
				$card
					.find(".email-provider-logo")
					.html(
						provider.image
							? `<img src="${provider.image}" alt="">`
							: frappe.utils.icon(provider.icon, "md")
					);
				$card.find(".email-provider-name").text(provider.label);
				$card.find(".email-provider-description").text(provider.description);
				$card.on("click", () =>
					load_setup().then((setup) => show_account_form(panel, provider, setup))
				);
			});
		},
	});
}

function show_account_form(panel, provider, setup) {
	const has_default_outgoing = setup.accounts.some((a) => a.default_outgoing);
	const has_default_incoming = setup.accounts.some((a) => a.default_incoming);
	const oauth = provider.oauth && setup.providers[provider.oauth];
	const is_other = !provider.service;
	const is_frappe_mail = provider.service === "Frappe Mail";
	const uses_password = provider.oauth ? "eval:doc.auth_method==='Basic'" : null;

	const fields = [
		{
			fieldname: "email_id",
			fieldtype: "Data",
			options: "Email",
			label: __("Email Address"),
			reqd: 1,
		},
		{
			fieldname: "email_account_name",
			fieldtype: "Data",
			label: __("Account Name"),
			description: __(
				"A short name to tell accounts apart, like Support or Sales. Leave it empty to use the part before @."
			),
		},
	];

	if (provider.oauth) {
		fields.push({
			fieldname: "auth_method",
			fieldtype: "Select",
			label: __("Sign-in Method"),
			options: [
				{ value: "OAuth", label: __("Sign in with {0}", [provider.label]) },
				{ value: "Basic", label: provider.password_label },
			],
			default: oauth.configured ? "OAuth" : "Basic",
		});
		fields.push({
			fieldname: "oauth_note",
			fieldtype: "HTML",
			depends_on: "eval:doc.auth_method==='OAuth'",
			options: oauth.configured
				? `<p class="email-settings-note">${__(
						"After you click Connect, {0} opens in this tab so you can allow access. You come back here when you are done.",
						[provider.label]
				  )}</p>`
				: `<p class="email-settings-note email-settings-warning">${__(
						"Sign in with {0} is not set up on this site yet. An administrator has to set it up once in {1}. Until then, choose {2} as the sign-in method.",
						[
							provider.label,
							`<a href="#" class="email-settings-goto" data-tab="${provider.oauth.toLowerCase()}">${__(
								"Sign-in Apps > {0}",
								[provider.label]
							)}</a>`,
							provider.password_label,
						]
				  )}</p>`,
		});
	}

	if (is_frappe_mail) {
		fields.push(
			{
				fieldname: "frappe_mail_site",
				fieldtype: "Data",
				label: __("Frappe Mail Site"),
				reqd: 1,
				description: __(
					"The address of your Frappe Mail site, like https://mail.example.com"
				),
			},
			{ fieldname: "api_key", fieldtype: "Data", label: __("API Key"), reqd: 1 },
			{
				fieldname: "api_secret",
				fieldtype: "Password",
				label: __("API Secret"),
				reqd: 1,
				description: __(
					"Create an API key and secret in your Frappe Mail account settings."
				),
			}
		);
	} else {
		if (is_other) {
			fields.push({
				fieldname: "login_id",
				fieldtype: "Data",
				label: __("Username"),
				description: __("Leave empty if the username is the same as the email address."),
			});
		}
		fields.push({
			fieldname: "password",
			fieldtype: "Password",
			label: provider.password_label,
			depends_on: is_other ? "eval:!doc.no_smtp_authentication" : uses_password,
			mandatory_depends_on: uses_password || undefined,
			reqd: uses_password || is_other ? 0 : 1,
			description: [
				provider.password_help,
				provider.password_url && link(provider.password_url, __("Create one here")),
			]
				.filter(Boolean)
				.join(" "),
		});
		if (is_other) {
			fields.push({
				fieldname: "no_smtp_authentication",
				fieldtype: "Check",
				label: __("The server needs no password"),
				depends_on: "eval:!doc.enable_incoming",
				description: __(
					"Tick for a mail relay that accepts email without signing in, like a local relay. Sending only."
				),
			});
		}
	}

	fields.push(
		{ fieldtype: "Section Break", label: __("Use This Account To") },
		{
			fieldname: "enable_outgoing",
			fieldtype: "Check",
			label: __("Send emails"),
			default: 1,
			description: __("Send notifications, password resets and replies from this address."),
		},
		{
			fieldname: "default_outgoing",
			fieldtype: "Check",
			label: __("Use as the default for sending"),
			default: has_default_outgoing ? 0 : 1,
			depends_on: "enable_outgoing",
			description: __("Emails that do not pick an account are sent from this one."),
		}
	);

	if (!provider.outgoing_only) {
		fields.push(
			{ fieldtype: "Column Break" },
			{
				fieldname: "enable_incoming",
				fieldtype: "Check",
				label: __("Receive emails"),
				description: __(
					"Fetch new emails from the inbox every few minutes. They show up in the Inbox and on the documents they are about."
				),
			},
			{
				fieldname: "default_incoming",
				fieldtype: "Check",
				label: __("Use as the default inbox"),
				default: has_default_incoming ? 0 : 1,
				depends_on: "enable_incoming",
				description: __(
					"When someone replies to an email this site sent, the reply is read from this mailbox."
				),
			}
		);
	}

	if (is_other) {
		fields.push(
			{
				fieldtype: "Section Break",
				label: __("Receiving Server (IMAP or POP)"),
				depends_on: "enable_incoming",
			},
			{
				fieldname: "email_server",
				fieldtype: "Data",
				label: __("Incoming Server"),
				mandatory_depends_on: "enable_incoming",
				description: __("For example imap.example.com"),
			},
			{
				fieldname: "incoming_protocol",
				fieldtype: "Select",
				label: __("Protocol"),
				options: ["IMAP", "POP"],
				default: "IMAP",
				description: __("Use IMAP unless your provider supports only POP."),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "incoming_port",
				fieldtype: "Int",
				label: __("Port"),
				default: 993,
				description: __("993 for IMAP and 995 for POP with SSL. 143 and 110 otherwise."),
			},
			{
				fieldname: "incoming_security",
				fieldtype: "Select",
				label: __("Security"),
				options: [
					{ value: "SSL", label: __("SSL") },
					{ value: "STARTTLS", label: __("STARTTLS (IMAP only)") },
					{ value: "None", label: __("None") },
				],
				default: "SSL",
			},
			{
				fieldtype: "Section Break",
				label: __("Sending Server (SMTP)"),
				depends_on: "enable_outgoing",
			},
			{
				fieldname: "smtp_server",
				fieldtype: "Data",
				label: __("Outgoing Server"),
				mandatory_depends_on: "enable_outgoing",
				description: __("For example smtp.example.com"),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "smtp_port",
				fieldtype: "Int",
				label: __("Port"),
				default: 587,
			},
			{
				fieldname: "smtp_security",
				fieldtype: "Select",
				label: __("Security"),
				options: [
					{ value: "TLS", label: __("STARTTLS (usually port 587)") },
					{ value: "SSL", label: __("SSL (usually port 465)") },
					{ value: "None", label: __("None (usually port 25)") },
				],
				default: "TLS",
			}
		);
	}

	panel.set_view({
		title: provider.service
			? __("Add {0} Account", [provider.label])
			: __("Add Email Account"),
		description: provider.description,
		actions: [
			{ label: __("Back"), icon: "arrow-left", click: () => show_providers(panel) },
			{
				label: __("Connect"),
				variant: "solid",
				click: () => connect(panel, provider, oauth),
			},
		],
		fields,
	});

	disable_password_checks(panel);

	panel.body.find(".email-settings-goto").on("click", (e) => {
		e.preventDefault();
		panel.dialog.activate($(e.currentTarget).data("tab"));
	});

	if (is_other) {
		const fg = panel.fieldgroup;
		const set_incoming_port = () => {
			const pop = fg.get_value("incoming_protocol") === "POP";
			let security = fg.get_value("incoming_security");
			if (pop && security === "STARTTLS") {
				security = "SSL";
				fg.set_value("incoming_security", security);
			}
			const ssl = security === "SSL";
			if ([993, 143, 995, 110].includes(cint(fg.get_value("incoming_port")))) {
				fg.set_value("incoming_port", pop ? (ssl ? 995 : 110) : ssl ? 993 : 143);
			}
		};
		fg.fields_dict.incoming_protocol.$input.on("change", set_incoming_port);
		fg.fields_dict.incoming_security.$input.on("change", set_incoming_port);
		fg.fields_dict.smtp_security.$input.on("change", () => {
			const ports = { TLS: 587, SSL: 465, None: 25 };
			if (Object.values(ports).includes(cint(fg.get_value("smtp_port")))) {
				fg.set_value("smtp_port", ports[fg.get_value("smtp_security")]);
			}
		});
	}
}

function connect(panel, provider, oauth) {
	const values = panel.get_values();
	if (!values) return;

	if (!values.enable_outgoing && !values.enable_incoming) {
		frappe.msgprint({
			title: __("Choose What This Account Does"),
			message: __("Tick Send emails, Receive emails, or both."),
			indicator: "orange",
		});
		return;
	}

	const missing = [
		values.auth_method !== "OAuth" &&
			provider.service !== "Frappe Mail" &&
			!values.no_smtp_authentication &&
			!values.password &&
			panel.get_field("password").df.label,
		values.enable_outgoing &&
			!provider.service &&
			!values.smtp_server &&
			panel.get_field("smtp_server").df.label,
		values.enable_incoming &&
			!provider.service &&
			!values.email_server &&
			panel.get_field("email_server").df.label,
	].filter(Boolean);
	if (missing.length) {
		frappe.msgprint({
			title: __("Missing Values Required"),
			message: __("Fill in: {0}", [missing.map((label) => label.bold()).join(", ")]),
			indicator: "orange",
		});
		return;
	}

	if (values.auth_method === "OAuth" && !oauth.configured) {
		frappe.msgprint({
			title: __("Sign in with {0} Is Not Set Up", [provider.label]),
			message: __(
				"Set it up first in Email Settings under Sign-in Apps > {0}, or choose {1} as the sign-in method.",
				[provider.label, provider.password_label]
			),
			indicator: "orange",
		});
		return;
	}

	const args = {
		email_id: values.email_id,
		email_account_name: values.email_account_name,
		service: provider.service || null,
		auth_method: values.auth_method || "Basic",
		password: values.password,
		enable_outgoing: values.enable_outgoing ? 1 : 0,
		enable_incoming: values.enable_incoming ? 1 : 0,
		default_outgoing: values.default_outgoing ? 1 : 0,
		default_incoming: values.default_incoming ? 1 : 0,
		login_id: values.login_id || provider.login_id,
		frappe_mail_site: values.frappe_mail_site,
		api_key: values.api_key,
		api_secret: values.api_secret,
	};

	if (!provider.service) {
		Object.assign(args, {
			email_server: values.email_server,
			incoming_port: values.incoming_port,
			use_imap: values.incoming_protocol === "POP" ? 0 : 1,
			use_ssl: values.incoming_security === "SSL" ? 1 : 0,
			use_starttls: values.incoming_security === "STARTTLS" ? 1 : 0,
			no_smtp_authentication: values.no_smtp_authentication ? 1 : 0,
			smtp_server: values.smtp_server,
			smtp_port: values.smtp_port,
			use_tls: values.smtp_security === "TLS" ? 1 : 0,
			use_ssl_for_outgoing: values.smtp_security === "SSL" ? 1 : 0,
		});
	}

	frappe
		.call({
			method: "frappe.email.setup.create_email_account",
			args,
			freeze: true,
			freeze_message:
				args.auth_method === "OAuth"
					? __("Opening {0}...", [provider.label])
					: __("Checking the connection. This can take up to 30 seconds..."),
		})
		.then((r) => {
			if (r.message.authorize_url) {
				window.location.href = r.message.authorize_url;
				return;
			}
			frappe.ui.toast({
				message: __("{0} is connected", [args.email_id]),
				type: "success",
			});
			panel.refresh();
		});
}

function render_oauth_app(panel, provider) {
	const config = OAUTH_SETUP[provider];
	panel.set_view({ title: __("Sign in with {0}", [provider]), description: config.description });
	frappe.doctype_settings.render_loading(panel.body);

	load_setup().then((setup) => {
		const app = setup.providers[provider];
		const fields = [
			{
				fieldname: "steps",
				fieldtype: "HTML",
				options: `<ol class="email-settings-steps">${config.steps
					.map((step) => `<li>${step}</li>`)
					.join("")}</ol>`,
			},
			{
				fieldname: "redirect_uri_html",
				fieldtype: "HTML",
				options: `
					<div class="form-group">
						<div class="clearfix"><label class="control-label">${__("Redirect URI")}</label></div>
						<div class="email-settings-copy">
							<code class="email-settings-copy-value"></code>
						</div>
						<p class="help-box small text-muted">${__(
							"The address {0} sends people back to after they sign in. It must match exactly.",
							[provider]
						)}</p>
					</div>`,
			},
			{
				fieldname: "client_id",
				fieldtype: "Data",
				label: config.client_id_label,
				reqd: 1,
				default: app.client_id,
			},
			{
				fieldname: "client_secret",
				fieldtype: "Password",
				label: __("Client Secret"),
				reqd: app.configured ? 0 : 1,
				description: app.configured
					? __("A secret is already saved. Leave this empty to keep it.")
					: "",
			},
		];

		if (provider === "Microsoft") {
			fields.push({
				fieldname: "tenant",
				fieldtype: "Data",
				label: __("Tenant"),
				default: app.tenant,
				description: __(
					"Use common to allow any Microsoft account. To allow only your organization, enter your Directory (tenant) ID or your domain, like example.com."
				),
			});
		}

		panel.set_view({
			title: __("Sign in with {0}", [provider]),
			description: config.description,
			actions: [
				{
					label: __("Save"),
					variant: "solid",
					click: () => save_oauth_app(panel, provider),
				},
			],
			fields,
		});

		disable_password_checks(panel);

		const $copy = panel.body.find(".email-settings-copy");
		$copy.find(".email-settings-copy-value").text(app.redirect_uri);
		frappe.ui
			.button({
				label: __("Copy"),
				icon: "copy",
				size: "xs",
				onclick: () => frappe.utils.copy_to_clipboard(app.redirect_uri),
			})
			.appendTo($copy);

		frappe.ui
			.badge(
				app.configured
					? { label: __("Set up"), theme: "green" }
					: { label: __("Not set up"), theme: "gray" }
			)
			.appendTo(panel.$header.find(".settings-dialog-panel-title"));
	});
}

function save_oauth_app(panel, provider) {
	const values = panel.get_values();
	if (!values) return;
	frappe
		.call({
			method: "frappe.email.setup.save_oauth_app",
			args: { provider, ...values },
			freeze: true,
		})
		.then(() => {
			frappe.ui.toast({
				message: __("Sign in with {0} is set up", [provider]),
				type: "success",
			});
			load_setup(true).then(() => panel.refresh());
		});
}

function render_general(panel) {
	panel.set_view({
		title: __("General"),
		description: __("Settings that apply to every email this site sends."),
	});
	frappe.doctype_settings.render_loading(panel.body);

	frappe.model.with_doctype("System Settings", () => {
		frappe.db.get_doc("System Settings").then((doc) => {
			const fields = Object.entries(GENERAL_FIELDS).map(([fieldname, description]) => {
				const df = frappe.meta.get_docfield("System Settings", fieldname);
				return {
					fieldname,
					fieldtype: df.fieldtype,
					label: __(df.label),
					options: df.options,
					description: description || (df.description && __(df.description)),
					default: doc[fieldname],
				};
			});
			panel.set_view({
				title: __("General"),
				description: __("Settings that apply to every email this site sends."),
				actions: [
					{
						label: __("Save"),
						variant: "solid",
						click: () => {
							const values = panel.get_values();
							if (!values) return;
							frappe
								.call({
									method: "frappe.client.set_value",
									args: {
										doctype: "System Settings",
										name: "System Settings",
										fieldname: values,
									},
									freeze: true,
								})
								.then(() =>
									frappe.ui.toast({ message: __("Saved"), type: "success" })
								);
						},
					},
				],
				fields,
			});
		});
	});
}

frappe.email_settings.sign_in = function (email_account) {
	return frappe
		.call({
			method: "frappe.email.setup.authorize",
			args: { email_account },
			freeze: true,
		})
		.then((r) => {
			window.location.href = r.message;
		});
};

frappe.email_settings.test = function (email_account) {
	return frappe
		.call({
			method: "frappe.email.setup.test_email_account",
			args: { email_account },
			freeze: true,
			freeze_message: __("Testing the connection. This can take up to 30 seconds..."),
		})
		.then((r) => show_test_results(email_account, r.message));
};

const CHECK_LABELS = {
	incoming: __("Receiving emails"),
	outgoing: __("Sending emails"),
};

function show_test_results(email_account, results) {
	const entries = Object.entries(results || {});
	if (!entries.length) {
		frappe.msgprint({
			title: __("Nothing to Test"),
			message: __("Turn on Enable Incoming or Enable Outgoing for this account first."),
			indicator: "orange",
		});
		return;
	}

	const all_ok = entries.every(([, r]) => r.ok);
	const needs_sign_in = entries.some(([, r]) => r.action === "authorize");
	const rows = needs_sign_in
		? [result_row(__("Sign-in"), entries.find(([, r]) => r.action)[1])]
		: entries.map(([key, r]) => result_row(CHECK_LABELS[key], r));

	const dialog = new frappe.ui.Dialog({
		title: all_ok ? __("Connection Works") : __("Connection Problem"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<div class="email-test-results">${rows.join("")}</div>`,
			},
		],
		primary_action_label: needs_sign_in ? __("Sign In") : __("Done"),
		primary_action: () => {
			dialog.hide();
			needs_sign_in && frappe.email_settings.sign_in(email_account);
		},
	});
	dialog.show();
}

function result_row(label, result) {
	const icon = `<span class="email-test-icon ${
		result.ok ? "email-test-ok" : "email-test-failed"
	}">${
		result.ok
			? frappe.utils.icon("circle-check", "md")
			: frappe.utils.icon("circle-alert", "md")
	}</span>`;
	const message = result.ok
		? __("Connected successfully.")
		: frappe.utils.escape_html(result.message || "");
	const help = result.help_url
		? `<div class="email-test-help">${link(result.help_url, __("How to fix this"))}</div>`
		: "";
	const server =
		result.server_message && result.server_message !== result.message
			? `<div class="email-test-server">${__("The server said: {0}", [
					frappe.utils.escape_html(result.server_message),
			  ])}</div>`
			: "";
	return `
		<div class="email-test-row">
			${icon}
			<div class="email-test-body">
				<div class="email-test-label">${frappe.utils.escape_html(label)}</div>
				<div class="email-test-message">${message}</div>
				${help}${server}
			</div>
		</div>`;
}

frappe.email_settings.send_test_email = function (email_account) {
	const dialog = new frappe.ui.Dialog({
		title: __("Send Test Email"),
		fields: [
			{
				fieldname: "recipient",
				fieldtype: "Data",
				options: "Email",
				label: __("Send To"),
				reqd: 1,
				default: frappe.session.user_email,
				description: __(
					"A short test email is sent right away. If it does not arrive in a minute, check the spam folder."
				),
			},
		],
		primary_action_label: __("Send"),
		primary_action: ({ recipient }) => {
			frappe
				.call({
					method: "frappe.email.setup.send_test_email",
					args: { email_account, recipient },
					freeze: true,
					freeze_message: __("Sending..."),
				})
				.then((r) => {
					dialog.hide();
					if (r.message.ok) {
						frappe.msgprint({
							title: __("Test Email Sent"),
							message: __(
								"The test email was sent to {0}. If it does not arrive in a minute, check the spam folder.",
								[frappe.utils.escape_html(r.message.recipient).bold()]
							),
							indicator: "green",
						});
					} else {
						show_test_results(email_account, { outgoing: r.message });
					}
				});
		},
	});
	dialog.show();
};
