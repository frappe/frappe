import base64
import hashlib
import secrets
from urllib.parse import urlencode

import jwt
import requests

import frappe
from frappe import _
from frappe.integrations.frappe_providers.frappecloud_billing import get_base_url, get_site_name, post
from frappe.utils import get_url
from frappe.www.login import sanitize_redirect

START_METHOD = "press.api.email_oauth.start"
RELAY_METHOD = "press.api.email_oauth.relay_token"
CALLBACK_PATH = "/api/method/frappe.integrations.frappe_providers.email_oauth.callback"
AUTHORIZATION_URI = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
PERSONAL_TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"
SCOPES = [
	"offline_access",
	"https://outlook.office.com/IMAP.AccessAsUser.All",
	"https://outlook.office.com/SMTP.Send",
	"openid",
	"email",
	"profile",
]
NOTE_TTL = 600
DEFAULT_REDIRECT = "/desk/email-account"


def is_available() -> bool:
	return bool(frappe.conf.get("fc_communication_secret"))


def get_relay_url() -> str:
	return f"{get_base_url()}/api/method/{RELAY_METHOD}"


def is_broker_app(connected_app: str | None) -> bool:
	return bool(
		connected_app and frappe.db.get_value("Connected App", connected_app, "token_uri") == get_relay_url()
	)


def get_note_key(state: str) -> str:
	return f"email_oauth_pkce:{state}"


@frappe.whitelist(methods=["POST"])
def initiate_mailbox_connect(redirect_to: str = DEFAULT_REDIRECT, target_doctype: str | None = None) -> str:
	frappe.has_permission("Email Account", "create", throw=True)
	if not is_available():
		frappe.throw(
			_("Sign in with Microsoft through Frappe Cloud is available only on Frappe Cloud sites.")
		)

	verifier = secrets.token_urlsafe(64)
	challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
	state = secrets.token_urlsafe(32)

	try:
		response = post(
			START_METHOD,
			{"state": state, "code_challenge": challenge, "return_url": get_url(CALLBACK_PATH)},
		)
		response.raise_for_status()
		data = response.json()["message"]
	except Exception:
		frappe.log_error(_("Sign in with Microsoft could not start"))
		frappe.throw(
			_("Sign in with Microsoft is not available right now. Try again in a few minutes."),
			title=_("Could Not Start Sign-in"),
		)

	frappe.cache.set_value(
		get_note_key(state),
		{
			"user": frappe.session.user,
			"verifier": verifier,
			"client_id": data["client_id"],
			"redirect_to": redirect_to,
			"target_doctype": target_doctype,
		},
		expires_in_sec=NOTE_TTL,
	)
	return data["authorize_url"]


@frappe.whitelist(methods=["GET"], allow_guest=True)  # nosemgrep: guest-whitelisted-method
def callback(
	code: str | None = None,
	state: str | None = None,
	error: str | None = None,
	error_description: str | None = None,
):
	if frappe.session.user == "Guest":
		return redirect("/login?" + urlencode({"redirect-to": frappe.request.url}))

	key = get_note_key(state or "")
	note = frappe.cache.get_value(key)
	if not note or note.get("user") != frappe.session.user:
		return redirect(DEFAULT_REDIRECT, "expired")
	frappe.cache.delete_value(key)

	if error:
		result = get_error_result(error, error_description)
	else:
		try:
			result = connect_mailbox(note, code)
		except Exception:
			frappe.db.rollback()
			frappe.log_error(_("Sign in with Microsoft failed"))
			result = "failed"

	frappe.db.commit()
	return redirect(note.get("redirect_to") or DEFAULT_REDIRECT, result)


def redirect(path: str, result: str | None = None):
	location = sanitize_redirect(path) or DEFAULT_REDIRECT
	if result:
		location += ("&" if "?" in location else "?") + urlencode({"email_oauth": result})
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location


def get_error_result(error: str, description: str | None) -> str:
	text = f"{error} {description or ''}".lower()
	if error == "not_team_member":
		return "not_team_member"
	if "aadsts65001" in text or "consent_required" in text or "admin" in text:
		return "admin_approval"
	if error == "access_denied":
		return "cancelled"
	frappe.log_error(_("Sign in with Microsoft failed"), f"{error}: {description}")
	return "failed"


def connect_mailbox(note: dict, code: str | None) -> str:
	from frappe.email.setup import get_error_chain

	client_secret = f"{get_site_name()}:{frappe.conf.get('fc_communication_secret')}"
	response = requests.post(
		get_relay_url(),
		data={
			"grant_type": "authorization_code",
			"code": code,
			"code_verifier": note["verifier"],
			"client_id": note["client_id"],
			"client_secret": client_secret,
		},
		timeout=(5, 20),
	)
	token = response.json()
	if not response.ok or "access_token" not in token:
		return get_error_result(token.get("error") or "token_error", token.get("error_description"))

	claims = jwt.decode(token["id_token"], options={"verify_signature": False})
	email_id = (claims.get("email") or claims.get("preferred_username") or "").strip().lower()
	if not email_id:
		frappe.log_error(_("Sign in with Microsoft failed"), "No email address in the id_token")
		return "failed"

	existing = frappe.db.get_value(
		"Email Account", {"email_id": email_id}, ["name", "connected_app", "connected_user"], as_dict=True
	)
	if existing and not (
		is_broker_app(existing.connected_app) and existing.connected_user == frappe.session.user
	):
		return "already_connected"

	if existing:
		app = frappe.get_doc("Connected App", existing.connected_app)
		email_account = frappe.get_doc("Email Account", existing.name)
	else:
		app = frappe.new_doc("Connected App")
		app.provider_name = "Microsoft"
		app.client_id = note["client_id"]
		app.client_secret = client_secret
		app.authorization_uri = AUTHORIZATION_URI
		app.token_uri = get_relay_url()
		app.set("scopes", [{"scope": scope} for scope in SCOPES])
		app.insert(set_name=get_connected_app_name(email_id), ignore_permissions=True)
		email_account = None

	token_cache = app.get_token_cache(frappe.session.user)
	if not token_cache:
		token_cache = frappe.new_doc("Token Cache")
		token_cache.user = frappe.session.user
		token_cache.connected_app = app.name
	token_cache.update_data(token)

	error = None
	try:
		if not email_account:
			email_account = create_email_account(email_id, app.name, note.get("target_doctype"))
		failed, error = check_mailbox(email_account, claims.get("tid"))
	except Exception as e:
		failed, error = "failed", e

	if failed and not existing:
		frappe.db.rollback()
		frappe.delete_doc("Token Cache", token_cache.name, ignore_permissions=True, force=True)
		frappe.delete_doc("Connected App", app.name, ignore_permissions=True, force=True)
	if failed == "failed":
		frappe.log_error(_("Sign in with Microsoft failed"), "\n".join(get_error_chain(error)))
	frappe.db.commit()
	return failed or "connected"


def get_connected_app_name(email_id: str) -> str:
	name = f"microsoft-{email_id}"
	if frappe.db.exists("Connected App", name):
		name = f"{name}-{frappe.generate_hash(length=5)}"
	return name


def create_email_account(email_id: str, connected_app: str, target_doctype: str | None):
	from frappe.email.setup import get_service_defaults

	doc = frappe.new_doc("Email Account")
	doc.update(get_service_defaults("Outlook.com"))
	doc.update(
		{
			"email_id": email_id,
			"service": "Outlook.com",
			"auth_method": "OAuth",
			"connected_app": connected_app,
			"connected_user": frappe.session.user,
			"enable_incoming": 1,
			"enable_outgoing": 1,
			"append_to": target_doctype,
		}
	)
	doc.append("imap_folder", {"folder_name": "INBOX", "append_to": target_doctype})
	doc.autoname()
	if frappe.db.exists("Email Account", doc.name):
		doc.email_account_name = email_id
	doc.insert(ignore_permissions=True)
	return doc


def check_mailbox(doc, tenant: str | None) -> tuple[str | None, Exception | None]:
	from frappe.email.setup import get_error_chain

	message_count = len(frappe.message_log)
	for part in ("incoming", "outgoing"):
		try:
			doc.validate_connections(incoming=part == "incoming", outgoing=part == "outgoing")
		except Exception as e:
			text = " ".join(get_error_chain(e)).lower()
			if part == "outgoing" and ("5.7.139" in text or "smtpclientauthentication" in text):
				return "smtp_disabled_personal" if tenant == PERSONAL_TENANT else "smtp_disabled", e
			if part == "incoming" and ("authenticate failed" in text or "login failed" in text):
				return "imap_disabled", e
			return "failed", e
		finally:
			del frappe.message_log[message_count:]
			doc.__dict__.pop("_smtp_server_instance", None)
	return None, None
