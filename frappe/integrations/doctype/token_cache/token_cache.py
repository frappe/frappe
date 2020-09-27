# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta
from frappe.model.document import Document

class TokenCache(Document):

	def get_auth_header(self):
		if self.access_token:
			headers = {'Authorization': 'Bearer ' + self.access_token}
			return headers

		raise frappe.exceptions.DoesNotExistError

	def check_validity(self):
		if(self.get('__islocal') or (not self.access_token)):
			raise frappe.exceptions.DoesNotExistError

		if not self.is_expired():
			return self

		return self.refresh_token()

	def refresh_token(self):
		app = frappe.get_doc("Connected App", self.connected_app)
		oauth = app.get_oauth2_session()
		new_token = oauth.refresh_token(
			app.token_uri,
			client_secret=app.get_password('client_secret'),
			token=self.get_json()
		)

		if new_token.get('access_token') and app.revocation_uri:
			# Revoke old token
			requests.post(
				app.revocation_uri,
				data=urlencode({'token': new_token.get('access_token')}),
				headers={
					'Authorization': 'Bearer ' + new_token.get('access_token'),
					'Content-Type': 'application/x-www-form-urlencoded'
				}
			)

		return self.update_data(new_token)

	def update_data(self, data):
		self.access_token = data.get('access_token')
		self.refresh_token = data.get('refresh_token')
		self.expires_in = data.get('expires_in')
		self.token_type = data.get('token_type')

		new_scopes = data.get('scope')
		if new_scopes:
			if isinstance(new_scopes, str):
				new_scopes = new_scopes.split(' ')
			if isinstance(new_scopes, list):
				self.scopes = None
				for scope in new_scopes:
					self.append('scopes', {'scope': scope})

		self.state = None
		self.save()
		frappe.db.commit()
		return self

	def get_expires_in(self):
		expiry_time = self.modified + timedelta(self.expires_in)
		return (datetime.now() - expiry_time).total_seconds()

	def is_expired(self):
		return self.get_expires_in() < 0

	def get_json(self):
		return {
			'access_token': self.get_password('access_token'),
			'refresh_token': self.get_password('refresh_token'),
			'expires_in': self.get_expires_in(),
			'token_type': self.token_type
		}
