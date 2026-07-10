# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.patches.v16_0.hash_oauth_bearer_tokens import execute as hash_existing_tokens
from frappe.tests import IntegrationTestCase
from frappe.utils import sha256_hash


class TestOAuthBearerToken(IntegrationTestCase):
	def test_tokens_are_hashed_before_insert(self):
		access_token = frappe.generate_hash()
		refresh_token = frappe.generate_hash()

		token = make_bearer_token(access_token, refresh_token)

		self.assertNotIn(token.name, (access_token, sha256_hash(access_token)))
		self.assertEqual(token.access_token, sha256_hash(access_token))
		self.assertEqual(token.refresh_token, sha256_hash(refresh_token))

	def test_refresh_token_is_looked_up_by_hash(self):
		from frappe.oauth import OAuthWebRequestValidator

		refresh_token = frappe.generate_hash()
		make_bearer_token(frappe.generate_hash(), refresh_token)
		request = frappe._dict()
		validator = OAuthWebRequestValidator()

		self.assertEqual(validator.get_original_scopes(refresh_token, request), "all openid")
		self.assertTrue(validator.validate_refresh_token(refresh_token, None, request))
		self.assertEqual(request.user, "Administrator")

	def test_patch_hashes_existing_tokens(self):
		access_token = frappe.generate_hash()
		refresh_token = frappe.generate_hash()
		token = make_bearer_token(access_token, refresh_token)

		token_table = frappe.qb.DocType("OAuth Bearer Token")
		(
			frappe.qb.update(token_table)
			.set(token_table.name, access_token)
			.set(token_table.access_token, access_token)
			.set(token_table.refresh_token, refresh_token)
			.where(token_table.name == token.name)
		).run()

		hash_existing_tokens()

		stored_token = frappe.get_doc("OAuth Bearer Token", {"access_token": sha256_hash(access_token)})
		self.assertNotIn(stored_token.name, (access_token, sha256_hash(access_token)))
		self.assertEqual(stored_token.access_token, sha256_hash(access_token))
		self.assertEqual(stored_token.refresh_token, sha256_hash(refresh_token))
		self.assertFalse(frappe.db.exists("OAuth Bearer Token", access_token))


def make_bearer_token(access_token: str, refresh_token: str):
	return frappe.get_doc(
		{
			"doctype": "OAuth Bearer Token",
			"access_token": access_token,
			"refresh_token": refresh_token,
			"expires_in": 3600,
			"scopes": "all openid",
			"status": "Active",
			"user": "Administrator",
		}
	).insert(ignore_permissions=True)
