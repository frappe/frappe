# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from rauth import OAuth2Service

import frappe
from frappe.auth import CookieManager, LoginManager
from frappe.integrations.doctype.social_login_key.social_login_key import BaseUrlNotSetError
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.utils.oauth import (
	consume_oauth_state,
	create_oauth_state,
	enforce_office_365_tenant,
	get_info_via_oauth,
	get_verified_office_365_claims,
	login_via_oauth2,
)

TEST_GITHUB_USER = "githublogin@example.com"
TEST_OFFICE_365_USER = "user@office365test.example"


class TestSocialLoginKey(IntegrationTestCase):
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

	@IntegrationTestCase.change_settings("Website Settings", disable_signup=1)
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

	def test_custom_provider_rejects_unverified_email_by_default(self):
		frappe.set_user("Administrator")
		key = custom_social_login_setup("testcustom-unverified")

		mock_session = MagicMock()
		mock_session.get.return_value = MagicMock(
			status_code=200,
			json=MagicMock(
				return_value={"email": "victim@example.com", "email_verified": False, "sub": "attacker"}
			),
		)
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			self.assertRaises(frappe.ValidationError, get_info_via_oauth, key.name, "iwriu")

	def test_custom_provider_trust_flag_allows_silent_provider(self):
		"""Trust flag fills in only when the provider omits the claim entirely."""
		frappe.set_user("Administrator")
		key = custom_social_login_setup("testcustom-trusted")
		key.trust_email_without_verified_claim = 1
		key.save(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.return_value = MagicMock(
			status_code=200,
			json=MagicMock(return_value={"email": "victim@example.com", "sub": "attacker"}),
		)
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			info = get_info_via_oauth(key.name, "iwriu")
		self.assertEqual(info.get("email"), "victim@example.com")

	def test_custom_provider_trust_flag_never_overrides_explicit_false(self):
		"""Trust flag must not override a provider's explicit email_verified: false."""
		frappe.set_user("Administrator")
		key = custom_social_login_setup("testcustom-trusted-explicit-false")
		key.trust_email_without_verified_claim = 1
		key.save(ignore_permissions=True)

		mock_session = MagicMock()
		mock_session.get.return_value = MagicMock(
			status_code=200,
			json=MagicMock(
				return_value={"email": "victim@example.com", "email_verified": False, "sub": "attacker"}
			),
		)
		with patch.object(OAuth2Service, "get_auth_session", return_value=mock_session):
			self.assertRaises(frappe.ValidationError, get_info_via_oauth, key.name, "iwriu")

	def test_office_365_rejects_unpinned_tenant_by_default(self):
		"""A newly configured Office 365 key with no Tenant ID and no opt-in must not log anyone in."""
		office_365_social_login_setup()

		with (
			patch.object(OAuth2Service, "get_auth_session", return_value=make_office_365_session("tenant-a")),
			patch(
				"frappe.utils.oauth.get_verified_office_365_claims",
				return_value=office_365_claims("tenant-a"),
			),
		):
			self.assertRaises(
				frappe.ValidationError, get_info_via_oauth, "office_365", "iwriu", id_token=True
			)

	def test_office_365_rejects_mismatched_tenant(self):
		"""A token issued by a tenant other than the configured one must be rejected."""
		office_365_social_login_setup(tenant_id="tenant-a")

		with (
			patch.object(OAuth2Service, "get_auth_session", return_value=make_office_365_session("tenant-b")),
			patch(
				"frappe.utils.oauth.get_verified_office_365_claims",
				return_value=office_365_claims("tenant-b"),
			),
		):
			self.assertRaises(
				frappe.ValidationError, get_info_via_oauth, "office_365", "iwriu", id_token=True
			)

	def test_office_365_allows_matching_tenant(self):
		office_365_social_login_setup(tenant_id="tenant-a")

		with (
			patch.object(OAuth2Service, "get_auth_session", return_value=make_office_365_session("tenant-a")),
			patch(
				"frappe.utils.oauth.get_verified_office_365_claims",
				return_value=office_365_claims("tenant-a"),
			),
		):
			info = get_info_via_oauth("office_365", "iwriu", id_token=True)
		self.assertEqual(info["upn"], TEST_OFFICE_365_USER)
		self.assertTrue(info["email_verified"])

	def test_office_365_trust_any_tenant_bypasses_pinning(self):
		"""The explicit insecure opt-in must keep working for admins who ask for it."""
		office_365_social_login_setup(trust_any_tenant=1)

		with (
			patch.object(OAuth2Service, "get_auth_session", return_value=make_office_365_session("tenant-c")),
			patch(
				"frappe.utils.oauth.get_verified_office_365_claims",
				return_value=office_365_claims("tenant-c"),
			),
		):
			info = get_info_via_oauth("office_365", "iwriu", id_token=True)
		self.assertEqual(info["upn"], TEST_OFFICE_365_USER)

	def test_enforce_office_365_tenant_directly(self):
		office_365_social_login_setup(tenant_id="tenant-a")

		enforce_office_365_tenant({"tid": "tenant-a"}, "office_365")  # does not raise
		self.assertRaises(
			frappe.ValidationError, enforce_office_365_tenant, {"tid": "tenant-b"}, "office_365"
		)
		self.assertRaises(frappe.ValidationError, enforce_office_365_tenant, {}, "office_365")

	def test_office_365_id_token_signature_is_verified(self):
		"""A token not signed by the key Microsoft's JWKS endpoint actually vends must be rejected."""
		office_365_social_login_setup(tenant_id="tenant-a")

		signing_key, other_key = make_rsa_keypair(), make_rsa_keypair()
		claims = office_365_claims("tenant-a")
		claims["aud"] = "client-x"
		token = jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-kid"})

		fake_jwks_client = MagicMock()
		fake_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(
			key=serialization.load_pem_private_key(other_key, password=None).public_key()
		)
		with patch("frappe.utils.oauth._get_office_365_jwks_client", return_value=fake_jwks_client):
			self.assertRaises(jwt.InvalidTokenError, get_verified_office_365_claims, token, "client-x")

	def test_office_365_id_token_valid_signature_decodes(self):
		office_365_social_login_setup(tenant_id="tenant-a")

		signing_key = make_rsa_keypair()
		claims = office_365_claims("tenant-a")
		claims["aud"] = "client-x"
		token = jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-kid"})

		fake_jwks_client = MagicMock()
		fake_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(
			key=serialization.load_pem_private_key(signing_key, password=None).public_key()
		)
		with patch("frappe.utils.oauth._get_office_365_jwks_client", return_value=fake_jwks_client):
			info = get_verified_office_365_claims(token, "client-x")
		self.assertEqual(info["tid"], "tenant-a")


def office_365_social_login_setup(tenant_id: str | None = None, trust_any_tenant: int = 0):
	set_request(path="/random")
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()

	if frappe.db.exists("Social Login Key", "office_365"):
		key = frappe.get_doc("Social Login Key", "office_365")
	else:
		key = frappe.get_doc(
			doctype="Social Login Key",
			social_login_provider="Office 365",
			provider_name="Office 365",
			client_id="client-x",
			client_secret="secret",
			base_url="https://login.microsoftonline.com",
			authorize_url="https://login.microsoftonline.com/common/oauth2/authorize",
			access_token_url="https://login.microsoftonline.com/common/oauth2/token",
			redirect_url="/api/method/frappe.integrations.oauth2_logins.login_via_office365",
			custom_base_url=0,
			enable_social_login=1,
		).insert(ignore_permissions=True)

	key.tenant_id = tenant_id
	key.trust_any_tenant = trust_any_tenant
	key.save(ignore_permissions=True)
	return key


def make_office_365_session(tenant_id: str):
	"""A rauth session stub whose access_token_response carries a placeholder id_token.

	The token's contents don't matter in tests that mock get_verified_office_365_claims
	directly; only its presence in the access_token_response JSON is exercised here.
	"""
	mock_session = MagicMock()
	mock_session.access_token_response.text = json.dumps({"id_token": f"dummy.token.for.{tenant_id}"})
	return mock_session


def office_365_claims(tenant_id: str) -> dict:
	return {"tid": tenant_id, "upn": TEST_OFFICE_365_USER, "sub": "test-oid"}


def make_rsa_keypair() -> bytes:
	"""Return a fresh RSA private key, PEM-encoded, for signing test JWTs."""
	key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	return key.private_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PrivateFormat.PKCS8,
		encryption_algorithm=serialization.NoEncryption(),
	)


def custom_social_login_setup(provider_name: str):
	set_request(path="/random")
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()

	if frappe.db.exists("Social Login Key", frappe.scrub(provider_name)):
		return frappe.get_doc("Social Login Key", frappe.scrub(provider_name))

	return frappe.get_doc(
		doctype="Social Login Key",
		social_login_provider="Custom",
		provider_name=provider_name,
		client_id="x",
		client_secret="y",
		base_url="http://127.0.0.1:9001",
		authorize_url="/authorize",
		access_token_url="/token",
		api_endpoint="/userinfo",
		redirect_url=f"/api/method/frappe.integrations.oauth2_logins.custom/{frappe.scrub(provider_name)}",
		custom_base_url=1,
		enable_social_login=1,
	).insert(ignore_permissions=True)


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
