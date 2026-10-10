import re
from urllib.parse import urljoin

import frappe
from frappe import _
from frappe.integrations.doctype.connected_app.connected_app import has_token
from frappe.utils import cint, get_url, get_url_to_form, validate_email_address

EMAIL_SERVICES = {
	"GMail": {
		"incoming": {
			"email_server": "imap.gmail.com",
			"incoming_port": 993,
			"use_ssl": 1,
			"use_imap": 1,
		},
		"pop_server": "pop.gmail.com",
		"outgoing": {"smtp_server": "smtp.gmail.com", "smtp_port": 587, "use_tls": 1},
		"oauth_provider": "Google",
	},
	"Outlook.com": {
		"incoming": {
			"email_server": "outlook.office365.com",
			"incoming_port": 993,
			"use_ssl": 1,
			"use_imap": 1,
		},
		"pop_server": "outlook.office365.com",
		"outgoing": {"smtp_server": "smtp.office365.com", "smtp_port": 587, "use_tls": 1},
		"oauth_provider": "Microsoft",
	},
	"Yahoo Mail": {
		"incoming": {
			"email_server": "imap.mail.yahoo.com",
			"incoming_port": 993,
			"use_ssl": 1,
			"use_imap": 1,
		},
		"pop_server": "pop.mail.yahoo.com",
		"outgoing": {"smtp_server": "smtp.mail.yahoo.com", "smtp_port": 587, "use_tls": 1},
	},
	"Yandex.Mail": {
		"incoming": {
			"email_server": "imap.yandex.com",
			"incoming_port": 993,
			"use_ssl": 1,
			"use_imap": 1,
		},
		"pop_server": "pop.yandex.com",
		"outgoing": {"smtp_server": "smtp.yandex.com", "smtp_port": 587, "use_tls": 1},
	},
	"Sendgrid": {
		"outgoing_only": 1,
		"outgoing": {"smtp_server": "smtp.sendgrid.net", "smtp_port": 587, "use_tls": 1},
	},
	"SparkPost": {
		"outgoing_only": 1,
		"outgoing": {"smtp_server": "smtp.sparkpostmail.com", "smtp_port": 587, "use_tls": 1},
	},
	"Frappe Mail": {},
}

OAUTH_PROVIDERS = {
	"Google": {
		"connected_app": "google-email",
		"openid_configuration": "https://accounts.google.com/.well-known/openid-configuration",
		"authorization_uri": "https://accounts.google.com/o/oauth2/v2/auth",
		"token_uri": "https://oauth2.googleapis.com/token",
		"revocation_uri": "https://oauth2.googleapis.com/revoke",
		"userinfo_uri": "https://openidconnect.googleapis.com/v1/userinfo",
		"scopes": ["https://mail.google.com/"],
		"query_parameters": {"access_type": "offline", "prompt": "consent"},
	},
	"Microsoft": {
		"connected_app": "microsoft-email",
		"openid_configuration": "https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration",
		"authorization_uri": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
		"token_uri": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
		"userinfo_uri": "https://graph.microsoft.com/oidc/userinfo",
		"scopes": [
			"offline_access",
			"https://outlook.office.com/IMAP.AccessAsUser.All",
			"https://outlook.office.com/POP.AccessAsUser.All",
			"https://outlook.office.com/SMTP.Send",
		],
		"query_parameters": {"prompt": "select_account"},
	},
}

CALLBACK_PATH = "/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/"

GOOGLE_APP_PASSWORD_URL = "https://support.google.com/accounts/answer/185833"
MICROSOFT_SMTP_AUTH_URL = "https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission"


def get_service_defaults(service: str | None, use_imap: int = 1) -> dict:
	preset = EMAIL_SERVICES.get(service or "") or {}
	values = {**preset.get("incoming", {}), **preset.get("outgoing", {})}
	if preset.get("outgoing"):
		values["enable_outgoing"] = 1
	if preset.get("outgoing_only"):
		values["enable_incoming"] = 0
	if preset.get("incoming") and not cint(use_imap):
		values["email_server"] = preset["pop_server"]
		values["incoming_port"] = 995
		values["use_imap"] = 0
	return values


def get_redirect_uri(connected_app: str) -> str:
	return urljoin(get_url(), CALLBACK_PATH + connected_app)


def get_oauth_provider(service: str | None) -> str | None:
	return (EMAIL_SERVICES.get(service or "") or {}).get("oauth_provider")


def get_provider_app(provider: str) -> str | None:
	name = OAUTH_PROVIDERS[provider]["connected_app"]
	if frappe.db.exists("Connected App", name) and frappe.db.get_value("Connected App", name, "client_id"):
		return name


@frappe.whitelist()
def get_service_settings(service: str | None = None, use_imap: int = 1) -> dict:
	frappe.has_permission("Email Account", "write", throw=True)
	provider = get_oauth_provider(service)
	return {
		"values": get_service_defaults(service, use_imap),
		"connected_app": provider and get_provider_app(provider),
		"provider_apps": [preset["connected_app"] for preset in OAUTH_PROVIDERS.values()],
	}


@frappe.whitelist()
def get_email_setup() -> dict:
	frappe.only_for("System Manager")

	accounts = frappe.get_all(
		"Email Account",
		fields=[
			"name",
			"email_id",
			"service",
			"auth_method",
			"connected_app",
			"connected_user",
			"backend_app_flow",
			"enable_incoming",
			"enable_outgoing",
			"default_incoming",
			"default_outgoing",
			"awaiting_password",
		],
		order_by="default_outgoing desc, default_incoming desc, creation asc",
	)
	for account in accounts:
		account.status = get_account_status(account)

	providers = {}
	for provider, preset in OAUTH_PROVIDERS.items():
		name = preset["connected_app"]
		app = (
			frappe.db.get_value("Connected App", name, ["client_id", "authorization_uri"], as_dict=True)
			or frappe._dict()
		)
		tenant = None
		if provider == "Microsoft" and app.authorization_uri:
			tenant = app.authorization_uri.split("login.microsoftonline.com/")[-1].split("/")[0]
		providers[provider] = {
			"connected_app": name,
			"configured": bool(app.client_id),
			"client_id": app.client_id,
			"tenant": tenant or "common",
			"redirect_uri": get_redirect_uri(name),
		}

	return {"accounts": accounts, "providers": providers}


def get_account_status(account) -> str:
	if not account.enable_incoming and not account.enable_outgoing:
		return "Disabled"
	if account.auth_method == "OAuth" and not account.backend_app_flow:
		if not account.connected_app or not has_token(account.connected_app, account.connected_user):
			return "Not Connected"
	if account.auth_method == "Basic" and account.awaiting_password:
		return "Password Needed"


@frappe.whitelist()
def save_oauth_app(
	provider: str, client_id: str, client_secret: str | None = None, tenant: str | None = None
):
	frappe.only_for("System Manager")
	if provider not in OAUTH_PROVIDERS:
		frappe.throw(_("Unknown provider {0}").format(provider))

	client_id = (client_id or "").strip()
	if not client_id:
		frappe.throw(_("Client ID is required"))

	preset = OAUTH_PROVIDERS[provider]
	tenant = (tenant or "").strip() or "common"
	if not re.fullmatch(r"[A-Za-z0-9.\-]+", tenant):
		frappe.throw(_("Tenant must be a tenant ID, a domain such as example.com, or common"))

	name = preset["connected_app"]
	is_new = not frappe.db.exists("Connected App", name)
	app = frappe.new_doc("Connected App") if is_new else frappe.get_doc("Connected App", name)

	if is_new and not client_secret:
		frappe.throw(_("Client Secret is required"))

	app.provider_name = provider
	app.client_id = client_id
	if client_secret:
		app.client_secret = client_secret.strip()
	for field in ("openid_configuration", "authorization_uri", "token_uri", "revocation_uri", "userinfo_uri"):
		app.set(field, (preset.get(field) or "").format(tenant=tenant) or None)

	app.set("scopes", [{"scope": scope} for scope in preset["scopes"]])
	app.set("query_parameters", [{"key": k, "value": v} for k, v in preset["query_parameters"].items()])

	if is_new:
		app.insert(set_name=name)
	else:
		app.save()

	return name


@frappe.whitelist()
def create_email_account(
	email_id: str,
	service: str | None = None,
	email_account_name: str | None = None,
	auth_method: str = "Basic",
	password: str | None = None,
	enable_incoming: int = 0,
	enable_outgoing: int = 1,
	default_incoming: int = 0,
	default_outgoing: int = 0,
	login_id: str | None = None,
	email_server: str | None = None,
	incoming_port: int | None = None,
	use_imap: int = 1,
	use_ssl: int = 0,
	use_starttls: int = 0,
	smtp_server: str | None = None,
	smtp_port: int | None = None,
	use_tls: int = 0,
	use_ssl_for_outgoing: int = 0,
	no_smtp_authentication: int = 0,
	frappe_mail_site: str | None = None,
	api_key: str | None = None,
	api_secret: str | None = None,
) -> dict:
	frappe.only_for("System Manager")

	email_id = (email_id or "").strip()
	if not validate_email_address(email_id):
		frappe.throw(_("Enter a valid email address, like name@example.com"), title=_("Invalid Email"))

	service = service or None
	if service and service not in EMAIL_SERVICES:
		frappe.throw(_("Unknown email service {0}").format(service))

	if frappe.db.exists("Email Account", {"email_id": email_id}):
		frappe.throw(
			_("An email account for {0} already exists.").format(frappe.bold(email_id)),
			title=_("Already Added"),
		)

	email_account_name = (email_account_name or "").strip()
	if email_account_name and frappe.db.exists("Email Account", email_account_name):
		frappe.throw(
			_("Another account is already named {0}. Enter a different Account Name.").format(
				frappe.bold(email_account_name)
			),
			title=_("Name Already Used"),
		)
	if not cint(enable_incoming) and not cint(enable_outgoing):
		frappe.throw(_("Choose at least one of Send emails or Receive emails"))

	doc = frappe.new_doc("Email Account")
	if service and service != "Frappe Mail":
		doc.update(get_service_defaults(service, use_imap))
	doc.update(
		{
			"email_id": email_id,
			"email_account_name": email_account_name or None,
			"service": service,
			"enable_incoming": cint(enable_incoming),
			"enable_outgoing": cint(enable_outgoing),
			"default_incoming": cint(enable_incoming) and cint(default_incoming),
			"default_outgoing": cint(enable_outgoing) and cint(default_outgoing),
			"auth_method": "OAuth" if auth_method == "OAuth" else "Basic",
		}
	)

	if service == "Frappe Mail":
		doc.update({"frappe_mail_site": frappe_mail_site, "api_key": api_key, "api_secret": api_secret})
	elif not service:
		doc.update(
			{
				"email_server": email_server,
				"incoming_port": incoming_port,
				"use_imap": cint(use_imap),
				"use_ssl": cint(use_ssl),
				"use_starttls": cint(use_starttls),
				"smtp_server": smtp_server,
				"smtp_port": smtp_port,
				"use_tls": cint(use_tls),
				"use_ssl_for_outgoing": cint(use_ssl_for_outgoing),
				"no_smtp_authentication": cint(no_smtp_authentication) and not cint(enable_incoming),
			}
		)

	if login_id and login_id.strip() != email_id:
		doc.login_id_is_different = 1
		doc.login_id = login_id.strip()

	authorize_url = None
	if doc.auth_method == "OAuth":
		provider = get_oauth_provider(service)
		connected_app = provider and get_provider_app(provider)
		if not connected_app:
			frappe.throw(
				_("Set up Sign in with {0} first.").format(provider or _("OAuth")),
				title=_("Sign-in App Missing"),
			)
		if provider == "Google" and (
			other := frappe.db.get_value(
				"Email Account",
				{
					"connected_app": connected_app,
					"connected_user": frappe.session.user,
					"auth_method": "OAuth",
				},
				"email_id",
			)
		):
			frappe.throw(
				_(
					"{0} is already connected with Sign in with Google under your user. Each user can sign in to one Google mailbox, so connect {1} from another user, or choose App Password."
				).format(frappe.bold(other), frappe.bold(email_id)),
				title=_("Google Mailbox Already Connected"),
			)
		doc.connected_app = connected_app
		doc.connected_user = frappe.session.user
	elif service != "Frappe Mail" and not doc.no_smtp_authentication:
		if not password:
			frappe.throw(_("Password is required"))
		doc.password = password

	if doc.enable_incoming and doc.use_imap:
		doc.append("imap_folder", {"folder_name": "INBOX"})

	if not email_account_name:
		doc.autoname()
		if frappe.db.exists("Email Account", doc.name):
			doc.email_account_name = email_id

	doc.insert()

	if doc.auth_method == "OAuth":
		app = frappe.get_doc("Connected App", doc.connected_app)
		authorize_url = app.initiate_web_application_flow(
			user=frappe.session.user,
			success_uri=get_url_to_form("Email Account", doc.name) + "?email_setup=1",
		)

	return {"name": doc.name, "authorize_url": authorize_url}


@frappe.whitelist()
def authorize(email_account: str) -> str:
	doc = frappe.get_doc("Email Account", email_account)
	doc.check_permission("write")
	if doc.auth_method != "OAuth" or not doc.connected_app:
		frappe.throw(_("This account does not use Sign in with Google or Microsoft"))
	if doc.connected_user and doc.connected_user != frappe.session.user:
		frappe.throw(
			_("Only {0} can sign in to this account, because they connected it.").format(
				frappe.bold(doc.connected_user)
			),
			title=_("Not Allowed"),
		)
	app = frappe.get_doc("Connected App", doc.connected_app)
	return app.initiate_web_application_flow(
		user=frappe.session.user, success_uri=get_url_to_form("Email Account", doc.name) + "?email_setup=1"
	)


@frappe.whitelist()
def test_email_account(email_account: str) -> dict:
	doc = frappe.get_doc("Email Account", email_account)
	doc.check_permission("write")

	results = {}
	if doc.service == "Frappe Mail":
		results["outgoing" if doc.enable_outgoing else "incoming"] = run_check(
			doc, doc.validate_frappe_mail_settings
		)
		return results

	if doc.enable_incoming:
		results["incoming"] = run_check(doc, lambda: doc.validate_connections(outgoing=False))
	if doc.enable_outgoing:
		results["outgoing"] = run_check(doc, lambda: doc.validate_connections(incoming=False))

	if results.get("incoming", {}).get("ok"):
		doc.db_set("no_failed", 0)

	return results


@frappe.whitelist()
def send_test_email(email_account: str, recipient: str | None = None) -> dict:
	from frappe.email.email_body import get_email

	doc = frappe.get_doc("Email Account", email_account)
	doc.check_permission("write")
	if not doc.enable_outgoing:
		frappe.throw(_("Turn on Enable Outgoing to send emails from this account"))

	recipient = (recipient or "").strip() or frappe.db.get_value("User", frappe.session.user, "email")
	if not validate_email_address(recipient):
		frappe.throw(_("Enter a valid email address to send the test email to"))

	def send():
		email = get_email(
			recipients=[recipient],
			sender=doc.email_id,
			subject=_("Test email from {0}").format(frappe.local.site),
			content=_(
				"This is a test email sent from {0} to check the email account {1}. No action is needed."
			).format(get_url(), doc.email_id),
			email_account=doc,
		)
		message = email.as_string()
		if doc.service == "Frappe Mail":
			doc.get_frappe_mail_client().send_raw(doc.email_id, [recipient], message)
			return
		doc.flags.validate_smtp_connection = True
		smtp_server = doc.get_smtp_server()
		try:
			smtp_server.session.sendmail(doc.email_id, [recipient], message)
		finally:
			smtp_server.quit()

	result = run_check(doc, send)
	result["recipient"] = recipient
	return result


def run_check(doc, fn) -> dict:
	if doc.auth_method == "OAuth" and not doc.backend_app_flow and not doc.get_access_token():
		return {
			"ok": False,
			"message": _(
				"This account is not signed in, or its sign-in has expired. Click Sign In to connect it."
			),
			"action": "authorize",
		}

	message_count = len(frappe.message_log)
	try:
		fn()
		return {"ok": True}
	except Exception as e:
		error = get_friendly_error(e, doc)
		if not error.get("hint"):
			doc.log_error(_("Email Account Connection Test Failed"))
		return {"ok": False, **error}
	finally:
		del frappe.message_log[message_count:]
		doc.__dict__.pop("_smtp_server_instance", None)


def raise_friendly(e: Exception, doc, message_count: int = 0) -> None:
	error = get_friendly_error(e, doc)
	if not error.get("hint"):
		raise e
	del frappe.message_log[message_count:]
	message = error["message"]
	if error.get("help_url"):
		message += "<br><br>" + _("How to fix it: {0}").format(
			f'<a href="{error["help_url"]}" target="_blank" rel="noopener noreferrer">{error["help_url"]}</a>'
		)
	if error.get("server_message"):
		message += "<br><br>" + _("The server said: {0}").format(
			frappe.utils.escape_html(error["server_message"])
		)
	frappe.throw(
		message,
		title=error.get("title") or _("Could Not Connect"),
		exc=type(e) if isinstance(e, frappe.ValidationError) else frappe.ValidationError,
	)


def get_friendly_error(e: Exception, doc=None) -> dict:
	chain = get_error_chain(e)
	raw = chain[-1] if chain else ""
	text = " ".join(chain).lower()

	def has_code(code):
		return re.search(rf"(?<![\d.]){re.escape(code)}(?![\d])", text)

	service = getattr(doc, "service", None)
	oauth = getattr(doc, "auth_method", None) == "OAuth"
	provider = get_oauth_provider(service)

	def hint(message, help_url=None, title=None):
		return {
			"hint": True,
			"message": message,
			"help_url": help_url,
			"title": title,
			"server_message": raw if len(chain) > 1 else None,
		}

	if has_code("5.7.139") or "smtpclientauthentication is disabled" in text:
		return hint(
			_(
				"Microsoft 365 has SMTP sending turned off for this mailbox. Ask your Microsoft 365 admin to turn on Authenticated SMTP for {0}."
			).format(getattr(doc, "email_id", "")),
			MICROSOFT_SMTP_AUTH_URL,
			_("SMTP Sending Is Off"),
		)
	if has_code("5.7.9") or "application-specific password" in text:
		return hint(
			_(
				"Google does not accept your normal password here. Use Sign in with Google, or create an App Password and use it as the password."
			),
			GOOGLE_APP_PASSWORD_URL,
			_("App Password Needed"),
		)
	if has_code("5.7.14") or "log in via your web browser" in text or "loginviayourwebbrowser" in text:
		return hint(
			_(
				"Google blocked this sign-in. Open Gmail in a browser, confirm the security alert, then try again. Sign in with Google avoids this."
			),
			"https://support.google.com/mail/answer/7126229",
			_("Sign-in Blocked"),
		)
	if "aadsts65001" in text or "admin consent" in text or "admin approval" in text:
		return hint(
			_(
				"Your Microsoft 365 admin has to approve this app before you can sign in. Ask them to grant admin consent."
			),
			"https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent",
			_("Admin Approval Needed"),
		)
	if "invalid_grant" in text or "aadsts700082" in text or "aadsts50173" in text:
		return hint(
			_("The sign-in for this account has expired or was revoked. Click Sign In to connect it again."),
			title=_("Sign-in Expired"),
		)
	if "please authorize oauth" in text:
		return hint(
			_(
				"This account is not signed in, or its sign-in has expired. Sign in again with Authorize API Access on the account, or Sign In in Email Settings."
			),
			title=_("Not Signed In"),
		)
	if any(has_code(code) for code in ("5.7.8", "5.7.3", "535")) or any(
		phrase in text
		for phrase in (
			"authenticationfailed",
			"authentication failed",
			"authenticate failed",
			"login failed",
			"loginfailed",
			"invalid credentials",
			"username and password not accepted",
			"authentication unsuccessful",
			"logondenied",
			"basic authentication is disabled",
		)
	):
		if oauth:
			message = _(
				"The mail server rejected the sign-in. Check that IMAP and SMTP are turned on for this mailbox, then click Sign In to connect it again."
			)
		elif provider == "Google":
			message = _(
				"Google rejected the email and password. Google needs an App Password (or Sign in with Google) instead of your normal password."
			)
		elif provider == "Microsoft":
			message = _(
				"Microsoft rejected the email and password. Microsoft has turned off password sign-in for most mailboxes. Use Sign in with Microsoft instead."
			)
		else:
			message = _(
				"The mail server rejected the username or password. Check them, and check that IMAP or SMTP access is turned on for this mailbox."
			)
		return hint(
			message,
			GOOGLE_APP_PASSWORD_URL if provider == "Google" and not oauth else None,
			_("Password Sign-in Not Allowed")
			if provider == "Microsoft" and not oauth
			else _("Wrong Username or Password"),
		)
	if "connection unexpectedly closed" in text:
		if provider == "Microsoft" and not oauth:
			message = _(
				"Microsoft closed the connection during sign-in. Microsoft has turned off password sign-in for most mailboxes. Use Sign in with Microsoft instead."
			)
		elif provider == "Google":
			message = _(
				"Google closed the connection during sign-in. Check that {0} is a Gmail or Google Workspace address and that the App Password is correct."
			).format(getattr(doc, "email_id", ""))
		else:
			message = _(
				"The mail server closed the connection. Check the username and password, and that the security setting matches the port: STARTTLS for 587, SSL for 465."
			)
		return hint(message, title=_("Connection Closed"))
	if (
		"must issue a starttls" in text
		or ("starttls" in text and "required" in text)
		or "smtp auth extension not supported" in text
	):
		return hint(
			_(
				"The server needs a secure connection. Use STARTTLS (Use TLS) for port 587, or SSL for port 465."
			),
			title=_("Secure Connection Needed"),
		)
	if (
		"wrong version number" in text
		or "socket error: eof" in text
		or ("ssl" in text and ("handshake" in text or "record layer" in text))
	):
		return hint(
			_(
				"The security setting does not match the port. Use SSL with ports 465, 993 and 995, and STARTTLS (Use TLS) with ports 587 and 143."
			),
			title=_("Security Setting Mismatch"),
		)
	if "certificate verify failed" in text:
		return hint(
			_(
				"The server's SSL certificate could not be verified. Check the server name, or ask your provider for a valid certificate."
			),
			title=_("Certificate Problem"),
		)
	if (
		"nodename nor servname" in text
		or "name or service not known" in text
		or "getaddrinfo" in text
		or "temporary failure in name resolution" in text
	):
		return hint(
			_("Could not find the mail server. Check the server name for typos."),
			title=_("Server Not Found"),
		)
	if "timed out" in text or "connection refused" in text or "network is unreachable" in text:
		return hint(
			_(
				"Could not reach the mail server. Check the server name and port, and that your firewall allows the connection."
			),
			title=_("Server Not Reachable"),
		)
	return {
		"hint": False,
		"message": (chain[0] if chain else "") or _("Something went wrong. Check the Error Log for details."),
		"server_message": raw if len(chain) > 1 else None,
	}


def get_error_chain(e: Exception) -> list[str]:
	messages = []
	while e:
		message = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(e))).strip()
		if message:
			messages.append(message)
		e = e.__context__
	return messages
