# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe, os
from frappe.utils import get_url
from frappe.core.doctype.user.user import generate_keys

import requests
import base64


class TestAPI(unittest.TestCase):
	def test_insert_many(self):
		if os.environ.get('CI'):
			return
		from frappe.frappeclient import FrappeClient

		frappe.db.sql("DELETE FROM `tabToDo` WHERE `description` LIKE 'Test API%'")
		frappe.db.commit()

		server = FrappeClient(get_url(), "Administrator", "admin", verify=False)

		server.insert_many([
			{"doctype": "ToDo", "description": "Test API 1"},
			{"doctype": "ToDo", "description": "Test API 2"},
			{"doctype": "ToDo", "description": "Test API 3"},
		])

		self.assertTrue(frappe.db.get_value('ToDo', {'description': 'Test API 1'}))
		self.assertTrue(frappe.db.get_value('ToDo', {'description': 'Test API 2'}))
		self.assertTrue(frappe.db.get_value('ToDo', {'description': 'Test API 3'}))

	def test_auth_via_api_key_secret(self):

		# generate api ke and api secret for administrator
		keys = generate_keys("Administrator")
		frappe.db.commit()
		generated_secret = frappe.utils.password.get_decrypted_password(
			"User", "Administrator", fieldname='api_secret'
		)

		api_key = frappe.db.get_value("User", "Administrator", "api_key")
		header = {"Authorization": "token {}:{}".format(api_key, generated_secret)}
		res = requests.post(frappe.get_site_config().host_name + "/api/method/frappe.auth.get_logged_user", headers=header)

		self.assertEqual(res.status_code, 200)
		self.assertEqual("Administrator", res.json()["message"])
		self.assertEqual(keys['api_secret'], generated_secret)

		header = {"Authorization": "Basic {}".format(base64.b64encode(frappe.safe_encode("{}:{}".format(api_key, generated_secret))).decode())}
		res = requests.post(frappe.get_site_config().host_name + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 200)
		self.assertEqual("Administrator", res.json()["message"])

		# Valid api key, invalid api secret
		api_secret = "ksk&93nxoe3os"
		header = {"Authorization": "token {}:{}".format(api_key, api_secret)}
		res = requests.post(frappe.get_site_config().host_name + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 403)


		# random api key and api secret
		api_key = "@3djdk3kld"
		api_secret = "ksk&93nxoe3os"
		header = {"Authorization": "token {}:{}".format(api_key, api_secret)}
		res = requests.post(frappe.get_site_config().host_name + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 401)