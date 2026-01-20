# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Test for OAuth2 Refresh Token Flow

This test verifies that the refresh token grant type works correctly,
specifically testing the fix for the 403 Permission Error that occurred
when Guest users attempted to refresh their access tokens.
"""

from urllib.parse import parse_qs

import frappe
from frappe.tests.test_oauth20 import FrappeRequestTestCase, update_client_for_auth_code_grant
from frappe.tests.utils import make_test_records


class TestOAuth20RefreshToken(FrappeRequestTestCase):
	"""Test OAuth2 Refresh Token functionality"""

	site = frappe.local.site

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_test_records("User")

		cls.form_header = {"content-type": "application/x-www-form-urlencoded"}
		cls.scope = "all openid"
		cls.redirect_uri = "http://localhost"

		# Set Frappe server URL required for id_token generation
		frappe_login_key = frappe.new_doc("Social Login Key")
		frappe_login_key.get_social_login_provider("Frappe", initialize=True)
		frappe_login_key.base_url = frappe.utils.get_url()
		frappe_login_key.enable_social_login = 0
		frappe_login_key.insert(ignore_if_duplicate=True)
		frappe.db.commit()

	def setUp(self):
		from frappe.tests.test_api import get_test_client

		self.TEST_CLIENT = get_test_client()
		self.oauth_client = frappe.new_doc("OAuth Client")
		self.oauth_client.update(
			{
				"app_name": "_Test OAuth Client Refresh Token",
				"client_secret": "test_client_secret_refresh",
				"default_redirect_uri": "http://localhost",
				"docstatus": 0,
				"doctype": "OAuth Client",
				"grant_type": "Authorization Code",
				"name": "test_client_id_refresh",
				"redirect_uris": "http://localhost",
				"response_type": "Code",
				"scopes": "all openid",
				"skip_authorization": 1,
			}
		)
		self.oauth_client.insert()

		self.client_id = self.oauth_client.get("client_id")
		self.client_secret = self.oauth_client.get("client_secret")

	def tearDown(self):
		self.oauth_client.delete(force=True)
		frappe.db.rollback()

	def test_refresh_token_grant(self):
		"""
		Test the complete OAuth2 refresh token flow:
		1. Authorize and get authorization code
		2. Exchange code for access token and refresh token
		3. Use refresh token to get a new access token (this was failing with 403)
		"""
		update_client_for_auth_code_grant(self.client_id)

		# Step 1: Go to Authorize URL and get authorization code
		self.TEST_CLIENT.set_cookie(key="sid", value=self.sid)
		resp = self.get(
			"/api/method/frappe.integrations.oauth2.authorize",
			{
				"client_id": self.client_id,
				"scope": self.scope,
				"response_type": "code",
				"redirect_uri": self.redirect_uri,
			},
			follow_redirects=True,
		)
		query = parse_qs(resp.request.environ["QUERY_STRING"])
		auth_code = query.get("code")[0]

		# Step 2: Exchange authorization code for tokens
		token_response = self.post(
			"/api/method/frappe.integrations.oauth2.get_token",
			headers=self.form_header,
			data={
				"grant_type": "authorization_code",
				"code": auth_code,
				"redirect_uri": self.redirect_uri,
				"client_id": self.client_id,
				"scope": self.scope,
			},
		)

		# Verify initial token response
		bearer_token = token_response.json
		self.assertTrue(bearer_token.get("access_token"), "Access token should be present")
		self.assertTrue(bearer_token.get("refresh_token"), "Refresh token should be present")
		self.assertTrue(bearer_token.get("expires_in"), "Expires_in should be present")
		self.assertTrue(bearer_token.get("token_type") == "Bearer", "Token type should be Bearer")

		original_access_token = bearer_token.get("access_token")
		refresh_token = bearer_token.get("refresh_token")

		# Step 3: Use refresh token to get a new access token
		# This is the critical test - it should NOT return a 403 error
		refresh_response = self.post(
			"/api/method/frappe.integrations.oauth2.get_token",
			headers=self.form_header,
			data={
				"grant_type": "refresh_token",
				"refresh_token": refresh_token,
				"client_id": self.client_id,
				"client_secret": self.client_secret,
				"scope": self.scope,
			},
		)

		# Verify refresh token response
		self.assertEqual(
			refresh_response.status_code,
			200,
			f"Refresh token request should succeed with 200, got {refresh_response.status_code}",
		)

		refreshed_token = refresh_response.json
		self.assertTrue(refreshed_token.get("access_token"), "New access token should be present")
		self.assertTrue(refreshed_token.get("expires_in"), "Expires_in should be present")
		self.assertTrue(refreshed_token.get("token_type") == "Bearer", "Token type should be Bearer")

		# Verify we got a new access token (it should be different from the original)
		new_access_token = refreshed_token.get("access_token")
		self.assertNotEqual(
			original_access_token,
			new_access_token,
			"New access token should be different from original",
		)

		# Verify the new access token works
		from frappe.tests.test_oauth20 import check_valid_openid_response

		self.assertTrue(
			check_valid_openid_response(access_token=new_access_token, client=self),
			"New access token should be valid",
		)

	def test_refresh_token_without_client_secret(self):
		"""
		Test refresh token flow without client_secret (for public clients).
		This should also work without permission errors.
		"""
		update_client_for_auth_code_grant(self.client_id)

		# Get initial tokens
		self.TEST_CLIENT.set_cookie(key="sid", value=self.sid)
		resp = self.get(
			"/api/method/frappe.integrations.oauth2.authorize",
			{
				"client_id": self.client_id,
				"scope": self.scope,
				"response_type": "code",
				"redirect_uri": self.redirect_uri,
			},
			follow_redirects=True,
		)
		query = parse_qs(resp.request.environ["QUERY_STRING"])
		auth_code = query.get("code")[0]

		token_response = self.post(
			"/api/method/frappe.integrations.oauth2.get_token",
			headers=self.form_header,
			data={
				"grant_type": "authorization_code",
				"code": auth_code,
				"redirect_uri": self.redirect_uri,
				"client_id": self.client_id,
				"scope": self.scope,
			},
		)

		bearer_token = token_response.json
		refresh_token = bearer_token.get("refresh_token")

		# Try to refresh without client_secret
		refresh_response = self.post(
			"/api/method/frappe.integrations.oauth2.get_token",
			headers=self.form_header,
			data={
				"grant_type": "refresh_token",
				"refresh_token": refresh_token,
				"client_id": self.client_id,
				# Note: no client_secret provided
				"scope": self.scope,
			},
		)

		# Should succeed (status 200) without permission errors
		self.assertEqual(
			refresh_response.status_code,
			200,
			f"Refresh token without client_secret should succeed, got {refresh_response.status_code}",
		)

	def test_refresh_token_with_invalid_token(self):
		"""
		Test that invalid refresh tokens are properly rejected.
		"""
		# Try to use a non-existent refresh token
		refresh_response = self.post(
			"/api/method/frappe.integrations.oauth2.get_token",
			headers=self.form_header,
			data={
				"grant_type": "refresh_token",
				"refresh_token": "invalid_refresh_token_12345",
				"client_id": self.client_id,
				"client_secret": self.client_secret,
			},
		)

		# Should return an error (not 200)
		self.assertNotEqual(
			refresh_response.status_code,
			200,
			"Invalid refresh token should not succeed",
		)
