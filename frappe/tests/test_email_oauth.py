import base64
import hashlib
from typing import get_args
from unittest.mock import MagicMock, patch

import jwt

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.exceptions import FrappeTypeError
from frappe.integrations.doctype.connected_app.connected_app import ConnectedApp
from frappe.integrations.frappe_providers import email_oauth
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.utils.safe_exec import safe_eval

V2 = {"pilot_endpoint": "http://pilot.test", "pilot_auth_token": "pt"}
AUTHORIZE = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
SCOPES = ["offline_access", "https://outlook.office.com/IMAP.AccessAsUser.All", "email"]
LINK = {"authorize_url": f"{AUTHORIZE}?x=1", "client_id": "cid", "scopes": SCOPES}
PERSONAL = email_oauth.PROVIDERS["microsoft"]["personal_tenant"]


def pilot_path(method: str) -> str:
	return f"sites/{frappe.local.site}/central/central.api.email_oauth.{method}"


class TestInitiateMailboxConnect(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(
			patch.object(email_oauth.PilotClient, "post", return_value=LINK)
		)
		set_request(method="POST", base_url="http://hd.localhost:8000")

	def test_asks_central_through_pilot_and_keeps_verifier(self) -> None:
		self.assertEqual(
			email_oauth.initiate_mailbox_connect("microsoft", "/helpdesk", "HD Ticket"), LINK["authorize_url"]
		)

		path, data = self.pilot.call_args.args
		self.assertEqual(path, pilot_path("start"))
		self.assertEqual(data["provider"], "microsoft")
		self.assertEqual(data["return_url"], "http://hd.localhost:8000" + email_oauth.CALLBACK_PATH)

		note = frappe.cache.get_value(f"pkce_verifier:{data['state']}")
		self.assertEqual(
			{
				k: note[k]
				for k in (
					"user",
					"provider",
					"client_id",
					"authorization_uri",
					"scopes",
					"redirect_to",
					"target_doctype",
				)
			},
			{
				"user": "Administrator",
				"provider": "microsoft",
				"client_id": "cid",
				"authorization_uri": AUTHORIZE,
				"scopes": SCOPES,
				"redirect_to": "/helpdesk",
				"target_doctype": "HD Ticket",
			},
		)
		challenge = base64.urlsafe_b64encode(hashlib.sha256(note["verifier"].encode()).digest()).rstrip(b"=")
		self.assertEqual(data["code_challenge"], challenge.decode())

	def test_user_without_email_account_permission_is_refused(self) -> None:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "email-oauth-nobody@example.com",
				"first_name": "Nobody",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		).insert(ignore_if_duplicate=True)
		with self.set_user(user.name):
			self.assertRaises(frappe.PermissionError, email_oauth.initiate_mailbox_connect, "microsoft")
		self.pilot.assert_not_called()

	def test_site_off_frappe_cloud_is_refused(self) -> None:
		for key in V2:
			with self.subTest(missing=key), patch.dict(frappe.conf, {key: None}):
				self.assertRaises(frappe.ValidationError, email_oauth.initiate_mailbox_connect, "microsoft")
		self.pilot.assert_not_called()

	def test_unknown_provider_is_refused(self) -> None:
		self.assertRaises(FrappeTypeError, email_oauth.initiate_mailbox_connect, "yahoo")
		self.pilot.assert_not_called()

	def test_provider_type_lists_every_provider(self) -> None:
		self.assertEqual(set(get_args(email_oauth.Provider)), set(email_oauth.PROVIDERS))

	def test_central_refusal_keeps_no_note(self) -> None:
		self.pilot.side_effect = frappe.ValidationError("Return URL must be the email callback")
		self.assertRaises(frappe.ValidationError, email_oauth.initiate_mailbox_connect, "microsoft")
		state = self.pilot.call_args.args[1]["state"]
		self.assertIsNone(frappe.cache.get_value(f"pkce_verifier:{state}"))


def id_token(email: str, tid: str = PERSONAL) -> str:
	return jwt.encode({"email": email, "tid": tid}, "not-checked", algorithm="HS256")


def token(email: str, **claims) -> dict:
	return {
		"token_type": "Bearer",
		"access_token": "at",
		"refresh_token": "rt",
		"expires_in": 3600,
		"id_token": id_token(email, **claims),
	}


def desk_would_refuse(doc) -> list[str]:
	"""Empty fields that Desk's form requires on save (mandatory_depends_on). The server never checks these."""
	missing = []
	for df in doc.meta.fields:
		rule = df.mandatory_depends_on or ""
		if rule.startswith("eval:"):
			js = (
				rule[5:]
				.replace("===", "==")
				.replace("&&", " and ")
				.replace("||", " or ")
				.replace("!doc", " not doc")
				.strip()
			)
			needed = safe_eval(js, None, {"doc": frappe._dict(doc.as_dict())})
		else:
			needed = rule and doc.get(rule)
		if needed and not doc.get(df.fieldname):
			missing.append(df.fieldname)
	return missing


class TestCallback(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(
			patch.object(email_oauth.PilotClient, "post", return_value=token("one@email-oauth.test"))
		)
		set_request(method="GET", base_url="http://hd.localhost:8000")
		self.addCleanup(self.delete_mailboxes)

	def delete_mailboxes(self) -> None:
		frappe.set_user("Administrator")
		for account in frappe.get_all(
			"Email Account", {"email_id": ("like", "%@email-oauth.test")}, ["name", "connected_app"]
		):
			frappe.delete_doc("Email Account", account.name, force=True)
			frappe.db.delete("Token Cache", {"connected_app": account.connected_app})
			frappe.delete_doc("Connected App", account.connected_app, force=True)
		frappe.db.commit()

	def note(self, **values) -> str:
		state = frappe.generate_hash()
		frappe.cache.set_value(
			f"pkce_verifier:{state}",
			{
				"user": "Administrator",
				"verifier": "v" * 64,
				"provider": "microsoft",
				"client_id": "cid",
				"authorization_uri": AUTHORIZE,
				"scopes": SCOPES,
				"redirect_to": "/helpdesk",
				"target_doctype": None,
				**values,
			},
			expires_in_sec=60,
		)
		return state

	def landed(self) -> str:
		return frappe.local.response["location"]

	def test_connects_mailbox(self) -> None:
		state = self.note(target_doctype="ToDo")
		email_oauth.callback(state=state, code="the-code")

		self.assertEqual(self.landed(), "http://hd.localhost:8000/helpdesk?email_oauth=connected")
		self.assertIsNone(frappe.cache.get_value(f"pkce_verifier:{state}"))
		self.pilot.assert_called_once_with(
			pilot_path("relay_token"),
			{
				"provider": "microsoft",
				"grant_type": "authorization_code",
				"code": "the-code",
				"code_verifier": "v" * 64,
			},
		)

		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.test"})
		self.assertEqual(account.auth_method, "OAuth")
		self.assertEqual(account.connected_user, "Administrator")
		self.assertEqual(account.email_server, "imap-mail.outlook.com")
		self.assertEqual(account.service, "Outlook.com")
		self.assertEqual([(f.folder_name, f.append_to) for f in account.imap_folder], [("INBOX", "ToDo")])
		app = frappe.get_doc("Connected App", account.connected_app)
		self.assertEqual(app.get_scopes(), SCOPES)
		self.assertEqual(app.authorization_uri, AUTHORIZE)
		self.assertEqual(app.provider_name, "Microsoft (one@email-oauth.test)")
		self.assertEqual(app.token_uri, "frappe-cloud-relay:microsoft")
		self.assertIsNone(app.get_password("client_secret", raise_exception=False))
		self.assertEqual(app.get_token_cache("Administrator").get_password("refresh_token"), "rt")
		self.assertEqual(desk_would_refuse(app), [])
		self.assertEqual(desk_would_refuse(account), [])

	def test_second_mailbox_is_added_beside_the_first(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		self.pilot.return_value = token("two@email-oauth.test", tid="work-tenant")
		email_oauth.callback(state=self.note(), code="c2")

		first, second = (
			frappe.get_doc("Email Account", {"email_id": f"{n}@email-oauth.test"}) for n in ("one", "two")
		)
		self.assertNotEqual(first.connected_app, second.connected_app)
		self.assertEqual(second.email_server, "outlook.office365.com")
		self.assertEqual(second.smtp_server, "smtp.office365.com")
		self.assertEqual(second.service, "Outlook.com")

	def test_google_mailbox_uses_gmail_settings(self) -> None:
		# Google's ID token has no tenant, so Microsoft's personal-account servers must not apply
		self.pilot.return_value = token("three@email-oauth.test", tid=None)
		email_oauth.callback(state=self.note(provider="google"), code="c")

		self.assertEqual(self.pilot.call_args.args[1]["provider"], "google")
		account = frappe.get_doc("Email Account", {"email_id": "three@email-oauth.test"})
		self.assertEqual(
			(account.service, account.email_server, account.smtp_server),
			("GMail", "imap.gmail.com", "smtp.gmail.com"),
		)
		app = frappe.get_doc("Connected App", account.connected_app)
		self.assertEqual(app.provider_name, "Google (three@email-oauth.test)")
		self.assertEqual(app.token_uri, "frappe-cloud-relay:google")

	def test_same_mailbox_again_creates_nothing(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		apps = frappe.db.count("Connected App")
		email_oauth.callback(state=self.note(), code="c2")
		self.assertEqual(self.landed(), "http://hd.localhost:8000/helpdesk?email_oauth=already_connected")
		self.assertEqual(frappe.db.count("Connected App"), apps)

	def test_microsoft_errors_become_fixed_codes(self) -> None:
		for error, description, result in (
			("access_denied", "AADSTS65004: User declined to consent", "cancelled"),
			("access_denied", "AADSTS90094: Admin consent is required", "admin_approval"),
			(
				"consent_required",
				"AADSTS65001: The user or administrator has not consented",
				"admin_approval",
			),
			("server_error", "AADSTS50000: something broke", "failed"),
			("not_team_member", None, "not_team_member"),
		):
			with self.subTest(description):
				email_oauth.callback(state=self.note(), error=error, error_description=description)
				self.assertEqual(self.landed(), f"http://hd.localhost:8000/helpdesk?email_oauth={result}")
		self.pilot.assert_not_called()

	def test_missing_or_foreign_note_is_expired(self) -> None:
		email_oauth.callback(state="no-such-state", code="c")
		self.assertEqual(self.landed(), "http://hd.localhost:8000/desk/email-account?email_oauth=expired")

		state = self.note(user="someone-else@example.com")
		email_oauth.callback(state=state, code="c")
		self.assertTrue(self.landed().endswith("?email_oauth=expired"))
		self.assertIsNotNone(frappe.cache.get_value(f"pkce_verifier:{state}"))
		self.pilot.assert_not_called()

	def test_used_code_is_expired(self) -> None:
		self.pilot.side_effect = frappe.ValidationError("invalid_grant")
		email_oauth.callback(state=self.note(), code="old")
		self.assertTrue(self.landed().endswith("/helpdesk?email_oauth=expired"))

	def test_pilot_unreachable_is_failed(self) -> None:
		self.pilot.side_effect = frappe.ValidationError("Could not reach your server")
		email_oauth.callback(state=self.note(), code="c")
		self.assertTrue(self.landed().endswith("/helpdesk?email_oauth=failed"))

	def test_off_host_redirect_lands_on_this_host(self) -> None:
		email_oauth.callback(state=self.note(redirect_to="https://evil.example/steal"), code="c")
		self.assertEqual(self.landed(), "http://hd.localhost:8000/desk?email_oauth=connected")

	def test_failed_save_leaves_nothing_behind(self) -> None:
		apps = frappe.db.count("Connected App")
		caches = frappe.db.count("Token Cache")
		smtp_off = "535 5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled"
		personal = PERSONAL
		for message, tid, result in (
			(smtp_off, personal, "smtp_disabled_personal"),
			(smtp_off, "work-tenant", "smtp_disabled"),
			("User is authenticated but not connected.", personal, "imap_disabled"),
			("Something else", personal, "failed"),
		):
			self.pilot.return_value = token("one@email-oauth.test", tid=tid)
			with (
				self.subTest(result),
				patch.object(EmailAccount, "validate", side_effect=frappe.ValidationError(message)),
			):
				email_oauth.callback(state=self.note(), code="c")
				self.assertTrue(self.landed().endswith(f"?email_oauth={result}"))
				self.assertEqual(frappe.db.count("Connected App"), apps)
				self.assertEqual(frappe.db.count("Token Cache"), caches)

	def test_guest_is_sent_to_login(self) -> None:
		with self.set_user("Guest"):
			email_oauth.callback(state="s", code="c")
		self.assertTrue(self.landed().startswith("/login?redirect-to="))


class TestRefresh(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(
			patch.object(email_oauth.PilotClient, "post", return_value=token("one@email-oauth.test"))
		)

	def expired_app(self, token_uri: str, client_secret: str | None = None) -> ConnectedApp:
		app = frappe.get_doc(
			{
				"doctype": "Connected App",
				"provider_name": "Microsoft (one@email-oauth.test)",
				"client_id": "cid",
				"client_secret": client_secret,
				"token_uri": token_uri,
				"scopes": [{"scope": "offline_access"}, {"scope": "email"}],
			}
		).insert()
		frappe.get_doc(
			{"doctype": "Token Cache", "connected_app": app.name, "user": "Administrator"}
		).update_data({"access_token": "old", "refresh_token": "rt-old", "expires_in": -60})
		self.addCleanup(frappe.delete_doc, "Connected App", app.name, force=True)
		self.addCleanup(frappe.db.delete, "Token Cache", {"connected_app": app.name})
		return app

	def test_relay_app_refreshes_through_pilot(self) -> None:
		app = self.expired_app("frappe-cloud-relay:microsoft")
		self.assertEqual(app.get_active_token("Administrator").get_password("access_token"), "at")
		self.pilot.assert_called_once_with(
			pilot_path("relay_token"),
			{
				"provider": "microsoft",
				"grant_type": "refresh_token",
				"refresh_token": "rt-old",
				"scope": "offline_access email",
			},
		)

	def test_other_apps_never_go_through_frappe_cloud(self) -> None:
		# a customer's own app keeps its refresh token away from Central
		app = self.expired_app("https://login.example.com/token", client_secret="their-secret")
		with patch("requests_oauthlib.OAuth2Session.refresh_token", return_value=token("x@y.test")) as own:
			app.get_active_token("Administrator")
		own.assert_called_once()
		self.pilot.assert_not_called()
