# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from rauth import OAuth2Service

import frappe
from frappe.auth import CookieManager, LoginManager
from frappe.integrations.doctype.social_login_key.social_login_key import BaseUrlNotSetError
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils import set_request
from frappe.utils.oauth import (
	OAUTH_LOGIN_BINDING_COOKIE,
	consume_oauth_state,
	create_oauth_state,
	get_oauth2_authorize_url,
	login_via_oauth2,
)

TEST_GITHUB_USER = "githublogin@example.com"


class TestSocialLoginKey(FrappeTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		frappe.delete_doc("User", TEST_GITHUB_USER, force=True)
		super().setUp()
		frappe.set_user("Guest")

	def test_adding_frappe_social_login_provider(self):
		frappe.set_user("Administrator")
		provider_name = "Frappe"
		social_login_key = make_social_login_key(social_login_provider=provider_name)
		social_login_key.get_social_login_provider(provider_name, initialize=True)
		self.assertRaises(BaseUrlNotSetError, social_login_key.insert)

	def test_github_login_with_private_email(self):
		github_social_login_setup()

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_private_email

		state = create_oauth_state(None)  # Dummy code, real state token
		simulate_oauth_browser_roundtrip()
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", state)

	def test_github_login_with_public_email(self):
		github_social_login_setup()

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_public_email

		state = create_oauth_state(None)  # Dummy code, real state token
		simulate_oauth_browser_roundtrip()
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", state)

	def test_normal_signup_and_github_login(self):
		github_social_login_setup()

		if not frappe.db.exists("User", TEST_GITHUB_USER):
			user = frappe.new_doc("User", email=TEST_GITHUB_USER, first_name="GitHub Login")
			user.insert(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		state = create_oauth_state(None)
		simulate_oauth_browser_roundtrip()
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", state)
		self.assertEqual(frappe.session.user, TEST_GITHUB_USER)

	def test_oauth_state_helpers_reject_unknown_and_reused_tokens(self):
		"""consume_oauth_state must only resolve tokens it minted itself, and only once."""
		github_social_login_setup()
		self.assertIsNone(consume_oauth_state("attacker-forged-token"))
		self.assertIsNone(consume_oauth_state(""))

		state = create_oauth_state("/app/some-page")
		simulate_oauth_browser_roundtrip()
		self.assertEqual(consume_oauth_state(state), "/app/some-page")
		# same token can't be redeemed twice
		self.assertIsNone(consume_oauth_state(state))

	def test_oauth_state_without_binding_cookie_is_rejected(self):
		"""A `state` that is valid and unused must still be rejected if the request
		completing the callback doesn't carry the cookie set when the flow started -
		i.e. it isn't the same browser."""
		github_social_login_setup()

		state = create_oauth_state("/app/some-page")
		# NOTE: no simulate_oauth_browser_roundtrip() here - the callback arrives
		# without the binding cookie, as it would from a browser that never started
		# this login attempt.
		self.assertIsNone(consume_oauth_state(state))

	def test_states_survive_a_second_login_render(self):
		"""Re-rendering /login (a refresh, a second tab) must reuse the binding cookie the
		browser already holds, or it orphans every state minted by the earlier render."""
		github_social_login_setup()

		simulate_new_request()
		first_tab_state = create_oauth_state("/app/first-tab")
		issued_secret = current_binding_secret()

		# The browser loads /login again, sending the cookie it already holds.
		simulate_new_request(issued_secret)
		create_oauth_state("/app/second-tab")

		# Whatever cookie that render left the browser with is what the callback carries.
		simulate_new_request(current_binding_secret() or issued_secret)
		self.assertEqual(consume_oauth_state(first_tab_state), "/app/first-tab")

	def test_rejected_callback_leaves_other_pending_states_usable(self):
		"""A callback that fails binding validation must not retire the browser's cookie,
		which would take its other in-flight login attempts down with it."""
		github_social_login_setup()

		simulate_new_request()
		flow_a = create_oauth_state("/app/flow-a")
		flow_b = create_oauth_state("/app/flow-b")
		issued_secret = current_binding_secret()

		# A callback for flow A arrives without the binding cookie, and is rejected.
		simulate_new_request()
		self.assertIsNone(consume_oauth_state(flow_a))
		browser_dropped_cookie = OAUTH_LOGIN_BINDING_COOKIE in frappe.local.cookie_manager.to_delete

		# Flow B is still pending in that same browser and must remain redeemable.
		simulate_new_request(None if browser_dropped_cookie else issued_secret)
		self.assertEqual(consume_oauth_state(flow_b), "/app/flow-b")

	def test_completed_login_leaves_other_pending_states_usable(self):
		"""Completing one attempt must not retire the browser's binding cookie either: the
		cookie is shared by every attempt that browser has in flight, so doing so would
		break the ones still pending."""
		github_social_login_setup()

		simulate_new_request()
		flow_a = create_oauth_state("/app/flow-a")
		flow_b = create_oauth_state("/app/flow-b")
		issued_secret = current_binding_secret()

		# Flow A completes successfully.
		simulate_new_request(issued_secret)
		self.assertEqual(consume_oauth_state(flow_a), "/app/flow-a")
		browser_dropped_cookie = OAUTH_LOGIN_BINDING_COOKIE in frappe.local.cookie_manager.to_delete

		# Flow B, still pending in that same browser, must remain redeemable.
		simulate_new_request(None if browser_dropped_cookie else issued_secret)
		self.assertEqual(consume_oauth_state(flow_b), "/app/flow-b")

	def test_form_post_provider_gets_a_cross_site_binding_cookie(self):
		"""A form_post callback is a cross-site POST, which a Lax cookie is not sent on."""
		github_social_login_setup()

		def binding_samesite(*cross_site_flags, scheme="https"):
			set_request(path="/login", base_url=f"{scheme}://example.com")
			frappe.local.cookie_manager = CookieManager()
			for cross_site in cross_site_flags:
				create_oauth_state(None, cross_site=cross_site)
			return frappe.local.cookie_manager.cookies[OAUTH_LOGIN_BINDING_COOKIE]["samesite"]

		self.assertEqual(binding_samesite(False), "Lax")
		self.assertEqual(binding_samesite(True), "None")
		# either order on one page: the form_post button's cookie wins
		self.assertEqual(binding_samesite(False, True), "None")
		self.assertEqual(binding_samesite(True, False), "None")
		# browsers drop SameSite=None without Secure, which would break every provider
		self.assertEqual(binding_samesite(True, scheme="http"), "Lax")

	def test_form_post_callback_is_still_bound_to_the_browser(self):
		"""Relaxing SameSite for form_post must not relax the binding itself."""
		github_social_login_setup()
		frappe.db.set_value(
			"Social Login Key", "github", "auth_url_data", json.dumps({"response_mode": "form_post"})
		)

		set_request(path="/login", base_url="https://example.com")
		frappe.local.cookie_manager = CookieManager()

		def state_from_authorize_url():
			return parse_qs(urlparse(get_oauth2_authorize_url("github", "/app")).query)["state"][0]

		matching_state, mismatched_state = state_from_authorize_url(), state_from_authorize_url()
		cookie = frappe.local.cookie_manager.cookies[OAUTH_LOGIN_BINDING_COOKIE]
		self.assertEqual(cookie["samesite"], "None")

		simulate_new_request("another-browsers-secret")
		self.assertIsNone(consume_oauth_state(mismatched_state))

		simulate_new_request(cookie["value"])
		self.assertEqual(consume_oauth_state(matching_state), "/app")

	def test_forged_oauth_state_is_rejected_end_to_end(self):
		"""A state value that wasn't issued via create_oauth_state() must not log anyone in
		or produce a redirect, regardless of what it contains."""
		github_social_login_setup()

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", "attacker-forged-token")

		self.assertEqual(frappe.session.user, "Guest")
		self.assertEqual(frappe.local.response.get("http_status_code"), 417)
		self.assertNotEqual(frappe.local.response.get("type"), "redirect")

	def test_oauth_state_cannot_be_replayed(self):
		"""A legitimate state token must not be usable a second time."""
		github_social_login_setup()

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		state = create_oauth_state("/app/some-legit-page")
		simulate_oauth_browser_roundtrip()

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", state)
		self.assertEqual(frappe.session.user, TEST_GITHUB_USER)
		self.assertEqual(frappe.local.response.get("location"), "/app/some-legit-page")

		frappe.set_user("Guest")
		frappe.local.response.pop("location", None)
		frappe.local.response.pop("http_status_code", None)

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", state)
		self.assertEqual(frappe.session.user, "Guest")
		self.assertEqual(frappe.local.response.get("http_status_code"), 417)

	def test_force_disabled_signups(self):
		key = github_social_login_setup()
		key.sign_ups = "Deny"
		key.save(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		state = create_oauth_state(None)
		simulate_oauth_browser_roundtrip()
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", state)
		self.assertEqual(frappe.session.user, "Guest")

	def test_disabled_social_login_key_is_refused(self):
		github_social_login_setup()
		self.addCleanup(frappe.db.set_value, "Social Login Key", "github", "enable_social_login", 1)
		frappe.db.set_value("Social Login Key", "github", "enable_social_login", 0)

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			self.assertRaises(
				frappe.PermissionError, login_via_oauth2, "github", "iwriu", create_oauth_state(None)
			)

		mock_session.get.assert_not_called()
		self.assertEqual(frappe.session.user, "Guest")

	@change_settings("Website Settings", disable_signup=1)
	def test_force_enabled_signups(self):
		"""Social login key can override website settings for disabled signups."""
		key = github_social_login_setup()
		key.sign_ups = "Allow"
		key.save(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		state = create_oauth_state(None)
		simulate_oauth_browser_roundtrip()
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", state)

		self.assertEqual(frappe.session.user, TEST_GITHUB_USER)


def make_social_login_key(**kwargs):
	kwargs["doctype"] = "Social Login Key"
	if "provider_name" not in kwargs:
		kwargs["provider_name"] = "Test OAuth2 Provider"
	return frappe.get_doc(kwargs)


def create_or_update_social_login_key():
	# used in other tests (connected app, oauth20)
	try:
		social_login_key = frappe.get_doc("Social Login Key", "frappe")
	except frappe.DoesNotExistError:
		social_login_key = frappe.new_doc("Social Login Key")
	social_login_key.get_social_login_provider("Frappe", initialize=True)
	social_login_key.base_url = frappe.utils.get_url()
	social_login_key.enable_social_login = 0
	social_login_key.save()
	frappe.db.commit()

	return social_login_key


def create_github_social_login_key():
	if frappe.db.exists("Social Login Key", "github"):
		return frappe.get_doc("Social Login Key", "github")
	else:
		provider_name = "GitHub"
		social_login_key = make_social_login_key(social_login_provider=provider_name)
		social_login_key.get_social_login_provider(provider_name, initialize=True)

		social_login_key.client_id = "h6htd6q"
		social_login_key.client_secret = "keoererk988ekkhf8w9e8ewrjhhkjer9889"
		social_login_key.insert(ignore_permissions=True)
		return social_login_key


def github_response_for_private_email(url, *args, **kwargs):
	if url == "user":
		return_value = {
			"login": "dummy_username",
			"id": "223342",
			"email": None,
			"first_name": "Github Private",
		}
	else:
		return_value = [{"email": "github@example.com", "primary": True, "verified": True}]

	return MagicMock(status_code=200, json=MagicMock(return_value=return_value))


def github_response_for_public_email(url, *args, **kwargs):
	if url == "user":
		return_value = {
			"login": "dummy_username",
			"id": "223343",
			"email": "github_public@example.com",
			"first_name": "Github Public",
		}

	return MagicMock(status_code=200, json=MagicMock(return_value=return_value))


def github_response_for_login(url, *args, **kwargs):
	if url == "user":
		return_value = {
			"login": "dummy_username",
			"id": "223346",
			"email": None,
			"first_name": "Github Login",
		}
	else:
		return_value = [{"email": TEST_GITHUB_USER, "primary": True, "verified": True}]

	return MagicMock(status_code=200, json=MagicMock(return_value=return_value))


def github_social_login_setup():
	set_request(path="/random")
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()

	return create_github_social_login_key()


def simulate_oauth_browser_roundtrip():
	"""Re-issue the current request carrying the binding cookie `create_oauth_state`
	just set on `frappe.local.cookie_manager`, as a real browser would on callback."""
	binding_secret = frappe.local.cookie_manager.cookies[OAUTH_LOGIN_BINDING_COOKIE]["value"]
	set_request(path="/random", headers=[("Cookie", f"{OAUTH_LOGIN_BINDING_COOKIE}={binding_secret}")])


def simulate_new_request(binding_secret=None):
	"""A fresh HTTP request, optionally carrying the binding cookie. Each request gets its
	own CookieManager, so a cookie set on a previous response is not visible to this one."""
	headers = [("Cookie", f"{OAUTH_LOGIN_BINDING_COOKIE}={binding_secret}")] if binding_secret else []
	set_request(path="/random", headers=headers)
	frappe.local.cookie_manager = CookieManager()


def current_binding_secret():
	"""The binding cookie this request's response would hand back, if any."""
	cookie = frappe.local.cookie_manager.cookies.get(OAUTH_LOGIN_BINDING_COOKIE)
	return cookie["value"] if cookie else None
