# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient
from urllib.parse import urljoin

if frappe.conf.developer_mode:
	# Disable mandatory TLS in developer mode
	import os
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class ConnectedApp(Document):
	"""Connect to a remote oAuth Server. Retrieve and store user's access token
	in a Token Cache.
	"""

	def validate(self):
		try:
			base_url = frappe.request.host_url
		except RuntimeError:
			# for tests
			base_url = frappe.get_site_config().host_name or 'http://localhost:8000'

		callback_path = '/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/' + self.name
		self.redirect_uri = urljoin(base_url, callback_path)

	def get_oauth2_session(self, user=None):
		token = None
		token_updater = None
		if user:
			token_cache = self.get_user_token(user)
			token = token_cache.get_json()
			token_updater = token_cache.update_data

		return OAuth2Session(
			client_id=self.client_id,
			token=token,
			token_updater=token_updater,
			auto_refresh_url=self.token_uri,
			redirect_uri=self.redirect_uri,
			scope=self.get_scopes()
		)

	def initiate_web_application_flow(self, user=None, success_uri=None):
		"""Return an authorization URL for the user. Save state in Token Cache."""
		success_uri = success_uri or '/desk'
		user = user or frappe.session.user
		oauth = self.get_oauth2_session()
		authorization_url, state = oauth.authorization_url(self.authorization_uri)

		try:
			token = self.get_stored_user_token(user)
		except frappe.exceptions.DoesNotExistError:
			token = frappe.new_doc('Token Cache')
			token.user = user
			token.connected_app = self.name

		token.success_uri = success_uri
		token.state = state
		token.save()
		frappe.db.commit()

		return authorization_url

	def get_user_token(self, user=None, success_uri=None):
		"""Return an existing user token or initiate a Web Application Flow."""
		user = user or frappe.session.user

		try:
			token = self.get_stored_user_token(user)
		except frappe.exceptions.DoesNotExistError:
			redirect = self.initiate_web_application_flow(user, success_uri)
			frappe.local.response['type'] = 'redirect'
			frappe.local.response['location'] = redirect
			return redirect

		return token

	def get_stored_user_token(self, user):
		return frappe.get_doc('Token Cache', self.name + '-' + user)

	def get_scopes(self):
		return [row.scope for row in self.scopes]


@frappe.whitelist(allow_guest=True)
def callback(code=None, state=None):
	"""Handle client's code.

	Called during the oauthorization flow by the remote oAuth2 server to
	transmit a code that can be used by the local server to obtain an access
	token.
	"""
	if frappe.request.method != 'GET':
		frappe.throw(_('Invalid Method'))

	if frappe.session.user == 'Guest':
		frappe.throw(_('Log in to access this page.'), frappe.PermissionError)

	path = frappe.request.path[1:].split('/')
	if len(path) != 4 or not path[3]:
		frappe.throw(_('Invalid Parameter(s)'))

	connected_app = path[3]
	token_cache = frappe.get_doc('Token Cache', connected_app + '-' + frappe.session.user)
	if not token_cache:
		frappe.throw(_('State Not Found'))

	if state != token_cache.state:
		frappe.throw(_('Invalid State'))

	try:
		app = frappe.get_doc('Connected App', connected_app)
	except frappe.exceptions.DoesNotExistError:
		frappe.throw(_('Invalid App'))

	oauth = app.get_oauth2_session()
	token = oauth.fetch_token(app.token_uri,
		code=code,
		client_secret=app.get_password('client_secret'),
		include_client_id=True
	)
	token_cache.update_data(token)

	frappe.local.response['type'] = 'redirect'
	frappe.local.response['location'] = token_cache.get('success_uri') or '/desk'
