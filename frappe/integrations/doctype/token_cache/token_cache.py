# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TokenCache(Document):

	def get_auth_header(self):
		if self.access_token:
			headers = {'Authorization': 'Bearer ' + self.access_token}
			return headers

		raise frappe.exceptions.DoesNotExistError

	def update_data(self, data):
		self.access_token = data.get('access_token')
		self.refresh_token = data.get('refresh_token')
		self.expires_in = data.get('expires_in')

		existing_scopes = [scope.scope for scope in self.scopes]
		new_scopes = data.get('scope')
		if isinstance(new_scopes, str):
			new_scopes = new_scopes.split(' ')
		scopes = set(existing_scopes) | set(new_scopes)
		self.scopes = None
		for scope in scopes:
			self.append('scopes', {'scope': scope})

		self.state = None
		self.save()

		return self
