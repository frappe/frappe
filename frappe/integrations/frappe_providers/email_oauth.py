"""Connect a mailbox in one click on Frappe Cloud.

Central (central.api.email_oauth) holds each provider's app and its secret; this site reaches it
through its own Pilot, and keeps the PKCE verifier and, after the callback, the tokens.
"""

import secrets
from typing import Literal
from urllib.parse import urlencode

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
# PROVIDERS' keys; frappe checks whitelisted arguments against this type
Provider = Literal["microsoft", "google"]
# Mail settings per provider, keyed like Central's PROVIDERS; Central sends the OAuth side (scopes)
PROVIDERS: dict[Provider, dict] = {
	"microsoft": {
		"label": "Microsoft",
		"service": "Outlook.com",  # the only Microsoft option, also for work accounts
		"servers": {"email_server": "outlook.office365.com", "smtp_server": "smtp.office365.com"},
		# personal accounts (outlook.com, hotmail) share this tenant ID and use other servers
		"personal_tenant": "9188040d-6c67-4c5b-b112-36a304b66dad",
		"personal_servers": {"email_server": "imap-mail.outlook.com", "smtp_server": "smtp-mail.outlook.com"},
	},
	"google": {
		"label": "Google",
		"service": "GMail",
		"servers": {"email_server": "imap.gmail.com", "smtp_server": "smtp.gmail.com"},
	},
}


@frappe.whitelist(methods=["POST"])
def initiate_mailbox_connect(
	provider: Provider, redirect_to: str = DEFAULT_LANDING, target_doctype: str | None = None
) -> str:
	"""Start a mailbox Connect; returns the provider's sign-in link."""
	frappe.has_permission("Email Account", "create", throw=True)
	if not is_v2_site():
		frappe.throw(
			_("Sign in with {0} is only available on Frappe Cloud").format(PROVIDERS[provider]["label"])
		)

	client = WebApplicationClient(None)
	verifier = client.create_code_verifier(64)
	state = secrets.token_urlsafe(16)
	link = relay(
		"start",
		provider=provider,
		state=state,
		code_challenge=client.create_code_challenge(verifier, "S256"),
		return_url=get_host_name_from_request() + CALLBACK_PATH,
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
		},
		expires_in_sec=NOTE_TTL,
	)
	return link["authorize_url"]


def relay(method: str, **data) -> dict:
	"""Call Central's central.api.email_oauth.<method> through this site's Pilot."""
	client = PilotClient()
	return client.post(client.site_path(f"central/central.api.email_oauth.{method}"), data)


def relay_refresh(app, token_cache) -> dict:
	"""Refresh for a Connected App whose Token URI starts with FRAPPE_CLOUD_RELAY; Central adds the secret."""
	return relay(
		"relay_token",
		provider=app.token_uri.removeprefix(FRAPPE_CLOUD_RELAY),
		grant_type="refresh_token",
		refresh_token=token_cache.get_password("refresh_token"),
		scope=" ".join(app.get_scopes()),
	)


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

	try:
		result = connect(note, code, error, error_description)
	except Exception:
		frappe.db.rollback()
		frappe.log_error("Email OAuth connect failed")
		result = "failed"
	frappe.db.commit()  # GET requests are rolled back otherwise; keeps the mailbox or the Error Log
	land(note["redirect_to"], result)


def connect(note: dict, code: str | None, error: str | None, error_description: str | None) -> str:
	if error:
		if any(c in (error_description or "") for c in ("AADSTS65001", "AADSTS90094")):
			return "admin_approval"
		if error == "access_denied":
			return "cancelled"
		if error == "not_team_member":  # from Central: this browser isn't logged in to the site's team
			return "not_team_member"
		frappe.log_error("Email OAuth sign-in failed", f"{error}: {error_description}")
		return "failed"

	provider = note["provider"]
	try:
		token = relay(
			"relay_token",
			provider=provider,
			grant_type="authorization_code",
			code=code,
			code_verifier=note["verifier"],
		)
	except frappe.ValidationError as e:
		if str(e) != "invalid_grant":  # Central passes on the provider's error code as the message
			raise
		return "expired"

	# straight from the token endpoint over TLS, so no signature check (OIDC Core 3.1.3.7)
	claims = jwt.decode(token["id_token"], options={"verify_signature": False})
	email = claims.get("email") or claims["preferred_username"]
	config = PROVIDERS[provider]
	personal = "personal_tenant" in config and claims.get("tid") == config["personal_tenant"]
	if frappe.db.exists("Email Account", {"email_id": email}):
		return "already_connected"

	app = frappe.get_doc(
		{
			"doctype": "Connected App",
			"provider_name": f"{config['label']} ({email})",
			"client_id": note["client_id"],
			"authorization_uri": note["authorization_uri"],
			"token_uri": FRAPPE_CLOUD_RELAY + provider,
			"scopes": [{"scope": scope} for scope in note["scopes"]],
		}
	).insert(ignore_permissions=True)
	token_cache = frappe.get_doc(
		{"doctype": "Token Cache", "connected_app": app.name, "user": frappe.session.user}
	).update_data(token)  # commits

	try:
		frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_account_name": email,
				"email_id": email,
				"auth_method": "OAuth",
				"connected_app": app.name,
				"connected_user": frappe.session.user,
				"enable_incoming": 1,
				"enable_outgoing": 1,
				"use_imap": 1,
				"use_ssl": 1,
				"incoming_port": 993,
				"use_tls": 1,
				"smtp_port": 587,
				"email_sync_option": "ALL",
				"initial_sync_count": 100,
				"create_contact": 1,
				"track_email_status": 1,
				"imap_folder": [{"folder_name": "INBOX", "append_to": note["target_doctype"]}],
				"service": config["service"],
				**(config["personal_servers"] if personal else config["servers"]),
			}
		).insert()
	except Exception as e:
		frappe.db.rollback()
		frappe.delete_doc("Token Cache", token_cache.name, ignore_permissions=True, force=True)
		frappe.delete_doc("Connected App", app.name, ignore_permissions=True, force=True)
		frappe.log_error("Email OAuth connect failed")
		message = str(e)
		if "SmtpClientAuthentication" in message:
			return "smtp_disabled_personal" if personal else "smtp_disabled"
		if "authenticated but not connected" in message:
			return "imap_disabled"
		return "failed"

	return "connected"


def land(redirect_to: str, result: str) -> None:
	url = sanitize_redirect(redirect_to)
	redirect(f"{url}{'&' if '?' in url else '?'}email_oauth={result}")


def redirect(location: str) -> None:
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
