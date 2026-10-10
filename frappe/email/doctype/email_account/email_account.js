const FRAPPE_MAIL_DEFAULTS = {
	domain: null,
	password: null,
	awaiting_password: 0,
	ascii_encode_password: 0,
	login_id_is_different: 0,
	login_id: null,
	use_imap: 0,
	use_ssl: 0,
	validate_ssl_certificate: 0,
	use_starttls: 0,
	email_server: null,
	incoming_port: 0,
	always_use_account_email_id_as_sender: 1,
	use_tls: 0,
	use_ssl_for_outgoing: 0,
	smtp_server: null,
	smtp_port: null,
	no_smtp_authentication: 0,
};

function get_service_settings(frm, use_imap) {
	return frappe.xcall("frappe.email.setup.get_service_settings", {
		service: frm.doc.service,
		use_imap,
	});
}

function set_oauth_app(frm, settings) {
	if (frm.doc.auth_method !== "OAuth" || frm.doc.backend_app_flow) return;
	const current = frm.doc.connected_app;
	if (
		settings.connected_app &&
		(!current ||
			(current !== settings.connected_app && settings.provider_apps.includes(current)))
	) {
		frm.set_value("connected_app", settings.connected_app);
	}
	if (!frm.doc.connected_user) frm.set_value("connected_user", frappe.session.user);
}

function with_email_settings(fn) {
	frappe.require("email_settings.bundle.js", () => fn(frappe.email_settings));
}

function oauth_access(frm) {
	frappe.model.with_doc("Connected App", frm.doc.connected_app, () => {
		const connected_app = frappe.get_doc("Connected App", frm.doc.connected_app);
		return frappe.call({
			doc: connected_app,
			method: "initiate_web_application_flow",
			args: {
				success_uri: window.location.pathname,
				user: frm.doc.connected_user,
			},
			callback: function (r) {
				window.open(r.message, "_self");
			},
		});
	});
}

function set_default_max_attachment_size(frm) {
	if (frm.doc.__islocal && !frm.doc["attachment_limit"]) {
		frappe.call({
			method: "frappe.core.api.file.get_max_file_size",
			callback: function (r) {
				if (!r.exc) {
					frm.set_value("attachment_limit", Number(r.message) / (1024 * 1024));
				}
			},
		});
	}
}
function add_helpful_links(frm) {
	if (frm.doc.service === "GMail") {
		frm.set_df_property(
			"password",
			"description",
			__(
				"Use a 16-letter App Password, not your Google password. {0}. Or set Method to OAuth to use Sign in with Google.",
				[
					"<a href='https://myaccount.google.com/apppasswords' target='_blank' rel='noopener noreferrer'>" +
						__("Create an App Password") +
						"</a>",
				]
			)
		);
	} else if (frm.doc.service === "Outlook.com") {
		frm.set_df_property(
			"password",
			"description",
			__(
				"Microsoft has turned off password sign-in for most mailboxes. Set Method to OAuth to use Sign in with Microsoft."
			)
		);
	} else {
		frm.set_df_property("password", "description", "");
	}

	if (frm.doc.service === "Frappe Mail") {
		frm.set_df_property(
			"api_secret",
			"description",
			__("To know more click {0}", [
				"<a href='https://github.com/frappe/mail' target='_blank'>" + __("here") + "</a>",
			])
		);
	} else {
		frm.set_df_property("api_secret", "description", "");
	}
}

frappe.ui.form.on("Email Account", {
	service: function (frm) {
		add_helpful_links(frm);
		if (frm.doc.service === "Frappe Mail") {
			frm.set_value(FRAPPE_MAIL_DEFAULTS);
			return;
		}
		return get_service_settings(frm, 1).then((settings) => {
			frm.set_value(settings.values);
			set_oauth_app(frm, settings);
		});
	},

	use_imap: function (frm) {
		if (!frm.doc.service || frm.doc.service === "Frappe Mail") return;
		return get_service_settings(frm, frm.doc.use_imap).then(({ values }) => {
			const { email_server, incoming_port, use_ssl } = values;
			if (email_server) frm.set_value({ email_server, incoming_port, use_ssl });
		});
	},

	auth_method: function (frm) {
		return get_service_settings(frm, frm.doc.use_imap).then((settings) =>
			set_oauth_app(frm, settings)
		);
	},

	enable_incoming: function (frm) {
		frm.trigger("warn_autoreply_on_incoming");
	},

	enable_auto_reply: function (frm) {
		frm.trigger("warn_autoreply_on_incoming");
	},

	onload: function (frm) {
		frm.set_df_property("append_to", "only_select", true);
		frm.set_query(
			"append_to",
			"frappe.email.doctype.email_account.email_account.get_append_to"
		);
		frm.set_query("append_to", "imap_folder", function () {
			return {
				query: "frappe.email.doctype.email_account.email_account.get_append_to",
			};
		});
		if (frm.doc.__islocal) {
			frm.add_child("imap_folder", { folder_name: "INBOX" });
			frm.refresh_field("imap_folder");
		}
		set_default_max_attachment_size(frm);
	},

	before_save: function (frm) {
		const old_email_id = frm.saved_email_id;
		const new_email_id = frm.doc.email_id;
		if (!old_email_id || !new_email_id || old_email_id === new_email_id) return;

		const stale_rows = (frm.doc.reply_to_addresses || []).filter(
			(row) => row.email?.toLowerCase() === old_email_id.toLowerCase()
		);
		if (!stale_rows.length) return;

		return new Promise((resolve) => {
			frappe.confirm(
				__("Reply-To Addresses still include {0}. Change it to {1} as well?", [
					frappe.utils.escape_html(old_email_id).bold(),
					frappe.utils.escape_html(new_email_id).bold(),
				]),
				() => {
					stale_rows.forEach((row) => (row.email = new_email_id));
					resolve();
				},
				resolve
			);
		});
	},

	refresh: function (frm) {
		frm.saved_email_id = frm.doc.email_id;
		add_helpful_links(frm);
		frm.events.enable_incoming(frm);
		frm.events.show_oauth_authorization_message(frm);

		if (frappe.route_flags.delete_user_from_locals && frappe.route_flags.linked_user) {
			delete frappe.route_flags.delete_user_from_locals;
			delete locals["User"][frappe.route_flags.linked_user];
		}

		if (frappe.user.has_role("System Manager")) {
			frm.page.add_menu_item(__("Email Settings"), () =>
				with_email_settings((settings) => settings.open())
			);
		}

		if (
			!frm.is_new() &&
			!frm.is_dirty() &&
			frm.perm[0]?.write &&
			(frm.doc.enable_incoming || frm.doc.enable_outgoing)
		) {
			frm.add_custom_button(__("Test Connection"), () =>
				with_email_settings((settings) => settings.test(frm.doc.name))
			);
			if (frm.doc.enable_outgoing) {
				frm.add_custom_button(__("Send Test Email"), () =>
					with_email_settings((settings) => settings.send_test_email(frm.doc.name))
				);
			}
			if (frappe.route_options?.email_setup) {
				frappe.route_options = null;
				with_email_settings((settings) => settings.test(frm.doc.name));
			}
		}

		if (!frm.is_dirty() && frm.doc.enable_incoming) {
			frm.add_custom_button(__("Pull Emails"), () => {
				frappe.dom.freeze(__("Pulling emails..."));
				frm.call({
					method: "pull_emails",
					args: { email_account: frm.doc.name },
				}).then((r) => {
					frappe.dom.unfreeze();
					if (!(r._server_messages && r._server_messages.length)) {
						frappe.show_alert({ message: __("Emails Pulled"), indicator: "green" });
					}
				});
			});
		}
	},

	authorize_api_access: function (frm) {
		oauth_access(frm);
	},

	validate_frappe_mail_settings: function (frm) {
		if (frm.doc.service == "Frappe Mail") {
			frappe.call({
				doc: frm.doc,
				method: "validate_frappe_mail_settings",
			});
		}
	},

	show_oauth_authorization_message(frm) {
		if (
			frm.doc.auth_method === "OAuth" &&
			frm.doc.connected_app &&
			!frm.doc.backend_app_flow
		) {
			frappe.call({
				method: "frappe.integrations.doctype.connected_app.connected_app.has_token",
				args: {
					connected_app: frm.doc.connected_app,
					connected_user: frm.doc.connected_user,
				},
				callback: (r) => {
					if (!r.message) {
						let msg = __(
							"This account is not signed in yet, so it cannot send or receive emails. Click Authorize API Access to sign in."
						);
						frm.dashboard.clear_headline();
						frm.dashboard.set_headline_alert(msg, "yellow");
					}
				},
			});
		}
	},

	domain: frappe.utils.debounce((frm) => {
		if (frm.doc.domain) {
			frappe.call({
				method: "get_domain_values",
				doc: frm.doc,
				args: {
					domain: frm.doc.domain,
				},
				callback: function (r) {
					if (!r.exc) {
						for (let field in r.message) {
							frm.set_value(field, r.message[field]);
						}
					}
				},
			});
		}
	}),

	email_sync_option: function (frm) {
		// confirm if the ALL sync option is selected

		if (frm.doc.email_sync_option == "ALL") {
			var msg = __(
				"You are selecting Sync Option as ALL, It will resync all read as well as unread message from server. This may also cause the duplication of Communication (emails)."
			);
			frappe.confirm(msg, null, function () {
				frm.set_value("email_sync_option", "UNSEEN");
			});
		}
	},

	warn_autoreply_on_incoming: function (frm) {
		if (frm.doc.enable_incoming && frm.doc.enable_auto_reply && frm.doc.__islocal) {
			var msg = __(
				"Enabling auto reply on an incoming email account will send automated replies to all the synchronized emails. Do you wish to continue?"
			);
			frappe.confirm(msg, null, function () {
				frm.set_value("enable_auto_reply", 0);
				frappe.show_alert({ message: __("Disabled Auto Reply"), indicator: "blue" });
			});
		}
	},
});
