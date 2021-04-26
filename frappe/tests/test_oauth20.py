# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest
import requests
import jwt
from six.moves.urllib.parse import urlparse, parse_qs, urljoin
from urllib.parse import urlencode, quote

import frappe
from frappe.test_runner import make_test_records
from frappe.integrations.oauth2 import encode_params

class TestOAuth20(unittest.TestCase):

	def setUp(self):
		make_test_records("OAuth Client")
		make_test_records("User")
		self.client_id = frappe.get_all("OAuth Client", fields=["*"])[0].get("client_id")
		self.form_header = {"content-type": "application/x-www-form-urlencoded"}
		self.scope = "all openid"
		self.redirect_uri = "http://localhost"

		# Set Frappe server URL reqired for id_token generation
		try:
			frappe_login_key = frappe.get_doc("Social Login Key", "frappe")
		except frappe.DoesNotExistError:
			frappe_login_key = frappe.new_doc("Social Login Key")

		frappe_login_key.get_social_login_provider("Frappe", initialize=True)
		frappe_login_key.base_url = frappe.utils.get_url()
		frappe_login_key.enable_social_login = 0
		frappe_login_key.save()
		frappe.db.commit()

	def test_invalid_login(self):
		self.assertFalse(check_valid_openid_response())

	def test_login_using_authorization_code(self):
		update_client_for_auth_code_grant(self.client_id)

		session = requests.Session()
		login(session)

		redirect_destination = None

		# Go to Authorize url
		try:
			session.get(
				get_full_url("/api/method/frappe.integrations.oauth2.authorize"),
				params=encode_params({
					"client_id": self.client_id,
					"scope": self.scope,
					"response_type": "code",
					"redirect_uri": self.redirect_uri
				})
			)
		except requests.exceptions.ConnectionError as ex:
			redirect_destination = ex.request.url

		# Get authorization code from redirected URL
		query = parse_qs(urlparse(redirect_destination).query)
		auth_code = query.get("code")[0]

		# Request for bearer token
		token_response = requests.post(
			get_full_url("/api/method/frappe.integrations.oauth2.get_token"),
			headers=self.form_header,
			data=encode_params({
				"grant_type": "authorization_code",
				"code": auth_code,
				"redirect_uri": self.redirect_uri,
				"client_id": self.client_id,
				"scope": self.scope,
			})
		)

		# Parse bearer token json
		bearer_token = token_response.json()

		self.assertTrue(bearer_token.get("access_token"))
		self.assertTrue(bearer_token.get("expires_in"))
		self.assertTrue(bearer_token.get("id_token"))
		self.assertTrue(bearer_token.get("refresh_token"))
		self.assertTrue(bearer_token.get("scope"))
		self.assertTrue(bearer_token.get("token_type") == "Bearer")
		self.assertTrue(check_valid_openid_response(bearer_token.get("access_token")))

	def test_login_using_authorization_code_with_pkce(self):
		update_client_for_auth_code_grant(self.client_id)

		session = requests.Session()
		login(session)

		redirect_destination = None

		# Go to Authorize url
		try:
			session.get(
				get_full_url("/api/method/frappe.integrations.oauth2.authorize"),
				params=encode_params({
					"client_id": self.client_id,
					"scope": self.scope,
					"response_type": "code",
					"redirect_uri": self.redirect_uri,
					"code_challenge_method": 'S256',
					"code_challenge": '21XaP8MJjpxCMRxgEzBP82sZ73PRLqkyBUta1R309J0' ,
				})
			)
		except requests.exceptions.ConnectionError as ex:
			redirect_destination = ex.request.url

		# Get authorization code from redirected URL
		query = parse_qs(urlparse(redirect_destination).query)
		auth_code = query.get("code")[0]

		# Request for bearer token
		token_response = requests.post(
			get_full_url("/api/method/frappe.integrations.oauth2.get_token"),
			headers=self.form_header,
			data=encode_params({
				"grant_type": "authorization_code",
				"code": auth_code,
				"redirect_uri": self.redirect_uri,
				"client_id": self.client_id,
				"scope": self.scope,
				"code_verifier": "420",
			})
		)

		# Parse bearer token json
		bearer_token = token_response.json()

		self.assertTrue(bearer_token.get("access_token"))
		self.assertTrue(bearer_token.get("id_token"))

	def test_revoke_token(self):
		client = frappe.get_doc("OAuth Client", self.client_id)
		client.grant_type = "Authorization Code"
		client.response_type = "Code"
		client.save()
		frappe.db.commit()

		session = requests.Session()
		login(session)

		redirect_destination = None

		# Go to Authorize url
		try:
			session.get(
				get_full_url("/api/method/frappe.integrations.oauth2.authorize"),
				params=encode_params({
					"client_id": self.client_id,
					"scope": self.scope,
					"response_type": "code",
					"redirect_uri": self.redirect_uri
				})
			)
		except requests.exceptions.ConnectionError as ex:
			redirect_destination = ex.request.url

		# Get authorization code from redirected URL
		query = parse_qs(urlparse(redirect_destination).query)
		auth_code = query.get("code")[0]

		# Request for bearer token
		token_response = requests.post(
			get_full_url("/api/method/frappe.integrations.oauth2.get_token"),
			headers=self.form_header,
			data=encode_params({
				"grant_type": "authorization_code",
				"code": auth_code,
				"redirect_uri": self.redirect_uri,
				"client_id": self.client_id
			})
		)

		# Parse bearer token json
		bearer_token = token_response.json()

		# Revoke Token
		revoke_token_response = requests.post(
			get_full_url("/api/method/frappe.integrations.oauth2.revoke_token"),
			headers=self.form_header,
			data={"token": bearer_token.get("access_token")}
		)

		self.assertTrue(revoke_token_response.status_code == 200)

		# Check revoked token
		self.assertFalse(check_valid_openid_response(bearer_token.get("access_token")))

	def test_resource_owner_password_credentials_grant(self):
		client = frappe.get_doc("OAuth Client", self.client_id)
		client.grant_type = "Authorization Code"
		client.response_type = "Code"
		client.save()
		frappe.db.commit()

		# Request for bearer token
		token_response = requests.post(
			get_full_url("/api/method/frappe.integrations.oauth2.get_token"),
			headers=self.form_header,
			data=encode_params({
				"grant_type": "password",
				"username": "test@example.com",
				"password": "Eastern_43A1W",
				"client_id":  self.client_id,
				"scope": self.scope
			})
		)

		# Parse bearer token json
		bearer_token = token_response.json()

		# Check token for valid response
		self.assertTrue(check_valid_openid_response(bearer_token.get("access_token")))

	def test_login_using_implicit_token(self):
		oauth_client = frappe.get_doc("OAuth Client", self.client_id)
		oauth_client.grant_type = "Implicit"
		oauth_client.response_type = "Token"
		oauth_client.save()
		frappe.db.commit()

		session = requests.Session()
		login(session)

		redirect_destination = None

		# Go to Authorize url
		try:
			session.get(
				get_full_url("/api/method/frappe.integrations.oauth2.authorize"),
				params=encode_params({
					"client_id": self.client_id,
					"scope": self.scope,
					"response_type": "token",
					"redirect_uri": self.redirect_uri
				})
			)
		except requests.exceptions.ConnectionError as ex:
			redirect_destination = ex.request.url

		response_dict = parse_qs(urlparse(redirect_destination).fragment)

		self.assertTrue(response_dict.get("access_token"))
		self.assertTrue(response_dict.get("expires_in"))
		self.assertTrue(response_dict.get("scope"))
		self.assertTrue(response_dict.get("token_type"))
		self.assertTrue(check_valid_openid_response(response_dict.get("access_token")[0]))

	def test_openid_code_id_token(self):
		client = update_client_for_auth_code_grant(self.client_id)

		session = requests.Session()
		login(session)

		redirect_destination = None

		nonce = frappe.generate_hash()

		# Go to Authorize url
		try:
			session.get(
				get_full_url("/api/method/frappe.integrations.oauth2.authorize"),
				params=encode_params({
					"client_id": self.client_id,
					"scope": self.scope,
					"response_type": "code",
					"redirect_uri": self.redirect_uri,
					"nonce": nonce,
				})
			)
		except requests.exceptions.ConnectionError as ex:
			redirect_destination = ex.request.url

		# Get authorization code from redirected URL
		query = parse_qs(urlparse(redirect_destination).query)
		auth_code = query.get("code")[0]

		# Request for bearer token
		token_response = requests.post(
			get_full_url("/api/method/frappe.integrations.oauth2.get_token"),
			headers=self.form_header,
			data=encode_params({
				"grant_type": "authorization_code",
				"code": auth_code,
				"redirect_uri": self.redirect_uri,
				"client_id": self.client_id,
				"scope": self.scope,
			})
		)

		# Parse bearer token json
		bearer_token = token_response.json()

		id_token = bearer_token.get("id_token")
		payload = jwt.decode(
			id_token,
			audience=client.client_id,
			key=client.client_secret,
			algorithm="HS256",
		)

		self.assertTrue(payload.get("nonce") == nonce)


def check_valid_openid_response(access_token=None):
	"""Return True for valid response."""
	# Use token in header
	headers = {}
	if access_token:
		headers["Authorization"] = "Bearer " + access_token

	# check openid for email test@example.com
	openid_response = requests.get(
		get_full_url("/api/method/frappe.integrations.oauth2.openid_profile"),
		headers=headers
	)

	return openid_response.status_code == 200


def login(session):
	session.post(
		get_full_url("/api/method/login"),
		data={
			"usr": "test@example.com",
			"pwd": "Eastern_43A1W"
		}
	)


def get_full_url(endpoint):
	"""Turn '/endpoint' into 'http://127.0.0.1:8000/endpoint'."""
	return urljoin(frappe.utils.get_url(), endpoint)


def update_client_for_auth_code_grant(client_id):
	client = frappe.get_doc("OAuth Client", client_id)
	client.grant_type = "Authorization Code"
	client.response_type = "Code"
	client.save()
	frappe.db.commit()
	return client
