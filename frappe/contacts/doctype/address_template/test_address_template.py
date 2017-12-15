# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe, unittest

class TestAddressTemplate(unittest.TestCase):
	def setUp(self):
		self.make_default_address_template()

	def test_default_is_unset(self):
		a = frappe.get_doc("Address Template", "India")
		a.is_default = 1
		a.save()

		b = frappe.get_doc("Address Template", "Brazil")
		b.is_default = 1
		b.save()

		self.assertEqual(frappe.db.get_value("Address Template", "India", "is_default"), 0)

	def tearDown(self):
		a = frappe.get_doc("Address Template", "India")
		a.is_default = 1
		a.save()

	@classmethod
	def make_default_address_template(self):
		template = """{{ address_line1 }}<br>{% if address_line2 %}{{ address_line2 }}<br>{% endif -%}{{ city }}<br>{% if state %}{{ state }}<br>{% endif -%}{% if pincode %}{{ pincode }}<br>{% endif -%}{{ country }}<br>{% if phone %}Phone: {{ phone }}<br>{% endif -%}{% if fax %}Fax: {{ fax }}<br>{% endif -%}{% if email_id %}Email: {{ email_id }}<br>{% endif -%}"""

		if not frappe.db.exists('Address Template', 'India'):
			frappe.get_doc({
				"doctype": "Address Template",
				"country": 'India',
				"is_default": 1,
				"template": template
			}).insert()

		if not frappe.db.exists('Address Template', 'Brazil'):
			frappe.get_doc({
				"doctype": "Address Template",
				"country": 'Brazil',
				"template": template
			}).insert()		