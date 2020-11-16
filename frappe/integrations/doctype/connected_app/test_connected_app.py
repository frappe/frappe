# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# See license.txt
from __future__ import unicode_literals

import unittest
import requests
from urllib.parse import urljoin

import frappe
from frappe.integrations.doctype.social_login_key.test_social_login_key import create_or_update_social_login_key

test_dependencies = ['Connected App', 'OAuth Client', 'User']

class TestConnectedApp(unittest.TestCase):

	def setUp(self):
		"""Set up a Connected App that connects to our own oAuth provider.

		Frappe comes with it's own oAuth2 provider that we can test against. The
		client credentials can be obtained from an "OAuth Client". All depends
		on "Social Login Key" so we create one as well.

		The redirect URIs from "Connected App" and "OAuth Client" have to match.
		Frappe's "Authorization URL" and "Access Token URL" (actually they're
		just endpoints) are stored in "Social Login Key" so we get them from
		there.
		"""
		self.user_name = 'test@example.com'
		self.user_password = 'Eastern_43A1W'

		connected_app = frappe.get_last_doc('Connected App')
		redirect_uri = connected_app.get('redirect_uri')

		web_application_client = frappe.get_last_doc('OAuth Client')
		web_application_client.update({
			'redirect_uris': redirect_uri,
			'default_redirect_uri': redirect_uri
		})
		web_application_client.save()

		social_login_key = create_or_update_social_login_key()
		self.base_url = social_login_key.get('base_url')

		connected_app.authorization_uri = urljoin(self.base_url, social_login_key.get('authorize_url'))
		connected_app.token_uri = urljoin(self.base_url, social_login_key.get('access_token_url'))
		connected_app.client_id = web_application_client.get('client_id')
		connected_app.client_secret = web_application_client.get('client_secret')
		self.connected_app = connected_app.save()

		frappe.db.commit()

	def test_web_application_flow(self):
		"""Simulate a logged in user who opens the authorization URL."""
		session = requests.Session()
		session.post(urljoin(self.base_url, '/api/method/login'), data={
			'usr': self.user_name,
			'pwd': self.user_password
		})
		authorization_url = self.connected_app.initiate_web_application_flow(user=self.user_name)

		auth_response = session.get(authorization_url)
		self.assertEqual(auth_response.status_code, 200)

		callback_response = session.get(auth_response.url)
		self.assertEqual(callback_response.status_code, 200)

		token_cache = self.connected_app.get_token_cache(self.user_name)
		token = token_cache.get_password('access_token')
		self.assertNotEqual(token, None)

		oauth2_session = self.connected_app.get_oauth2_session(self.user_name)
		resp = oauth2_session.get(urljoin(self.base_url, '/api/method/frappe.auth.get_logged_user'))
		self.assertEqual(resp.json().get('message'), self.user_name)
