# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
from frappe.integrations.doctype.social_login_key.social_login_key import BaseUrlNotSetError
import unittest

class TestSocialLoginKey(unittest.TestCase):
	def test_adding_frappe_social_login_provider(self):
		provider_name = "Frappe"
		social_login_key = make_social_login_key(
			social_login_provider=provider_name
		)
		social_login_key.get_social_login_provider(provider_name, initialize=True)
		self.assertRaises(BaseUrlNotSetError, social_login_key.insert)

def make_social_login_key(**kwargs):
	kwargs["doctype"] = "Social Login Key"
	if not "provider_name" in kwargs:
		kwargs["provider_name"] = "Test OAuth2 Provider"
	doc = frappe.get_doc(kwargs)
	return doc

def create_or_update_social_login_key():
	# used in other tests (connected app, oauth20)
	try:
		social_login_key = frappe.get_doc("Social Login Key", "frappe")
	except frappe.DoesNotExistError:
		social_login_key = frappe.new_doc("Social Login Key")
	social_login_key.get_social_login_provider("Frappe", initialize=True)
	social_login_key.base_url = frappe.utils.get_url()
	social_login_key.enable_social_login = 0
	social_login_key.save()
	frappe.db.commit()

	return social_login_key
