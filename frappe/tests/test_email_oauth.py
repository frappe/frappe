import base64
import hashlib
from typing import get_args
from unittest.mock import MagicMock, patch

import jwt
from oauthlib.oauth2 import InvalidGrantError

import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.integrations.doctype.connected_app.connected_app import (
	ConnectedApp,
	delete_token_cache,
	has_token,
)
from frappe.integrations.frappe_providers import email_oauth
from frappe.permissions import add_user_permission
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import wait_for_job
from frappe.utils import set_request

V2 = {"pilot_endpoint": "http://pilot.test", "pilot_auth_token": "pt"}
AUTHORIZE = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
SCOPES = ["offline_access", "https://outlook.office.com/IMAP.AccessAsUser.All", "email"]
LINK = {"authorize_url": f"{AUTHORIZE}?x=1", "client_id": "cid", "scopes": SCOPES}
PERSONAL = email_oauth.ONE_CLICK_PROVIDERS["microsoft"]["personal_tenant"]
USER = "email-oauth-manager@example.com"


def pilot_path(method: str) -> str:
	return f"sites/{frappe.local.site}/central/central.api.email_oauth.{method}"


class TestInitiateMailboxConnect(IntegrationTestCase):
	def setUp(self) -> None:
		self.enterContext(self.set_user(create_user(USER).name))
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(
			patch.object(email_oauth.PilotClient, "post", return_value=LINK)
		)
		set_request(method="POST", base_url="http://hd.localhost:8000")

	def test_asks_central_through_pilot_and_keeps_verifier(self) -> None:
		self.assertEqual(
			email_oauth.initiate_mailbox_connect("Outlook.com", "/helpdesk", "HD Ticket"),
			LINK["authorize_url"],
		)

		path, data = self.pilot.call_args.args
		self.assertEqual(path, pilot_path("start"))
		self.assertEqual(data["provider"], "microsoft")
		self.assertEqual(data["return_url"], "http://hd.localhost:8000" + email_oauth.CALLBACK_PATH)
		self.assertNotIn("login_hint", data)

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
				"user": USER,
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
			self.assertRaises(frappe.PermissionError, email_oauth.initiate_mailbox_connect, "Outlook.com")
		self.pilot.assert_not_called()

	def test_reconnect_needs_write_on_that_mailbox(self) -> None:
		allowed = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_account_name": "_Test Email OAuth Allowed",
				"email_id": "email-oauth-allowed@example.com",
				"smtp_server": "smtp.example.com",
			}
		).insert()
		user = create_user("email-oauth-restricted@example.com")
		add_user_permission("Email Account", allowed.name, user.name)

		with self.set_user(user.name):
			self.assertTrue(frappe.has_permission("Email Account", "create"))
			self.assertRaises(
				frappe.PermissionError,
				email_oauth.initiate_mailbox_connect,
				email_account="_Test Email Account 1",
			)
		self.pilot.assert_not_called()

		self.relay_mailbox()
		email_oauth.initiate_mailbox_connect(email_account="_Test Email Account 1")
		state = self.pilot.call_args.args[1]["state"]
		self.assertEqual(
			frappe.cache.get_value(f"pkce_verifier:{state}")["email_account"], "_Test Email Account 1"
		)

	def relay_mailbox(self, token_uri: str = "frappe-cloud-relay:microsoft") -> str:
		app = frappe.get_doc(
			{"doctype": "Connected App", "provider_name": "Microsoft (relay)", "token_uri": token_uri}
		).insert()
		frappe.db.set_value("Email Account", "_Test Email Account 1", "connected_app", app.name)
		return "_Test Email Account 1"

	def test_adding_off_frappe_cloud_opens_the_form(self) -> None:
		for key in V2:
			with self.subTest(missing=key), patch.dict(frappe.conf, {key: None}):
				self.assertIsNone(email_oauth.initiate_mailbox_connect("Outlook.com"))
		self.pilot.assert_not_called()

	def test_reconnecting_off_frappe_cloud_is_refused(self) -> None:
		account = self.relay_mailbox()
		with patch.dict(frappe.conf, {"pilot_endpoint": None}):
			self.assertRaises(
				frappe.ValidationError, email_oauth.initiate_mailbox_connect, email_account=account
			)
		self.pilot.assert_not_called()

	def test_service_without_one_click_opens_the_form(self) -> None:
		for service in ("Yahoo Mail", "GMail", None):
			with self.subTest(service):
				self.assertIsNone(email_oauth.initiate_mailbox_connect(service))
		self.pilot.assert_not_called()

	def test_provider_unavailable_on_frappe_cloud_opens_the_form(self) -> None:
		self.pilot.side_effect = lambda *args: frappe.throw("provider_unavailable")  # nosemgrep
		frappe.clear_messages()
		self.assertIsNone(email_oauth.initiate_mailbox_connect("Outlook.com"))
		self.assertEqual(self.pilot.call_args.args[1]["provider"], "microsoft")
		self.assertEqual(frappe.get_message_log(), [])

	def test_reconnect_signs_in_with_the_mailboxs_provider(self) -> None:
		account = self.relay_mailbox()
		self.assertEqual(
			email_oauth.initiate_mailbox_connect("GMail", email_account=account), LINK["authorize_url"]
		)
		data = self.pilot.call_args.args[1]
		self.assertEqual(data["provider"], "microsoft")
		self.assertEqual(data["login_hint"], frappe.db.get_value("Email Account", account, "email_id"))

	def test_reconnect_with_provider_unavailable_is_refused(self) -> None:
		account = self.relay_mailbox()
		self.pilot.side_effect = lambda *args: frappe.throw("provider_unavailable")  # nosemgrep
		frappe.clear_messages()
		with self.assertRaisesRegex(frappe.ValidationError, "Outlook sign-in isn't available"):
			email_oauth.initiate_mailbox_connect(email_account=account)
		self.assertEqual(
			[m["message"] for m in frappe.get_message_log()],
			["Outlook sign-in isn't available right now"],
		)

	def test_reconnect_of_a_mailbox_not_signed_in_through_frappe_cloud_is_refused(self) -> None:
		for token_uri in ("https://login.example.com/token", "frappe-cloud-relay:yahoo"):
			with self.subTest(token_uri):
				account = self.relay_mailbox(token_uri)
				self.assertRaises(
					frappe.ValidationError, email_oauth.initiate_mailbox_connect, email_account=account
				)
		self.pilot.assert_not_called()

	def test_provider_type_lists_every_provider(self) -> None:
		self.assertEqual(set(get_args(email_oauth.Provider)), set(email_oauth.ONE_CLICK_PROVIDERS))

	def test_central_refusal_keeps_no_note(self) -> None:
		self.pilot.side_effect = frappe.ValidationError("Return URL must be the email callback")
		self.assertRaises(frappe.ValidationError, email_oauth.initiate_mailbox_connect, "Outlook.com")
		state = self.pilot.call_args.args[1]["state"]
		self.assertIsNone(frappe.cache.get_value(f"pkce_verifier:{state}"))


class TestBoot(IntegrationTestCase):
	def test_desk_boot_says_whether_the_site_is_on_frappe_cloud_v2(self) -> None:
		from frappe.boot import get_bootinfo

		with self.set_user("test@example.com"):
			with patch.dict(frappe.conf, V2):
				boot = get_bootinfo()
				self.assertTrue(boot.is_v2_site)
				self.assertEqual(boot.one_click_email_services, {"Outlook.com": "Outlook"})
			with patch.dict(frappe.conf, {key: None for key in V2}):
				boot = get_bootinfo()
				self.assertFalse(boot.is_v2_site)
				self.assertEqual(boot.one_click_email_services, {})


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


class TestCallback(IntegrationTestCase):
	def setUp(self) -> None:
		self.enterContext(self.set_user(create_user(USER).name))
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(
			patch.object(email_oauth.PilotClient, "post", return_value=token("one@email-oauth.example.com"))
		)
		set_request(method="GET", base_url="http://hd.localhost:8000")
		self.addCleanup(self.delete_mailboxes)

	def delete_mailboxes(self) -> None:
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"Email Account", {"email_id": ("like", "%@email-oauth.example.com")}, pluck="name"
		):
			frappe.delete_doc("Email Account", name, force=True)
		frappe.db.commit()  # the callback commits the mailboxes it makes; # nosemgrep

	def note(self, **values) -> str:
		state = frappe.generate_hash()
		frappe.cache.set_value(
			f"pkce_verifier:{state}",
			{
				"user": USER,
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

		self.assertEqual(
			self.landed(),
			"http://hd.localhost:8000/helpdesk?email_oauth=connected&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft",
		)
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

		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		self.assertEqual(account.auth_method, "OAuth")
		self.assertEqual(account.connected_user, USER)
		self.assertEqual(account.email_server, "imap-mail.outlook.com")
		self.assertEqual(account.service, "Outlook.com")
		self.assertEqual([(f.folder_name, f.append_to) for f in account.imap_folder], [("INBOX", "ToDo")])
		app = frappe.get_doc("Connected App", account.connected_app)
		self.assertEqual(app.get_scopes(), SCOPES)
		self.assertEqual(app.client_id, "cid")
		self.assertEqual(app.authorization_uri, AUTHORIZE)
		self.assertEqual(app.provider_name, "Outlook (one@email-oauth.example.com)")
		self.assertEqual(app.token_uri, "frappe-cloud-relay:microsoft")
		self.assertIsNone(app.get_password("client_secret", raise_exception=False))
		self.assertEqual(app.get_token_cache(USER).get_password("refresh_token"), "rt")

	def test_lands_with_the_result_before_the_fragment(self) -> None:
		email_oauth.callback(state=self.note(redirect_to="/desk/email-account?view=list#top"), code="c")
		self.assertEqual(
			self.landed(),
			"http://hd.localhost:8000/desk/email-account?view=list&email_oauth=connected&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft#top",
		)

	def test_second_mailbox_is_added_beside_the_first(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		self.pilot.return_value = token("two@email-oauth.example.com", tid="work-tenant")
		email_oauth.callback(state=self.note(), code="c2")

		first, second = (
			frappe.get_doc("Email Account", {"email_id": f"{n}@email-oauth.example.com"})
			for n in ("one", "two")
		)
		self.assertNotEqual(first.connected_app, second.connected_app)
		self.assertEqual(second.email_server, "outlook.office365.com")
		self.assertEqual(second.smtp_server, "smtp.office365.com")
		self.assertEqual(second.service, "Outlook.com")

	def test_same_mailbox_again_creates_nothing(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		apps = frappe.db.count("Connected App")
		email_oauth.callback(state=self.note(), code="c2")
		self.assertEqual(
			self.landed(),
			"http://hd.localhost:8000/helpdesk?email_oauth=already_connected&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft",
		)
		self.assertEqual(frappe.db.count("Connected App"), apps)

	def test_reconnect_moves_the_mailbox_to_a_new_app(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		account.db_set({"enable_outgoing": 0, "use_ssl_for_outgoing": 1, "smtp_port": 465})
		old_app = account.connected_app

		email_oauth.callback(state=self.note(email_account=account.name), code="c2")

		self.assertTrue(
			self.landed().endswith(
				"?email_oauth=reconnected&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft"
			)
		)
		account.reload()
		self.assertNotEqual(account.connected_app, old_app)
		self.assertEqual(account.enable_outgoing, 0)
		self.assertEqual((account.use_ssl_for_outgoing, account.use_tls, account.smtp_port), (0, 1, "587"))
		self.assertTrue(frappe.get_doc("Connected App", account.connected_app).get_token_cache(USER))
		self.assertFalse(frappe.db.exists("Connected App", old_app))
		self.assertFalse(frappe.db.exists("Token Cache", {"connected_app": old_app}))
		self.assertEqual(frappe.db.count("Email Account", {"email_id": "one@email-oauth.example.com"}), 1)

	def test_reconnect_keeps_the_old_app_another_mailbox_links(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		duplicate = frappe.copy_doc(account)
		duplicate.update({"email_account_name": "one-incoming", "enable_outgoing": 0})
		duplicate.insert()

		email_oauth.callback(state=self.note(email_account=account.name), code="c2")

		self.assertTrue(
			self.landed().endswith(
				"?email_oauth=reconnected&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft"
			)
		)
		self.assertTrue(frappe.db.exists("Connected App", account.connected_app))
		self.assertTrue(frappe.db.exists("Token Cache", {"connected_app": account.connected_app}))

	def test_repointing_a_mailbox_deletes_its_old_app_and_tokens(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		self.pilot.return_value = token("two@email-oauth.example.com")
		email_oauth.callback(state=self.note(), code="c2")
		first, second = (
			frappe.get_doc("Email Account", {"email_id": f"{n}@email-oauth.example.com"})
			for n in ("one", "two")
		)
		old_app = first.connected_app

		first.connected_app = second.connected_app
		first.save()

		self.assertFalse(frappe.db.exists("Connected App", old_app))
		self.assertFalse(frappe.db.exists("Token Cache", {"connected_app": old_app}))
		self.assertTrue(frappe.db.exists("Connected App", second.connected_app))

	def test_reconnect_matches_the_mailbox_whatever_its_case(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		self.pilot.return_value = token("One@Email-OAuth.example.com")

		email_oauth.callback(state=self.note(email_account=account.name), code="c2")

		self.assertTrue(
			self.landed().endswith(
				"?email_oauth=reconnected&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft"
			)
		)
		self.assertNotEqual(
			frappe.db.get_value("Email Account", account.name, "connected_app"), account.connected_app
		)

	def test_reconnect_moves_a_pop_mailbox_to_imap(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		account.db_set("use_imap", 0)
		frappe.db.delete("IMAP Folder", {"parent": account.name})

		email_oauth.callback(state=self.note(email_account=account.name), code="c2")

		self.assertIn("email_oauth=reconnected", self.landed())
		account.reload()
		self.assertEqual(account.use_imap, 1)
		self.assertEqual([f.folder_name for f in account.imap_folder], ["INBOX"])

	def test_reconnect_with_another_mailbox_changes_nothing(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		apps = frappe.db.count("Connected App")
		self.pilot.return_value = token("two@email-oauth.example.com")

		email_oauth.callback(state=self.note(email_account=account.name), code="c2")

		self.assertTrue(
			self.landed().endswith(
				"?email_oauth=wrong_mailbox&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft"
			)
		)
		self.assertEqual(
			frappe.db.get_value("Email Account", account.name, "connected_app"), account.connected_app
		)
		self.assertEqual(frappe.db.count("Connected App"), apps)

	def test_cancelled_reconnect_names_the_mailbox(self) -> None:
		email_oauth.callback(state=self.note(), code="c1")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})

		email_oauth.callback(
			state=self.note(email_account=account.name),
			error="access_denied",
			error_description="AADSTS65004",
		)

		self.assertEqual(
			self.landed(),
			"http://hd.localhost:8000/helpdesk?email_oauth=cancelled&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft",
		)

	def test_reconnect_of_a_deleted_mailbox_fails_and_leaves_nothing(self) -> None:
		apps = frappe.db.count("Connected App")
		caches = frappe.db.count("Token Cache")

		email_oauth.callback(state=self.note(email_account="deleted@email-oauth.example.com"), code="c")

		self.assertTrue(self.landed().endswith("?email_oauth=failed&email_oauth_provider=microsoft"))
		self.assertEqual(frappe.db.count("Connected App"), apps)
		self.assertEqual(frappe.db.count("Token Cache"), caches)
		self.assertFalse(frappe.db.exists("Email Account", {"email_id": "one@email-oauth.example.com"}))

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
			with self.subTest(description), patch("frappe.log_error") as log:
				email_oauth.callback(state=self.note(), error=error, error_description=description)
				self.assertEqual(
					self.landed(),
					f"http://hd.localhost:8000/helpdesk?email_oauth={result}&email_oauth_provider=microsoft",
				)
				if result == "failed":
					log.assert_called_once_with("Email OAuth sign-in failed", f"{error}: {description}")
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
		self.assertTrue(
			self.landed().endswith("/helpdesk?email_oauth=expired&email_oauth_provider=microsoft")
		)

	def test_pilot_unreachable_is_failed(self) -> None:
		self.pilot.side_effect = frappe.ValidationError("Could not reach your server")
		with patch("frappe.log_error") as log:
			email_oauth.callback(state=self.note(), code="c")
		self.assertTrue(self.landed().endswith("/helpdesk?email_oauth=failed&email_oauth_provider=microsoft"))
		log.assert_called_once_with("Email OAuth connect failed")

	def test_off_host_redirect_lands_on_this_host(self) -> None:
		email_oauth.callback(state=self.note(redirect_to="https://evil.example/steal"), code="c")
		self.assertEqual(
			self.landed(),
			"http://hd.localhost:8000/desk?email_oauth=connected&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft",
		)

	def test_failed_save_leaves_nothing_behind(self) -> None:
		apps = frappe.db.count("Connected App")
		caches = frappe.db.count("Token Cache")
		smtp_off = "535 5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled"
		for message, tid, result in (
			(smtp_off, PERSONAL, "smtp_disabled_personal"),
			(smtp_off, "work-tenant", "smtp_disabled"),
			("User is authenticated but not connected.", PERSONAL, "imap_disabled"),
			("Something else", PERSONAL, "failed"),
		):
			self.pilot.return_value = token("one@email-oauth.example.com", tid=tid)
			with (
				self.subTest(result),
				patch.object(EmailAccount, "validate", side_effect=frappe.ValidationError(message)),
				patch("frappe.log_error") as log,
			):
				email_oauth.callback(state=self.note(), code="c")
				log.assert_called_once_with("Email OAuth connect failed")
				self.assertTrue(
					self.landed().endswith(
						f"?email_oauth={result}&email_oauth_mailbox=one%40email-oauth.example.com&email_oauth_provider=microsoft"
					)
				)
				self.assertEqual(frappe.db.count("Connected App"), apps)
				self.assertEqual(frappe.db.count("Token Cache"), caches)

	def test_deleting_the_mailbox_deletes_its_app_and_tokens(self) -> None:
		email_oauth.callback(state=self.note(), code="c")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})

		token_cache = f"{account.connected_app}-{USER}"

		account.delete()

		self.assertFalse(frappe.db.exists("Connected App", account.connected_app))
		self.assertFalse(frappe.db.exists("Token Cache", {"connected_app": account.connected_app}))
		auth = frappe.qb.Table("__Auth")
		self.assertFalse(frappe.qb.from_(auth).select(auth.name).where(auth.name == token_cache).run())

	def test_deleting_a_mailbox_keeps_an_app_another_mailbox_links(self) -> None:
		email_oauth.callback(state=self.note(), code="c")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		duplicate = frappe.copy_doc(account)
		duplicate.update({"email_account_name": "one-incoming", "enable_outgoing": 0})
		duplicate.insert()

		duplicate.delete()

		self.assertTrue(frappe.db.exists("Connected App", account.connected_app))
		self.assertTrue(frappe.db.exists("Token Cache", {"connected_app": account.connected_app}))

	def test_deleting_a_mailbox_keeps_a_customers_own_app(self) -> None:
		email_oauth.callback(state=self.note(), code="c")
		account = frappe.get_doc("Email Account", {"email_id": "one@email-oauth.example.com"})
		frappe.db.set_value(
			"Connected App", account.connected_app, "token_uri", "https://login.example.com/token"
		)
		self.addCleanup(frappe.delete_doc, "Connected App", account.connected_app, force=True)
		self.addCleanup(frappe.db.delete, "Token Cache", {"connected_app": account.connected_app})

		account.delete()

		self.assertTrue(frappe.db.exists("Connected App", account.connected_app))

	def test_guest_is_sent_to_login(self) -> None:
		with self.set_user("Guest"):
			email_oauth.callback(state="s", code="c")
		self.assertTrue(self.landed().startswith("/login?redirect-to="))


class TestRefresh(IntegrationTestCase):
	def setUp(self) -> None:
		# update_data commits the app, so its cleanup must commit too (cleanups run last-in, first-out)
		self.addCleanup(frappe.db.commit)
		self.enterContext(self.set_user(create_user(USER).name))
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(
			patch.object(email_oauth.PilotClient, "post", return_value=token("one@email-oauth.example.com"))
		)

	def expired_app(self, token_uri: str, client_secret: str | None = None) -> ConnectedApp:
		app = frappe.get_doc(
			{
				"doctype": "Connected App",
				"provider_name": "Outlook (one@email-oauth.example.com)",
				"client_id": "cid",
				"client_secret": client_secret,
				"token_uri": token_uri,
				"scopes": [{"scope": "offline_access"}, {"scope": "email"}],
			}
		).insert()
		frappe.get_doc({"doctype": "Token Cache", "connected_app": app.name, "user": USER}).update_data(
			{"access_token": "old", "refresh_token": "rt-old", "expires_in": -60}
		)
		self.addCleanup(frappe.delete_doc, "Connected App", app.name, force=True)
		self.addCleanup(frappe.db.delete, "Token Cache", {"connected_app": app.name})
		return app

	def test_relay_app_refreshes_through_pilot(self) -> None:
		app = self.expired_app("frappe-cloud-relay:microsoft")
		self.assertEqual(app.get_active_token(USER).get_password("access_token"), "at")
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
		with patch(
			"requests_oauthlib.OAuth2Session.refresh_token", return_value=token("x@example.com")
		) as own:
			app.get_active_token(USER)
		own.assert_called_once()
		self.pilot.assert_not_called()

	def assert_token_dropped(self, app: ConnectedApp) -> None:
		wait_for_job(f"delete_token_cache:{app.name}-{USER}")
		frappe.db.rollback()
		self.assertFalse(has_token(app.name, USER))

	def test_dead_grant_drops_the_tokens(self) -> None:
		app = self.expired_app("frappe-cloud-relay:microsoft")
		self.pilot.side_effect = frappe.ValidationError("invalid_grant")
		callers_work = frappe.get_doc({"doctype": "ToDo", "description": "email-oauth caller"}).insert()

		with patch("frappe.log_error") as log:
			self.assertIsNone(app.get_active_token(USER))
		self.assertEqual(log.call_args.kwargs["title"], "Token Refresh Error")
		self.assertTrue(frappe.db.exists("ToDo", callers_work.name))

		self.assert_token_dropped(app)
		self.assertFalse(frappe.db.exists("ToDo", callers_work.name))

	def test_dead_grant_on_a_customers_own_app_drops_the_tokens(self) -> None:
		app = self.expired_app("https://login.example.com/token", client_secret="their-secret")
		with (
			patch("requests_oauthlib.OAuth2Session.refresh_token", side_effect=InvalidGrantError()),
			patch("frappe.log_error") as log,
		):
			self.assertIsNone(app.get_active_token(USER))
		self.assertEqual(log.call_args.kwargs["title"], "Token Refresh Error")

		self.assert_token_dropped(app)

	def test_reauthorizing_before_the_drop_keeps_the_new_token(self) -> None:
		app = self.expired_app("https://login.example.com/token", client_secret="their-secret")
		with (
			patch("requests_oauthlib.OAuth2Session.refresh_token", side_effect=InvalidGrantError()),
			patch("frappe.log_error"),
			patch("frappe.enqueue") as enqueue,
		):
			self.assertIsNone(app.get_active_token(USER))
		frappe.get_doc("Token Cache", f"{app.name}-{USER}").update_data(
			{"access_token": "new", "refresh_token": "rt-new", "expires_in": 3600}
		)

		job = enqueue.call_args.kwargs
		delete_token_cache(name=job["name"], modified=job["modified"])
		self.assertTrue(has_token(app.name, USER))

	def test_other_refresh_failures_keep_the_tokens(self) -> None:
		app = self.expired_app("frappe-cloud-relay:microsoft")
		self.pilot.side_effect = frappe.ValidationError("Could not reach your server")

		with patch("frappe.log_error") as log:
			self.assertIsNone(app.get_active_token(USER))
		self.assertEqual(log.call_args.kwargs["title"], "Token Refresh Error")

		self.assertTrue(has_token(app.name, USER))
