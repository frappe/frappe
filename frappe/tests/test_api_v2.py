import typing
from random import choice

import requests

import frappe
from frappe.installer import update_site_config
from frappe.tests.test_api import FrappeAPITestCase, suppress_stdout
from frappe.tests.utils import toggle_test_mode, whitelist_for_tests

authorization_token = None


resource_key = {
	"": "resource",
	"v1": "resource",
	"v2": "document",
}


class TestResourceAPIV2(FrappeAPITestCase):
	version = "v2"
	DOCTYPE = "ToDo"
	GENERATED_DOCUMENTS: typing.ClassVar[list] = []

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for _ in range(20):
			doc = frappe.get_doc({"doctype": "ToDo", "description": frappe.mock("paragraph")}).insert()
			cls.GENERATED_DOCUMENTS = []
			cls.GENERATED_DOCUMENTS.append(doc.name)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.commit()
		for name in cls.GENERATED_DOCUMENTS:
			frappe.delete_doc_if_exists(cls.DOCTYPE, name)
		frappe.db.commit()

	def test_unauthorized_call(self):
		# test 1: fetch documents without auth
		response = requests.get(self.resource(self.DOCTYPE))
		self.assertEqual(response.status_code, 403)

	def test_get_list(self):
		# test 2: fetch documents without params
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIn("data", response.json)

	def test_get_list_limit(self):
		# test 3: fetch data with limit
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "limit": 2})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json["data"]), 2)

	def test_get_list_dict(self):
		# test 4: fetch response as (not) dict
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "as_dict": True})
		json = frappe._dict(response.json)
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json.data, list)
		self.assertIsInstance(json.data[0], dict)

		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "as_dict": False})
		json = frappe._dict(response.json)
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json.data, list)
		self.assertIsInstance(json.data[0], list)

	def test_get_list_fields(self):
		# test 6: fetch response with fields
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "fields": '["description"]'})
		self.assertEqual(response.status_code, 200)
		json = frappe._dict(response.json)
		self.assertIn("description", json.data[0])

	def test_create_document(self):
		data = {"description": frappe.mock("paragraph"), "sid": self.sid}
		response = self.post(self.resource(self.DOCTYPE), data)
		self.assertEqual(response.status_code, 200)
		docname = response.json["data"]["name"]
		self.assertIsInstance(docname, str)
		self.GENERATED_DOCUMENTS.append(docname)

	def test_copy_document(self):
		doc = frappe.get_doc(self.DOCTYPE, self.GENERATED_DOCUMENTS[0])

		# disabled temporarily to assert that `docstatus` is not copied outside of tests
		toggle_test_mode(False)
		try:
			response = self.get(self.resource(self.DOCTYPE, doc.name, "copy"))
		finally:
			toggle_test_mode(True)

		self.assertEqual(response.status_code, 200)
		data = response.json["data"]

		self.assertEqual(data["doctype"], self.DOCTYPE)
		self.assertEqual(data["description"], doc.description)
		self.assertEqual(data["status"], doc.status)
		self.assertEqual(data["priority"], doc.priority)

		self.assertNotIn("name", data)
		self.assertNotIn("creation", data)
		self.assertNotIn("modified", data)
		self.assertNotIn("modified_by", data)
		self.assertNotIn("owner", data)
		self.assertNotIn("docstatus", data)

	def test_delete_document(self):
		doc_to_delete = choice(self.GENERATED_DOCUMENTS)
		response = self.delete(self.resource(self.DOCTYPE, doc_to_delete), data={"sid": self.sid})
		self.assertEqual(response.status_code, 202)
		self.assertDictEqual(response.json, {"data": "ok"})

		response = self.get(self.resource(self.DOCTYPE, doc_to_delete))
		self.assertEqual(response.status_code, 404)
		self.GENERATED_DOCUMENTS.remove(doc_to_delete)

	def test_execute_doc_method(self):
		response = self.get(self.resource("Website Theme", "Standard", "method", "get_apps"))
		self.assertEqual(response.json["data"][0]["name"], "frappe")

	def test_update_document(self):
		generated_desc = frappe.mock("paragraph")
		data = {"description": generated_desc, "sid": self.sid}
		random_doc = choice(self.GENERATED_DOCUMENTS)

		response = self.patch(self.resource(self.DOCTYPE, random_doc), data=data)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["description"], generated_desc)

		response = self.get(self.resource(self.DOCTYPE, random_doc))
		self.assertEqual(response.json["data"]["description"], generated_desc)

	def test_delete_document_non_existing(self):
		non_existent_doc = frappe.generate_hash(length=12)
		with suppress_stdout():
			response = self.delete(self.resource(self.DOCTYPE, non_existent_doc))
		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.json["errors"][0]["type"], "DoesNotExistError")
		# 404s dont return exceptions
		self.assertFalse(response.json["errors"][0].get("exception"))


class TestMethodAPIV2(FrappeAPITestCase):
	version = "v2"

	def setUp(self) -> None:
		self.post(self.method("login"), {"sid": self.sid})
		return super().setUp()

	def test_ping(self):
		response = self.get(self.method("ping"))
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertEqual(response.json["data"], "pong")

	def test_get_user_info(self):
		# server-to-server only
		response = self.get(self.method("frappe.realtime.get_user_info"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json.get("data"), {})

	def test_auth_cycle(self):
		global authorization_token

		generate_admin_keys()
		user = frappe.get_doc("User", "Administrator")
		api_key, api_secret = user.api_key, user.get_password("api_secret")
		authorization_token = f"{api_key}:{api_secret}"
		response = self.get(self.method("frappe.auth.get_logged_user"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"], "Administrator")

		authorization_token = None

	def test_404s(self):
		response = self.get(self.get_path("rest"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)
		response = self.get(self.resource("User", "NonExistent@s.com"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)

	def test_shorthand_controller_methods(self):
		shorthand_response = self.get(self.method("User", "get_all_roles"), {"sid": self.sid})
		self.assertIn("Website Manager", shorthand_response.json["data"])

		expanded_response = self.get(
			self.method("frappe.core.doctype.user.user.get_all_roles"), {"sid": self.sid}
		)
		self.assertEqual(expanded_response.data, shorthand_response.data)

	def test_logout(self):
		self.post(self.method("logout"), {"sid": self.sid})
		response = self.get(self.method("ping"))
		self.assertFalse(response.request.cookies["sid"])

	def test_run_doc_method_in_memory(self):
		dns = frappe.get_doc("Document Naming Settings")

		# Check that simple API can be called.
		response = self.get(
			self.method("run_doc_method"),
			{
				"sid": self.sid,
				"document": dns.as_dict(),
				"method": "get_transactions_and_prefixes",
			},
		)
		self.assertTrue(response.json["data"])
		self.assertGreaterEqual(len(response.json["docs"]), 1)

		# Call with known and unknown arguments, only known should get passed
		response = self.get(
			self.method("run_doc_method"),
			{
				"sid": self.sid,
				"document": dns.as_dict(),
				"method": "get_options",
				"kwargs": {"doctype": "Webhook", "unknown": "what"},
			},
		)
		self.assertEqual(response.status_code, 200)

	def test_logs(self):
		method = "frappe.tests.test_api.test"

		expected_message = "Failed v2"
		response = self.get(self.method(method), {"sid": self.sid, "message": expected_message}).json

		self.assertIsInstance(response["messages"], list)
		self.assertEqual(response["messages"][0]["message"], expected_message)

		# Cause handled failured
		with suppress_stdout():
			response = self.get(
				self.method(method), {"sid": self.sid, "message": expected_message, "fail": True}
			).json
		self.assertIsInstance(response["errors"], list)
		self.assertEqual(response["errors"][0]["message"], expected_message)
		self.assertEqual(response["errors"][0]["type"], "ValidationError")
		self.assertIn("Traceback", response["errors"][0]["exception"])

		# Cause handled failured
		with suppress_stdout():
			response = self.get(
				self.method(method),
				{"sid": self.sid, "message": expected_message, "fail": True, "handled": False},
			).json

		self.assertIsInstance(response["errors"], list)
		self.assertEqual(response["errors"][0]["type"], "ZeroDivisionError")
		self.assertIn("Traceback", response["errors"][0]["exception"])

	def test_add_comment(self):
		comment_txt = frappe.generate_hash()
		response = self.post(
			self.resource("User", "Administrator", "method", "add_comment"), {"text": comment_txt}
		).json
		self.assertEqual(response["data"]["content"], comment_txt)


class TestBulkOperationsV2(FrappeAPITestCase):
	"""Test bulk delete and bulk update endpoints"""

	version = "v2"
	DOCTYPE = "ToDo"

	def setUp(self) -> None:
		self.post(self.method("login"), {"sid": self.sid})
		return super().setUp()

	def test_bulk_delete_docs_single_doctype(self):
		# Create docs to delete
		doc1 = frappe.get_doc({"doctype": self.DOCTYPE, "description": "To delete 1"}).insert()
		doc2 = frappe.get_doc({"doctype": self.DOCTYPE, "description": "To delete 2"}).insert()
		frappe.db.commit()  # nosemgrep

		# Bulk delete
		response = self.post(
			self.resource(self.DOCTYPE, "bulk_delete"),
			{"names": [doc1.name, doc2.name], "sid": self.sid},
		)

		self.assertEqual(response.status_code, 200)
		data = response.json["data"]
		self.assertEqual(data["total"], 2)
		self.assertEqual(data["success_count"], 2)
		self.assertEqual(data["failure_count"], 0)
		self.assertIn(doc1.name, data["deleted"])
		self.assertIn(doc2.name, data["deleted"])

		# Verify deletion
		self.assertFalse(frappe.db.exists(self.DOCTYPE, doc1.name))
		self.assertFalse(frappe.db.exists(self.DOCTYPE, doc2.name))

	def test_bulk_delete_docs_partial_failure(self):
		# Create one valid doc
		doc = frappe.get_doc({"doctype": self.DOCTYPE, "description": "To delete"}).insert()
		frappe.db.commit()  # nosemgrep

		# Try to delete valid and non-existent doc
		non_existent = "non-existent-todo"
		response = self.post(
			self.resource(self.DOCTYPE, "bulk_delete"),
			{"names": [doc.name, non_existent], "sid": self.sid},
		)

		self.assertEqual(response.status_code, 200)
		data = response.json["data"]
		self.assertEqual(data["total"], 2)
		self.assertEqual(data["success_count"], 1)
		self.assertEqual(data["failure_count"], 1)
		self.assertIn(doc.name, data["deleted"])
		self.assertEqual(len(data["failed"]), 1)
		self.assertEqual(data["failed"][0]["name"], non_existent)

	def test_bulk_delete_cross_doctype(self):
		# Create docs of different types
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Test"}).insert()
		note = frappe.get_doc({"doctype": "Note", "title": "Test Note", "content": "Test"}).insert()
		frappe.db.commit()  # nosemgrep

		# Bulk delete across doctypes
		response = self.post(
			self.method("bulk_delete"),
			{
				"docs": [
					{"doctype": "ToDo", "name": todo.name},
					{"doctype": "Note", "name": note.name},
				],
				"sid": self.sid,
			},
		)

		self.assertEqual(response.status_code, 200)
		data = response.json["data"]
		self.assertEqual(data["total"], 2)
		self.assertEqual(data["success_count"], 2)
		self.assertEqual(data["failure_count"], 0)

		# Verify deletion
		self.assertFalse(frappe.db.exists("ToDo", todo.name))
		self.assertFalse(frappe.db.exists("Note", note.name))

	def test_bulk_delete_invalid_format(self):
		# Test with invalid format (not a list)
		response = self.post(
			self.method("bulk_delete"),
			{"docs": {"doctype": "ToDo", "name": "test"}, "sid": self.sid},
		)
		self.assertEqual(response.status_code, 417)
		self.assertIn("'docs' must be a list", response.json["errors"][0]["exception"])

		# Test with invalid document format (not dict)
		response = self.post(
			self.method("bulk_delete"),
			{"docs": ["invalid-item"], "sid": self.sid},
		)
		self.assertEqual(response.status_code, 200)
		data = response.json["data"]
		self.assertEqual(data["failure_count"], 1)
		self.assertIn("must be a dictionary", data["failed"][0]["error"])

	def test_bulk_update_docs_single_doctype(self):
		# Create fresh docs for this test
		doc1 = frappe.get_doc({"doctype": self.DOCTYPE, "description": "Original 1"}).insert()
		doc2 = frappe.get_doc({"doctype": self.DOCTYPE, "description": "Original 2"}).insert()
		frappe.db.commit()  # nosemgrep

		try:
			# Bulk update
			response = self.post(
				self.resource(self.DOCTYPE, "bulk_update"),
				{
					"docs": [
						{"name": doc1.name, "description": "Updated description 1", "priority": "High"},
						{"name": doc2.name, "description": "Updated description 2", "priority": "Low"},
					],
					"sid": self.sid,
				},
			)

			self.assertEqual(response.status_code, 200)
			data = response.json["data"]
			self.assertEqual(data["total"], 2)
			self.assertEqual(data["success_count"], 2)
			self.assertEqual(data["failure_count"], 0)
			self.assertIn(doc1.name, data["updated"])
			self.assertIn(doc2.name, data["updated"])

			# Verify updates
			updated_doc1 = frappe.get_doc(self.DOCTYPE, doc1.name)
			updated_doc2 = frappe.get_doc(self.DOCTYPE, doc2.name)
			self.assertEqual(updated_doc1.description, "Updated description 1")
			self.assertEqual(updated_doc1.priority, "High")
			self.assertEqual(updated_doc2.description, "Updated description 2")
			self.assertEqual(updated_doc2.priority, "Low")
		finally:
			frappe.delete_doc_if_exists(self.DOCTYPE, doc1.name)
			frappe.delete_doc_if_exists(self.DOCTYPE, doc2.name)
			frappe.db.commit()  # nosemgrep

	def test_bulk_update_cross_doctype(self):
		# Create test documents
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Test"}).insert()
		note = frappe.get_doc({"doctype": "Note", "title": "Test", "content": "Test"}).insert()
		frappe.db.commit()  # nosemgrep

		try:
			# Bulk update across doctypes
			response = self.post(
				self.method("bulk_update"),
				{
					"docs": [
						{"doctype": "ToDo", "name": todo.name, "description": "Updated ToDo"},
						{"doctype": "Note", "name": note.name, "title": "Updated Note"},
					],
					"sid": self.sid,
				},
			)

			self.assertEqual(response.status_code, 200)
			data = response.json["data"]
			self.assertEqual(data["total"], 2)
			self.assertEqual(data["success_count"], 2)
			self.assertEqual(data["failure_count"], 0)

			# Verify updates
			updated_todo = frappe.get_doc("ToDo", todo.name)
			updated_note = frappe.get_doc("Note", note.name)
			self.assertEqual(updated_todo.description, "Updated ToDo")
			self.assertEqual(updated_note.title, "Updated Note")
		finally:
			frappe.delete_doc_if_exists("ToDo", todo.name)
			frappe.delete_doc_if_exists("Note", note.name)
			frappe.db.commit()  # nosemgrep

	def test_bulk_update_partial_failure(self):
		# Create a fresh doc for this test
		doc = frappe.get_doc({"doctype": self.DOCTYPE, "description": "Original"}).insert()
		frappe.db.commit()  # nosemgrep
		valid_doc = doc.name
		non_existent = "non-existent-todo"

		try:
			# Try to update valid and non-existent doc
			response = self.post(
				self.resource(self.DOCTYPE, "bulk_update"),
				{
					"docs": [
						{"name": valid_doc, "description": "Updated"},
						{"name": non_existent, "description": "Should fail"},
					],
					"sid": self.sid,
				},
			)

			self.assertEqual(response.status_code, 200)
			data = response.json["data"]
			self.assertEqual(data["total"], 2)
			self.assertEqual(data["success_count"], 1)
			self.assertEqual(data["failure_count"], 1)
			self.assertIn(valid_doc, data["updated"])
			self.assertEqual(len(data["failed"]), 1)
			self.assertEqual(data["failed"][0]["name"], non_existent)

			# Verify successful update
			updated_doc = frappe.get_doc(self.DOCTYPE, valid_doc)
			self.assertEqual(updated_doc.description, "Updated")
		finally:
			frappe.delete_doc_if_exists(self.DOCTYPE, valid_doc)
			frappe.db.commit()  # nosemgrep

	def test_bulk_update_invalid_format(self):
		# Test with invalid format (not a list)
		response = self.post(
			self.resource(self.DOCTYPE, "bulk_update"),
			{"docs": {"name": "test", "description": "test"}, "sid": self.sid},
		)
		self.assertEqual(response.status_code, 417)
		self.assertIn("'docs' must be a list", response.json["errors"][0]["exception"])

		# Test with missing name field
		response = self.post(
			self.resource(self.DOCTYPE, "bulk_update"),
			{"docs": [{"description": "test"}], "sid": self.sid},
		)
		self.assertEqual(response.status_code, 200)
		data = response.json["data"]
		self.assertEqual(data["failure_count"], 1)
		self.assertIn("'name' must be a string or integer", data["failed"][0]["error"])

	def test_bulk_enqueue(self):
		# Create 25 docs
		docs = [
			frappe.get_doc({"doctype": self.DOCTYPE, "description": f"To delete {i}"}).insert()
			for i in range(25)
		]
		frappe.db.commit()  # nosemgrep

		try:
			# Bulk delete > 20 docs
			names = [doc.name for doc in docs]
			response = self.post(
				self.resource(self.DOCTYPE, "bulk_delete"),
				{"names": names, "sid": self.sid},
			)

			self.assertEqual(response.status_code, 202)
			self.assertIn("job_id", response.json["data"])
		finally:
			# Clean up
			for doc in docs:
				frappe.delete_doc_if_exists(self.DOCTYPE, doc.name)
			frappe.db.commit()  # nosemgrep

	def test_bulk_update_enqueue(self):
		# Create 25 docs
		docs = [
			frappe.get_doc({"doctype": self.DOCTYPE, "description": f"To update {i}"}).insert()
			for i in range(25)
		]
		frappe.db.commit()  # nosemgrep

		try:
			# Bulk update > 20 docs
			updates = [{"name": doc.name, "description": "Updated"} for doc in docs]
			response = self.post(
				self.resource(self.DOCTYPE, "bulk_update"),
				{"docs": updates, "sid": self.sid},
			)

			self.assertEqual(response.status_code, 202)
			self.assertIn("job_id", response.json["data"])
		finally:
			# Clean up
			for doc in docs:
				frappe.delete_doc_if_exists(self.DOCTYPE, doc.name)
			frappe.db.commit()  # nosemgrep


class TestDocTypeAPIV2(FrappeAPITestCase):
	version = "v2"

	def setUp(self) -> None:
		self.post(self.method("login"), {"sid": self.sid})
		return super().setUp()

	def test_meta(self):
		response = self.get(self.doctype_path("ToDo", "meta"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["name"], "ToDo")

	def test_count(self):
		response = self.get(self.doctype_path("ToDo", "count"))
		self.assertIsInstance(response.json["data"], int)


class TestReadOnlyMode(FrappeAPITestCase):
	"""During migration if read only mode can be enabled.
	Test if reads work well and writes are blocked"""

	version = "v2"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		update_site_config("allow_reads_during_maintenance", 1)
		cls.addClassCleanup(update_site_config, "maintenance_mode", 0)
		update_site_config("maintenance_mode", 1)

	def test_reads(self):
		response = self.get(self.resource("ToDo"), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIsInstance(response.json["data"], list)

	def test_blocked_writes_v2(self):
		with suppress_stdout():
			response = self.post(
				self.resource("ToDo"), {"description": frappe.mock("paragraph"), "sid": self.sid}
			)
		self.assertEqual(response.status_code, 503)
		self.assertEqual(response.json["errors"][0]["type"], "InReadOnlyMode")


def generate_admin_keys():
	from frappe.core.doctype.user.user import generate_keys

	generate_keys("Administrator")
	frappe.db.commit()  # nosemgrep


@whitelist_for_tests()
def test(*, fail=False, handled=True, message="Failed"):
	if fail:
		if handled:
			frappe.throw(message)
		else:
			1 / 0
	else:
		frappe.msgprint(message)
