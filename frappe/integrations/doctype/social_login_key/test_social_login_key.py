# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import MagicMock, patch

from rauth import OAuth2Service

import frappe
from frappe.auth import CookieManager, LoginManager
from frappe.integrations.doctype.social_login_key.social_login_key import BaseUrlNotSetError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.utils.oauth import login_via_oauth2


class TestSocialLoginKey(FrappeTestCase):
	def test_adding_frappe_social_login_provider(self):
		provider_name = "Frappe"
		social_login_key = make_social_login_key(social_login_provider=provider_name)
		social_login_key.get_social_login_provider(provider_name, initialize=True)
		self.assertRaises(BaseUrlNotSetError, social_login_key.insert)

	def test_github_login_with_private_email(self):
		github_social_login_setup()

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_private_email

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", {"token": "ewrwerwer"})  # Dummy code and state token

	def test_github_login_with_public_email(self):
		github_social_login_setup()

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_public_email

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", {"token": "ewrwerwer"})  # Dummy code and state token

	def test_normal_signup_and_github_login(self):
		github_social_login_setup()

		if not frappe.db.exists("User", "githublogin@example.com"):
			user = frappe.get_doc(
				{"doctype": "User", "email": "githublogin@example.com", "first_name": "GitHub Login"}
			)
			user.save(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.side_effect = github_response_for_login

		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			login_via_oauth2("github", "iwriu", {"token": "ewrwerwer"})


def make_social_login_key(**kwargs):
	kwargs["doctype"] = "Social Login Key"
	if not "provider_name" in kwargs:
		kwargs["provider_name"] = "Test OAuth2 Provider"
	doc = frappe.get_doc(kwargs)
	return doc


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

		# Dummy client_id and client_secret
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
		return_value = [{"email": "githublogin@example.com", "primary": True, "verified": True}]

	return MagicMock(status_code=200, json=MagicMock(return_value=return_value))


def github_social_login_setup():
	set_request(path="/random")
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()

	create_github_social_login_key()
