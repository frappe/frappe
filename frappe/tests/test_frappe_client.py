# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import unittest

import requests

import frappe
from frappe.core.doctype.user.user import generate_keys
from frappe.frappeclient import AuthError, FrappeClient, FrappeException
from frappe.utils.data import get_url


class TestFrappeClient(unittest.TestCase):
	PASSWORD = frappe.conf.admin_password or "admin"

	@classmethod
	def setUpClass(cls) -> None:
		site_url = get_url()
		try:
			FrappeClient(site_url, "Administrator", cls.PASSWORD, verify=False)
		except AuthError:
			raise unittest.SkipTest(
				f"AuthError raised for {site_url} [usr=Administrator, pwd={cls.PASSWORD}]"
			)

		return super().setUpClass()

	def test_insert_many(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		frappe.db.delete("Note", {"title": ("in", ("Sing", "a", "song", "of", "sixpence"))})
		frappe.db.commit()

		server.insert_many(
			[
				{"doctype": "Note", "public": True, "title": "Sing"},
				{"doctype": "Note", "public": True, "title": "a"},
				{"doctype": "Note", "public": True, "title": "song"},
				{"doctype": "Note", "public": True, "title": "of"},
				{"doctype": "Note", "public": True, "title": "sixpence"},
			]
		)

		self.assertTrue(frappe.db.get_value("Note", {"title": "Sing"}))
		self.assertTrue(frappe.db.get_value("Note", {"title": "a"}))
		self.assertTrue(frappe.db.get_value("Note", {"title": "song"}))
		self.assertTrue(frappe.db.get_value("Note", {"title": "of"}))
		self.assertTrue(frappe.db.get_value("Note", {"title": "sixpence"}))

	def test_create_doc(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		frappe.db.delete("Note", {"title": "test_create"})
		frappe.db.commit()

		server.insert({"doctype": "Note", "public": True, "title": "test_create"})

		self.assertTrue(frappe.db.get_value("Note", {"title": "test_create"}))

	def test_list_docs(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		doc_list = server.get_list("Note")

		self.assertTrue(len(doc_list))

	def test_get_doc(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		frappe.db.delete("Note", {"title": "get_this"})
		frappe.db.commit()

		server.insert_many(
			[
				{"doctype": "Note", "public": True, "title": "get_this"},
			]
		)
		doc = server.get_doc("Note", "get_this")
		self.assertTrue(doc)

	def test_get_value(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		frappe.db.delete("Note", {"title": "get_value"})
		frappe.db.commit()

		test_content = "test get value"

		server.insert_many(
			[
				{"doctype": "Note", "public": True, "title": "get_value", "content": test_content},
			]
		)
		self.assertEqual(
			server.get_value("Note", "content", {"title": "get_value"}).get("content"), test_content
		)
		name = server.get_value("Note", "name", {"title": "get_value"}).get("name")

		# test by name
		self.assertEqual(server.get_value("Note", "content", name).get("content"), test_content)

		self.assertRaises(
			FrappeException,
			server.get_value,
			"Note",
			"(select (password) from(__Auth) order by name desc limit 1)",
			{"title": "get_value"},
		)

	def test_get_single(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		server.set_value("Website Settings", "Website Settings", "title_prefix", "test-prefix")
		self.assertEqual(
			server.get_value("Website Settings", "title_prefix", "Website Settings").get("title_prefix"),
			"test-prefix",
		)
		self.assertEqual(
			server.get_value("Website Settings", "title_prefix").get("title_prefix"), "test-prefix"
		)
		frappe.db.set_value("Website Settings", None, "title_prefix", "")

	def test_update_doc(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		frappe.db.delete("Note", {"title": ("in", ("Sing", "sing"))})
		frappe.db.commit()

		server.insert({"doctype": "Note", "public": True, "title": "Sing"})
		doc = server.get_doc("Note", "Sing")
		changed_title = "sing"
		doc["title"] = changed_title
		doc = server.update(doc)
		self.assertTrue(doc["title"] == changed_title)

	def test_update_child_doc(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		frappe.db.delete("Contact", {"first_name": "George", "last_name": "Steevens"})
		frappe.db.delete("Contact", {"first_name": "William", "last_name": "Shakespeare"})
		frappe.db.delete("Communication", {"reference_doctype": "Event"})
		frappe.db.delete("Communication Link", {"link_doctype": "Contact"})
		frappe.db.delete("Event", {"subject": "Sing a song of sixpence"})
		frappe.db.delete("Event Participants", {"reference_doctype": "Contact"})
		frappe.db.commit()

		# create multiple contacts
		server.insert_many(
			[
				{"doctype": "Contact", "first_name": "George", "last_name": "Steevens"},
				{"doctype": "Contact", "first_name": "William", "last_name": "Shakespeare"},
			]
		)

		# create an event with one of the created contacts
		event = server.insert(
			{
				"doctype": "Event",
				"subject": "Sing a song of sixpence",
				"event_participants": [
					{"reference_doctype": "Contact", "reference_docname": "George Steevens"}
				],
			}
		)

		# update the event's contact to the second contact
		server.update(
			{
				"doctype": "Event Participants",
				"name": event.get("event_participants")[0].get("name"),
				"reference_docname": "William Shakespeare",
			}
		)

		# the change should run the parent document's validations and
		# create a Communication record with the new contact
		self.assertTrue(frappe.db.exists("Communication Link", {"link_name": "William Shakespeare"}))

	def test_delete_doc(self):
		server = FrappeClient(get_url(), "Administrator", self.PASSWORD, verify=False)
		frappe.db.delete("Note", {"title": "delete"})
		frappe.db.commit()

		server.insert_many(
			[
				{"doctype": "Note", "public": True, "title": "delete"},
			]
		)
		server.delete("Note", "delete")

		self.assertFalse(frappe.db.get_value("Note", {"title": "delete"}))

	def test_auth_via_api_key_secret(self):
		# generate API key and API secret for administrator
		keys = generate_keys("Administrator")
		frappe.db.commit()
		generated_secret = frappe.utils.password.get_decrypted_password(
			"User", "Administrator", fieldname="api_secret"
		)

		api_key = frappe.db.get_value("User", "Administrator", "api_key")
		header = {"Authorization": f"token {api_key}:{generated_secret}"}
		res = requests.post(get_url() + "/api/method/frappe.auth.get_logged_user", headers=header)

		self.assertEqual(res.status_code, 200)
		self.assertEqual("Administrator", res.json()["message"])
		self.assertEqual(keys["api_secret"], generated_secret)

		header = {
			"Authorization": "Basic {}".format(
				base64.b64encode(frappe.safe_encode(f"{api_key}:{generated_secret}")).decode()
			)
		}
		res = requests.post(get_url() + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 200)
		self.assertEqual("Administrator", res.json()["message"])

		# Valid api key, invalid api secret
		api_secret = "ksk&93nxoe3os"
		header = {"Authorization": f"token {api_key}:{api_secret}"}
		res = requests.post(get_url() + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 401)

		# random api key and api secret
		api_key = "@3djdk3kld"
		api_secret = "ksk&93nxoe3os"
		header = {"Authorization": f"token {api_key}:{api_secret}"}
		res = requests.post(get_url() + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 401)
