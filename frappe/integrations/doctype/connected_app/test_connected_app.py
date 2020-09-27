# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# See license.txt
from __future__ import unicode_literals

import unittest
import requests
import frappe
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin, urlparse, parse_qs
from frappe.test_runner import make_test_records
from frappe.integrations.doctype.social_login_key.test_social_login_key import create_or_update_social_login_key
from .connected_app import callback

test_dependencies = ['OAuth Client', 'User', 'Connected App']

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
		connected_app = frappe.get_doc('Connected App', 'frappe')
		social_login_key = create_or_update_social_login_key()
		self.base_url = social_login_key.get('base_url')

		oauth_client_name = frappe.get_all('OAuth Client', fields=['name'])[0]
		oauth_client = frappe.get_doc('OAuth Client', oauth_client_name['name'])
		oauth_client.redirect_uris = connected_app.get('redirect_uri')
		oauth_client.default_redirect_uri = connected_app.get('redirect_uri')
		oauth_client.save()
		frappe.db.commit()

		connected_app.client_id = oauth_client.get('client_id')
		connected_app.client_secret = oauth_client.get('client_secret')
		connected_app.authorization_uri = urljoin(self.base_url, social_login_key.get('authorize_url'))
		connected_app.token_uri = urljoin(self.base_url, social_login_key.get('access_token_url'))
		self.app = connected_app.save()
		self.user_name = 'test@example.com'
		self.user_password = 'Eastern_43A1W'

	def test_web_application_flow(self):
		"""Simulate a logged in user who opens the authorization URL."""
		session = requests.Session()
		session.post(urljoin(self.base_url, '/api/method/login'), data={
			'usr': self.user_name,
			'pwd': self.user_password
		})
		authorization_url = self.app.initiate_web_application_flow(user=self.user_name)

		auth_response = session.get(authorization_url)
		self.assertEqual(auth_response.status_code, 200)

		callback_response = session.get(auth_response.url)
		self.assertEqual(callback_response.status_code, 200)

		token_cache = frappe.get_doc('Token Cache', self.app.name + '-' + self.user_name)
		token = token_cache.get_password('access_token')
		self.assertNotEqual(token, None)
