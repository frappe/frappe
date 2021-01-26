# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# See license.txt
from __future__ import unicode_literals

import unittest
import frappe

test_dependencies = ['User', 'Connected App', 'Token Cache']

class TestTokenCache(unittest.TestCase):

	def setUp(self):
		self.token_cache = frappe.get_last_doc('Token Cache')
		self.token_cache.update({'connected_app': frappe.get_last_doc('Connected App').name})
		self.token_cache.save()

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
