# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import MagicMock, patch

from rauth import OAuth2Service

import frappe
from frappe.auth import CookieManager, LoginManager
from frappe.integrations.doctype.social_login_key.social_login_key import BaseUrlNotSetError
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils import set_request
from frappe.utils.oauth import consume_oauth_state, create_oauth_state, login_via_oauth2

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

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", create_oauth_state(None))  # Dummy code, real state token

	def test_github_login_with_public_email(self):
		github_social_login_setup()

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_public_email

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", create_oauth_state(None))  # Dummy code, real state token

	def test_normal_signup_and_github_login(self):
		github_social_login_setup()

		if not frappe.db.exists("User", TEST_GITHUB_USER):
			user = frappe.new_doc("User", email=TEST_GITHUB_USER, first_name="GitHub Login")
			user.insert(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", create_oauth_state(None))
		self.assertEqual(frappe.session.user, TEST_GITHUB_USER)

	def test_oauth_state_helpers_reject_unknown_and_reused_tokens(self):
		"""consume_oauth_state must only resolve tokens it minted itself, and only once."""
		self.assertIsNone(consume_oauth_state("attacker-forged-token"))
		self.assertIsNone(consume_oauth_state(""))

		state = create_oauth_state("/app/some-page")
		self.assertEqual(consume_oauth_state(state), "/app/some-page")
		# same token can't be redeemed twice
		self.assertIsNone(consume_oauth_state(state))

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

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", create_oauth_state(None))
		self.assertEqual(frappe.session.user, "Guest")

	@change_settings("Website Settings", disable_signup=1)
	def test_force_enabled_signups(self):
		"""Social login key can override website settings for disabled signups."""
		key = github_social_login_setup()
		key.sign_ups = "Allow"
		key.save(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", create_oauth_state(None))

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
