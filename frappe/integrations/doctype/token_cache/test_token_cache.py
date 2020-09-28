# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# See license.txt
from __future__ import unicode_literals

import unittest
import frappe

test_dependencies = ['User', 'Connected App', 'Token Cache']

class TestTokenCache(unittest.TestCase):

	def setup(self):
		token_cache_list = frappe.get_list('Token Cache')
		connected_app_list = frappe.get_list('Connected App')
		self.token_cache = frappe.get_doc('Token Cache', token_cache_list[0].name)
		self.token_cache.update({'connected_app': connected_app_list[0].name})

	def test_get_auth_header(self):
		self.token_cache.get_auth_header()

	def test_update_data(self):
		self.token_cache.update_data({
			'access_token': 'new-access-token',
			'refresh_token': 'new-refresh-token',
			'token_type': 'bearer',
			'expires_in': 2000,
			'scope': 'new scope'
		})

	def test_get_expires_in(self):
		self.token_cache.get_expires_in()

	def test_is_expired(self):
		self.token_cache.is_expired()

	def get_json(self):
		self.token_cache.get_json()
