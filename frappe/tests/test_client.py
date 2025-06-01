# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors

from unittest.mock import patch

import nts
from nts.tests.utils import ntsTestCase
from nts.utils import get_site_url


class TestClient(ntsTestCase):
	def test_set_value(self):
		todo = nts.get_doc(dict(doctype="ToDo", description="test")).insert()
		nts.set_value("ToDo", todo.name, "description", "test 1")
		self.assertEqual(nts.get_value("ToDo", todo.name, "description"), "test 1")

		nts.set_value("ToDo", todo.name, {"description": "test 2"})
		self.assertEqual(nts.get_value("ToDo", todo.name, "description"), "test 2")

	def test_delete(self):
		from nts.client import delete
		from nts.desk.doctype.note.note import Note

		note = nts.get_doc(
			doctype="Note",
			title=nts.generate_hash(length=8),
			content="test",
			seen_by=[{"user": "Administrator"}],
		).insert()

		child_row_name = note.seen_by[0].name

		with patch.object(Note, "save") as save:
			delete("Note Seen By", child_row_name)
			save.assert_called()

		delete("Note", note.name)

		self.assertFalse(nts.db.exists("Note", note.name))
		self.assertRaises(nts.DoesNotExistError, delete, "Note", note.name)
		self.assertRaises(nts.DoesNotExistError, delete, "Note Seen By", child_row_name)

	def test_http_valid_method_access(self):
		from nts.client import delete
		from nts.handler import execute_cmd

		nts.set_user("Administrator")

		nts.local.request = nts._dict()
		nts.local.request.method = "POST"

		nts.local.form_dict = nts._dict(
			{"doc": dict(doctype="ToDo", description="Valid http method"), "cmd": "nts.client.save"}
		)
		todo = execute_cmd("nts.client.save")

		self.assertEqual(todo.get("description"), "Valid http method")

		delete("ToDo", todo.name)

	def test_http_invalid_method_access(self):
		from nts.handler import execute_cmd

		nts.set_user("Administrator")

		nts.local.request = nts._dict()
		nts.local.request.method = "GET"

		nts.local.form_dict = nts._dict(
			{"doc": dict(doctype="ToDo", description="Invalid http method"), "cmd": "nts.client.save"}
		)

		self.assertRaises(nts.PermissionError, execute_cmd, "nts.client.save")

	def test_run_doc_method(self):
		from nts.handler import execute_cmd

		if not nts.db.exists("Report", "Test Run Doc Method"):
			report = nts.get_doc(
				{
					"doctype": "Report",
					"ref_doctype": "User",
					"report_name": "Test Run Doc Method",
					"report_type": "Query Report",
					"is_standard": "No",
					"roles": [{"role": "System Manager"}],
				}
			).insert()
		else:
			report = nts.get_doc("Report", "Test Run Doc Method")

		nts.local.request = nts._dict()
		nts.local.request.method = "GET"

		# Whitelisted, works as expected
		nts.local.form_dict = nts._dict(
			{
				"dt": report.doctype,
				"dn": report.name,
				"method": "toggle_disable",
				"cmd": "run_doc_method",
				"args": 0,
			}
		)

		execute_cmd(nts.local.form_dict.cmd)

		# Not whitelisted, throws permission error
		nts.local.form_dict = nts._dict(
			{
				"dt": report.doctype,
				"dn": report.name,
				"method": "create_report_py",
				"cmd": "run_doc_method",
				"args": 0,
			}
		)

		self.assertRaises(nts.PermissionError, execute_cmd, nts.local.form_dict.cmd)

	def test_array_values_in_request_args(self):
		import requests

		from nts.auth import CookieManager, LoginManager

		nts.utils.set_request(path="/")
		nts.local.cookie_manager = CookieManager()
		nts.local.login_manager = LoginManager()
		nts.local.login_manager.login_as("Administrator")
		params = {
			"doctype": "DocType",
			"fields": ["name", "modified"],
			"sid": nts.session.sid,
		}
		headers = {
			"accept": "application/json",
			"content-type": "application/json",
		}
		url = get_site_url(nts.local.site)
		url += "/api/method/nts.client.get_list"

		res = requests.post(url, json=params, headers=headers)
		self.assertEqual(res.status_code, 200)
		data = res.json()
		first_item = data["message"][0]
		self.assertTrue("name" in first_item)
		self.assertTrue("modified" in first_item)

	def test_client_get(self):
		from nts.client import get

		todo = nts.get_doc(doctype="ToDo", description="test").insert()
		filters = {"name": todo.name}
		filters_json = nts.as_json(filters)

		self.assertEqual(get("ToDo", filters=filters).description, "test")
		self.assertEqual(get("ToDo", filters=filters_json).description, "test")
		self.assertEqual(get("System Settings", "", "").doctype, "System Settings")
		self.assertEqual(get("ToDo", filters={}), get("ToDo", filters="{}"))
		todo.delete()

	def test_client_validatate_link(self):
		from nts.client import validate_link

		# Basic test
		self.assertTrue(validate_link("User", "Guest"))

		# fixes capitalization
		if nts.db.db_type == "mariadb":
			self.assertEqual(validate_link("User", "GueSt"), {"name": "Guest"})

		# Fetch
		self.assertEqual(validate_link("User", "Guest", fields=["enabled"]), {"name": "Guest", "enabled": 1})

		# Permissions
		with self.set_user("Guest"), self.assertRaises(nts.PermissionError):
			self.assertEqual(
				validate_link("User", "Guest", fields=["enabled"]), {"name": "Guest", "enabled": 1}
			)

	def test_client_insert(self):
		from nts.client import insert

		def get_random_title():
			return f"test-{nts.generate_hash()}"

		# test insert dict
		doc = {"doctype": "Note", "title": get_random_title(), "content": "test"}
		note1 = insert(doc)
		self.assertTrue(note1)

		# test insert json
		doc["title"] = get_random_title()
		json_doc = nts.as_json(doc)
		note2 = insert(json_doc)
		self.assertTrue(note2)

		# test insert child doc without parent fields
		child_doc = {"doctype": "Note Seen By", "user": "Administrator"}
		with self.assertRaises(nts.ValidationError):
			insert(child_doc)

		# test insert child doc with parent fields
		child_doc = {
			"doctype": "Note Seen By",
			"user": "Administrator",
			"parenttype": "Note",
			"parent": note1.name,
			"parentfield": "seen_by",
		}
		note3 = insert(child_doc)
		self.assertTrue(note3)

		# cleanup
		nts.delete_doc("Note", note1.name)
		nts.delete_doc("Note", note2.name)

	def test_client_insert_many(self):
		from nts.client import insert, insert_many

		def get_random_title():
			return f"test-{nts.generate_hash(length=5)}"

		# insert a (parent) doc
		note1 = {"doctype": "Note", "title": get_random_title(), "content": "test"}
		note1 = insert(note1)

		doc_list = [
			{
				"doctype": "Note Seen By",
				"user": "Administrator",
				"parenttype": "Note",
				"parent": note1.name,
				"parentfield": "seen_by",
			},
			{
				"doctype": "Note Seen By",
				"user": "Administrator",
				"parenttype": "Note",
				"parent": note1.name,
				"parentfield": "seen_by",
			},
			{
				"doctype": "Note Seen By",
				"user": "Administrator",
				"parenttype": "Note",
				"parent": note1.name,
				"parentfield": "seen_by",
			},
			{"doctype": "Note", "title": "not-a-random-title", "content": "test"},
			{"doctype": "Note", "title": get_random_title(), "content": "test"},
			{"doctype": "Note", "title": get_random_title(), "content": "test"},
			{"doctype": "Note", "title": "another-note-title", "content": "test"},
		]

		# insert all docs
		docs = insert_many(doc_list)

		self.assertEqual(len(docs), 7)
		self.assertEqual(nts.db.get_value("Note", docs[3], "title"), "not-a-random-title")
		self.assertEqual(nts.db.get_value("Note", docs[6], "title"), "another-note-title")
		self.assertIn(note1.name, docs)

		# cleanup
		for doc in docs:
			nts.delete_doc("Note", doc)
