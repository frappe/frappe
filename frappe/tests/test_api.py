# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe, os
from frappe.core.doctype.user.user import generate_keys
from frappe.frappeclient import FrappeClient

import requests
import base64

class TestAPI(unittest.TestCase):
	def test_insert_many(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabNote` where title in ('Sing','a','song','of','sixpence')")
		frappe.db.commit()

		server.insert_many([
			{"doctype": "Note", "public": True, "title": "Sing"},
			{"doctype": "Note", "public": True, "title": "a"},
			{"doctype": "Note", "public": True, "title": "song"},
			{"doctype": "Note", "public": True, "title": "of"},
			{"doctype": "Note", "public": True, "title": "sixpence"},
		])

		self.assertTrue(frappe.db.get_value('Note', {'title': 'Sing'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'a'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'song'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'of'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'sixpence'}))

	def test_create_doc(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabNote` where title = 'test_create'")
		frappe.db.commit()

		server.insert({"doctype": "Note", "public": True, "title": "test_create"})

		self.assertTrue(frappe.db.get_value('Note', {'title': 'test_create'}))

	def test_list_docs(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		doc_list = server.get_list("Note")

		self.assertTrue(len(doc_list))

	def test_get_doc(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabNote` where title = 'get_this'")
		frappe.db.commit()

		server.insert_many([
			{"doctype": "Note", "public": True, "title": "get_this"},
		])
		doc = server.get_doc("Note", "get_this")
		self.assertTrue(doc)

	def test_update_doc(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabNote` where title in ('Sing','sing')")
		frappe.db.commit()

		server.insert({"doctype":"Note", "public": True, "title": "Sing"})
		doc = server.get_doc("Note", 'Sing')
		changed_title = "sing"
		doc["title"] = changed_title
		doc = server.update(doc)
		self.assertTrue(doc["title"] == changed_title)

	def test_update_child_doc(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabContact` where first_name = 'George' and last_name = 'Steevens'")
		frappe.db.sql("delete from `tabContact` where first_name = 'William' and last_name = 'Shakespeare'")
		frappe.db.sql("delete from `tabCommunication` where reference_doctype = 'Event'")
		frappe.db.sql("delete from `tabCommunication Link` where link_doctype = 'Contact'")
		frappe.db.sql("delete from `tabEvent` where subject = 'Sing a song of sixpence'")
		frappe.db.sql("delete from `tabEvent Participants` where reference_doctype = 'Contact'")
		frappe.db.commit()

		# create multiple contacts
		server.insert_many([
			{"doctype": "Contact", "first_name": "George", "last_name": "Steevens"},
			{"doctype": "Contact", "first_name": "William", "last_name": "Shakespeare"}
		])

		# create an event with one of the created contacts
		event = server.insert({
			"doctype": "Event",
			"subject": "Sing a song of sixpence",
			"event_participants": [{
				"reference_doctype": "Contact",
				"reference_docname": "George Steevens"
			}]
		})

		# update the event's contact to the second contact
		server.update({
			"doctype": "Event Participants",
			"name": event.get("event_participants")[0].get("name"),
			"reference_docname": "William Shakespeare"
		})

		# the change should run the parent document's validations and
		# create a Communication record with the new contact
		self.assertTrue(frappe.db.exists("Communication Link", {"link_name": "William Shakespeare"}))

	def test_delete_doc(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabNote` where title = 'delete'")
		frappe.db.commit()

		server.insert_many([
			{"doctype": "Note", "public": True, "title": "delete"},
		])
		server.delete("Note", "delete")

		self.assertFalse(frappe.db.get_value('Note', {'title': 'delete'}))

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
