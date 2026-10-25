"""Connect a mailbox in one click on Frappe Cloud.

Central (central.api.email_oauth) holds each provider's app and its secret; this site reaches it
through its own Pilot, and keeps the PKCE verifier and, after the callback, the tokens.
"""

import secrets
from typing import Literal
from urllib.parse import urlencode, urlparse

import jwt
from oauthlib.oauth2 import WebApplicationClient

import frappe
from frappe import _
from frappe.integrations.frappe_providers.cloud_settings import PilotClient, is_v2_site
from frappe.utils.data import get_host_name_from_request
from frappe.www.login import sanitize_redirect

NOTE_TTL = 10 * 60
CALLBACK_PATH = "/api/method/frappe.integrations.frappe_providers.email_oauth.callback"
# Token URI of a mailbox connected here is this + its provider key; Connected App refreshes it
# through relay_refresh
FRAPPE_CLOUD_RELAY = "frappe-cloud-relay:"
DEFAULT_LANDING = "/desk/email-account"
# ONE_CLICK_PROVIDERS' keys; a relay app's Token URI ends in one
Provider = Literal["microsoft"]
# Mail settings per provider, keyed like Central's Email OAuth Provider records; Central sends the OAuth side (scopes)
ONE_CLICK_PROVIDERS: dict[Provider, dict] = {
	"microsoft": {
		"label": "Outlook",
		"service": "Outlook.com",  # the only Microsoft option, also for work accounts
		"servers": {"email_server": "outlook.office365.com", "smtp_server": "smtp.office365.com"},
		# personal accounts (outlook.com, hotmail) share this tenant ID and use other servers
		"personal_tenant": "9188040d-6c67-4c5b-b112-36a304b66dad",
		"personal_servers": {"email_server": "imap-mail.outlook.com", "smtp_server": "smtp-mail.outlook.com"},
		# result code for each text found in an error, by where the error comes from
		"errors": {
			"sign_in": {"admin_approval": ("AADSTS65001", "AADSTS90094")},
			"save": {
				"smtp_disabled": ("SmtpClientAuthentication",),
				"imap_disabled": ("authenticated but not connected",),
			},
		},
	},
}


def get_one_click_services() -> dict[str, str]:
	"""Email Account services this site can add in one click, each with its provider's label; sent
	in the host app's boot. Frappe Cloud may still have a provider turned off, and
	initiate_mailbox_connect then returns None."""
	if not is_v2_site():
		return {}
	return {config["service"]: config["label"] for config in ONE_CLICK_PROVIDERS.values()}


@frappe.whitelist(methods=["POST"])
def initiate_mailbox_connect(
	service: str | None = None,
	redirect_to: str = DEFAULT_LANDING,
	target_doctype: str | None = None,
	email_account: str | None = None,
) -> str | None:
	"""Start a mailbox Connect; returns the provider's sign-in link, or None when adding a mailbox
	of `service` can't be done in one click here and needs the normal Email Account form.

	With `email_account`, signing in reconnects that mailbox instead of adding one, with the
	provider it was connected with; `service` is ignored."""
	if email_account:
		frappe.has_permission("Email Account", "write", doc=email_account, throw=True)
		connected_app, login_hint = frappe.db.get_value(
			"Email Account", email_account, ["connected_app", "email_id"]
		)
		token_uri = (connected_app and frappe.db.get_value("Connected App", connected_app, "token_uri")) or ""
		provider = token_uri.startswith(FRAPPE_CLOUD_RELAY) and token_uri.removeprefix(FRAPPE_CLOUD_RELAY)
		if provider not in ONE_CLICK_PROVIDERS:
			frappe.throw(_("{0} wasn't connected with one-click sign-in").format(email_account))
		if not is_v2_site():
			frappe.throw(
				_("{0} sign-in is only available on Frappe Cloud").format(
					ONE_CLICK_PROVIDERS[provider]["label"]
				)
			)
	else:
		login_hint = None
		frappe.has_permission("Email Account", "create", throw=True)
		provider = next((k for k, v in ONE_CLICK_PROVIDERS.items() if v["service"] == service), None)
		if not provider or not is_v2_site():
			return None

	client = WebApplicationClient(None)
	verifier = client.create_code_verifier(64)
	state = secrets.token_urlsafe(16)
	try:
		link = call_central_method(
			"start",
			provider=provider,
			state=state,
			code_challenge=client.create_code_challenge(verifier, "S256"),
			return_url=get_host_name_from_request() + CALLBACK_PATH,
			**({"login_hint": login_hint} if login_hint else {}),
		)
	except frappe.ValidationError as e:
		if str(e) != "provider_unavailable":  # Central's code for a provider it has turned off
			raise
		frappe.clear_last_message()
		if not email_account:
			return None
		frappe.throw(
			_("{0} sign-in isn't available right now").format(ONE_CLICK_PROVIDERS[provider]["label"])
		)
	frappe.cache.set_value(
		f"pkce_verifier:{state}",
		{
			"user": frappe.session.user,
			"verifier": verifier,
			"provider": provider,
			"client_id": link["client_id"],
			"authorization_uri": link["authorize_url"].split("?")[0],
			"scopes": link["scopes"],
			"redirect_to": redirect_to,
			"target_doctype": target_doctype,
			"email_account": email_account,
		},
		expires_in_sec=NOTE_TTL,
	)
	return link["authorize_url"]


def relay_refresh(app, token_cache) -> dict:
	"""Refresh for a Connected App whose Token URI starts with FRAPPE_CLOUD_RELAY; Central adds the secret."""
	return call_central_method(
		"relay_token",
		provider=app.token_uri.removeprefix(FRAPPE_CLOUD_RELAY),
		grant_type="refresh_token",
		refresh_token=token_cache.get_password("refresh_token"),
		scope=" ".join(app.get_scopes()),
	)


def call_central_method(method: str, **data) -> dict:
	"""Call Central's central.api.email_oauth.<method> through this site's Pilot."""
	client = PilotClient()
	return client.post(client.site_path(f"central/central.api.email_oauth.{method}"), data)


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def callback(
	state: str | None = None,
	code: str | None = None,
	error: str | None = None,
	error_description: str | None = None,
):
	"""
	The provider sends the admin back here (through Central) with a code; connect the mailbox.
	Creates Connected App and Mailbox records based on the OAuth response.
	"""

	if frappe.session.user == "Guest":
		return redirect("/login?" + urlencode({"redirect-to": frappe.request.url}))

	note = frappe.cache.get_value(f"pkce_verifier:{state}")
	if not note or note["user"] != frappe.session.user:
		return land(DEFAULT_LANDING, "expired")
	frappe.cache.delete_value(f"pkce_verifier:{state}")
	account_name = note.get("email_account")
	account_email = account_name and frappe.db.get_value("Email Account", account_name, "email_id")

	email = None
	try:
		result, email = connect_mailbox(note, code, error, error_description, account_email)
	except Exception:
		frappe.db.rollback()
		frappe.log_error("Email OAuth connect failed")
		result = "failed"
	# the provider can only send the browser back with a GET, which is rolled back unless it commits;
	# the state note above ties this request to the user's own sign-in
	frappe.db.commit()  # keeps the mailbox or the Error Log  # nosemgrep
	land(note["redirect_to"], result, account_email if account_name else email, note["provider"])


def connect_mailbox(
	note: dict,
	code: str | None,
	error: str | None,
	error_description: str | None,
	account_email: str | None,
) -> tuple[str, str | None]:
	"""Return the result code, and the address signed in to once the provider has given it."""
	if error:
		if result := matched_error(note["provider"], "sign_in", error_description):
			return result, None
		if error == "access_denied":
			return "cancelled", None
		if error == "not_team_member":  # from Central: this browser isn't logged in to the site's team
			return "not_team_member", None
		frappe.log_error("Email OAuth sign-in failed", f"{error}: {error_description}")
		return "failed", None

	provider = note["provider"]
	try:
		token = call_central_method(
			"relay_token",
			provider=provider,
			grant_type="authorization_code",
			code=code,
			code_verifier=note["verifier"],
		)
	except frappe.ValidationError as e:
		if str(e) != "invalid_grant":  # Central passes on the provider's error code as the message
			raise
		return "expired", None

	# straight from the token endpoint over TLS, so no signature check (OIDC Core 3.1.3.7)
	claims = jwt.decode(token["id_token"], options={"verify_signature": False})
	email = claims.get("email") or claims["preferred_username"]
	config = ONE_CLICK_PROVIDERS[provider]
	personal = "personal_tenant" in config and claims.get("tid") == config["personal_tenant"]
	if account_name := note.get("email_account"):
		if not account_email:
			return "failed", email
		if account_email.casefold() != email.casefold():
			return "wrong_mailbox", email
	elif frappe.db.exists("Email Account", {"email_id": email}):
		return "already_connected", email

	connected_app = create_relay_app(note, email, token)
	try:
		save_email_account(note, email, connected_app, personal)
	except Exception as e:
		frappe.db.rollback()
		delete_relay_app(connected_app)
		frappe.log_error("Email OAuth connect failed")
		result = matched_error(provider, "save", str(e)) or "failed"
		if result == "smtp_disabled" and personal:
			result = "smtp_disabled_personal"
		return result, email

	return ("reconnected" if account_name else "connected"), email


def matched_error(provider: str, source: str, message: str | None) -> str | None:
	"""Return the result code whose text, from the provider's errors for this source, is in the message."""
	for result, texts in ONE_CLICK_PROVIDERS[provider].get("errors", {}).get(source, {}).items():
		if any(t in (message or "") for t in texts):
			return result


def create_relay_app(note: dict, email: str, token: dict) -> str:
	"""Create the Connected App that refreshes through Central, with this user's tokens; commits."""
	provider = note["provider"]
	app = frappe.get_doc(
		{
			"doctype": "Connected App",
			"provider_name": f"{ONE_CLICK_PROVIDERS[provider]['label']} ({email})",
			"client_id": note["client_id"],
			"authorization_uri": note["authorization_uri"],
			"token_uri": FRAPPE_CLOUD_RELAY + provider,
			"scopes": [{"scope": scope} for scope in note["scopes"]],
		}
	).insert(ignore_permissions=True)
	frappe.get_doc(
		{"doctype": "Token Cache", "connected_app": app.name, "user": frappe.session.user}
	).update_data(token)  # commits
	return app.name


def save_email_account(note: dict, email: str, connected_app: str, personal: bool) -> None:
	"""Add the mailbox, or point the one being reconnected at `connected_app`.
	Saving logs in over IMAP and SMTP, and raises if either is refused."""
	config = ONE_CLICK_PROVIDERS[note["provider"]]
	mail_settings = {
		"auth_method": "OAuth",
		"connected_app": connected_app,
		"connected_user": frappe.session.user,
		"backend_app_flow": 0,
		"use_imap": 1,
		"use_ssl": 1,
		"incoming_port": 993,
		"use_tls": 1,
		"use_ssl_for_outgoing": 0,
		"smtp_port": 587,
		"service": config["service"],
		**(config["personal_servers"] if personal else config["servers"]),
	}
	if account_name := note.get("email_account"):
		account = frappe.get_doc("Email Account", account_name).update(mail_settings)
		if not account.imap_folder:
			account.append("imap_folder", {"folder_name": "INBOX", "append_to": account.append_to})
		account.save()
	else:
		frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_account_name": email,
				"email_id": email,
				"enable_incoming": 1,
				"enable_outgoing": 1,
				"email_sync_option": "ALL",
				"initial_sync_count": 100,
				"create_contact": 1,
				"track_email_status": 1,
				"imap_folder": [{"folder_name": "INBOX", "append_to": note["target_doctype"]}],
				**mail_settings,
			}
		).insert()


def delete_relay_app(connected_app: str | None) -> None:
	"""Delete a Connected App this module made, with its tokens, once no Email Account links it;
	a customer's own app is left alone."""
	token_uri = connected_app and frappe.db.get_value("Connected App", connected_app, "token_uri")
	if not (token_uri or "").startswith(FRAPPE_CLOUD_RELAY) or frappe.db.exists(
		"Email Account", {"connected_app": connected_app}
	):
		return
	for token_cache in frappe.get_all("Token Cache", {"connected_app": connected_app}, pluck="name"):
		frappe.delete_doc("Token Cache", token_cache, ignore_permissions=True)
	frappe.delete_doc("Connected App", connected_app, ignore_permissions=True)


def land(redirect_to: str, result: str, mailbox: str | None = None, provider: str | None = None) -> None:
	url = urlparse(sanitize_redirect(redirect_to))
	query = urlencode(
		{"email_oauth": result}
		| ({"email_oauth_mailbox": mailbox} if mailbox else {})
		| ({"email_oauth_provider": provider} if provider else {})
	)
	redirect(url._replace(query=f"{url.query}&{query}" if url.query else query).geturl())


def redirect(location: str) -> None:
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
