# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import requests
from frappe.utils import get_site_url
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map

class TestServerScript(unittest.TestCase):
	def setUp(self):
		frappe.cache().delete_value('server_script_map')

	def test_doctype_event(self):
		script = get_server_script()
		script.script_type = 'DocType Event'
		script.script = 'frappe.flags._ping = True'
		script.reference_doctype = 'ToDo'
		script.doctype_event = 'Before Save'
		script.save()
		frappe.db.commit()

		frappe.flags._ping = False
		frappe.get_doc(dict(doctype='ToDo', description='test todo')).insert()
		self.assertTrue(frappe.flags._ping)

	def test_api(self):
		script = get_server_script()
		script.script_type = 'API'
		script.api_method = 'test_server_script'
		script.allow_guest = 1
		script.script = 'frappe.response["message"] = "hello"'
		script.save()
		frappe.db.commit()

		response = requests.post(get_site_url(frappe.local.site) + "/api/method/test_server_script")
		self.assertEqual(response.status_code, 200)
		self.assertEqual("hello", response.json()["message"])


def get_server_script():
	if frappe.db.exists('Server Script', 'Test Server Script'):
		return frappe.get_doc('Server Script', 'Test Server Script')
	else:
		script = frappe.get_doc(dict(
			doctype = 'Server Script',
			name = 'Test Server Script',
			script = '# nothing',
			script_type = 'DocType Event'
		)).insert()

		return script
