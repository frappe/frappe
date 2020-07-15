# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import requests
import frappe
from frappe import _
from frappe.model.document import Document
from datetime import datetime, timedelta
from urllib.parse import urlencode
from requests_oauthlib import OAuth2Session

if frappe.conf.developer_mode:
	# Disable mandatory TLS in developer mode
	import os
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class ConnectedApp(Document):

	def autoname(self):
		self.callback = frappe.scrub(self.provider_name)

	def validate(self):
		callback_path = 'api/method/frappe.integrations.doctype.connected_app.connected_app.callback/'
		self.redirect_uri = frappe.request.host_url + callback_path + self.callback

	def get_oauth2_session(self):
		return OAuth2Session(
			self.client_id,
			redirect_uri=self.redirect_uri,
			scope=[scope.scope for scope in self.scopes]
		)

	def get_client_token(self):
		try:
			token = self.get_stored_client_token()
		except frappe.exceptions.DoesNotExistError:
			token = self.retrieve_client_token()

		token = self.check_validity(token)
		return token

	def get_params(self, **kwargs):
		return {
			'client_id': self.client_id,
			'redirect_uri': self.redirect_uri,
			'scope': self.scope
		}.update(kwargs)

	def retrieve_client_token(self):
		client_secret = self.get_password('client_secret')
		data = self.get_params(grant_type='client_credentials', client_secret=client_secret)
		response = requests.post(
			self.token_endpoint,
			data=urlencode(data),
			headers={'Content-Type': 'application/x-www-form-urlencoded'}
		)
		token = response.json()
		return self.update_stored_client_token(token)

	def check_validity(self, token):
		if(token.get('__islocal') or (not token.access_token)):
			raise frappe.exceptions.DoesNotExistError

		expiry = token.modified + timedelta(seconds=token.expires_in)
		if expiry > datetime.now():
			return token

		return self.refresh_token(token)

	def initiate_auth_code_flow(self, user=None, redirect_to=None):
		redirect_to = redirect_to or '/desk'
		user = user or frappe.session.user
		oauth = self.get_oauth2_session()
		authorization_url, state = oauth.authorization_url(self.authorization_endpoint)

		try:
			token = self.get_stored_user_token(user)
		except frappe.exceptions.DoesNotExistError:
			token = frappe.new_doc('Token Cache')
			token.user = user
			token.connected_app = self.name

		token.state = state
		token.save()
		frappe.db.commit()

		return authorization_url

	def get_user_token(self, user=None, redirect_to=None):
		redirect_to = redirect_to or '/desk'
		user = user or frappe.session.user

		try:
			token = self.get_stored_user_token(user)
			token = self.check_validity(token)
		except frappe.exceptions.DoesNotExistError:
			redirect = self.initiate_auth_code_flow(user, redirect_to)
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = redirect
			return redirect

		return token

	def refresh_token(self, token):
		data = self.get_params(grant_type='refresh_token', refresh_token=token.refresh_token)
		headers = {'Content-Type': 'application/x-www-form-urlencoded'}
		response = requests.post(self.token_endpoint, data=urlencode(data), headers=headers)
		new_token = response.json()

		# Revoke old token
		data = urlencode({'token': token.get('access_token')})
		headers['Authorization'] = 'Bearer ' + new_token.get('access_token')
		requests.post(self.revocation_endpoint, data=data, headers=headers)

		return self.update_stored_client_token(new_token)

	def get_stored_client_token(self):
		return frappe.get_doc('Token Cache', self.name + '-user')

	def get_stored_user_token(self, user):
		return frappe.get_doc('Token Cache', self.name + '-' + user)

	def update_stored_client_token(self, token_data):
		try:
			stored_token = self.get_stored_client_token()
		except frappe.exceptions.DoesNotExistError:
			stored_token = frappe.new_doc('Token Cache')

		stored_token.connected_app = self.name
		stored_token.access_token = token_data.get('access_token')
		stored_token.refresh_token = token_data.get('refresh_token')
		stored_token.expires_in = token_data.get('expires_in')
		stored_token.save(ignore_permissions=True)
		frappe.db.commit()

		return frappe.get_doc('Token Cache', stored_token.name)


@frappe.whitelist(allow_guest=True)
def callback(code=None, state=None):
	"""Handle client's code."""
	if frappe.request.method != 'GET':
		frappe.throw(_('Invalid Method'))

	if frappe.session.user == 'Guest':
		frappe.throw(_("Log in to access this page."), frappe.PermissionError)

	path = frappe.request.path[1:].split("/")
	if len(path) == 4 and path[3]:
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

		client_secret = app.get_password('client_secret')
		oauth = app.get_oauth2_session()
		token = oauth.fetch_token(
			app.token_endpoint,
			code=code,
			client_secret=client_secret
		)

		token_cache.access_token = token.get('access_token')
		token_cache.refresh_token = token.get('refresh_token')
		token_cache.expires_in = token.get('expires_in')

		scopes = token.get('scope')
		if isinstance(scopes, str):
			scopes = [scopes]
		for scope in scopes:
			token_cache.append('scopes', {'scope': scope})

		token_cache.state = None
		token_cache.save()
		frappe.db.commit()

		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = '/desk'
	else:
		frappe.throw(_('Invalid Parameter(s)'))
