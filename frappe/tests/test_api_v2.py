import json
import typing
from base64 import b64encode
from functools import cached_property
from io import BytesIO
from random import choice
from unittest.mock import patch

import requests

import frappe
import frappe.defaults
import frappe.share
from frappe.api import discovery
from frappe.installer import update_site_config
from frappe.model.document import Document
from frappe.tests.test_api import FrappeAPITestCase, make_request, suppress_stdout
from frappe.tests.utils import toggle_test_mode, wait_for_job, whitelist_for_tests
from frappe.tests.utils.test_capabilities import TestService, requires_test_service

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

	@requires_test_service(TestService.WEB_SERVER)
	def test_unauthorized_call_v2(self):
		# test 1: fetch documents without auth
		response = requests.get(self.resource(self.DOCTYPE))
		self.assertEqual(response.status_code, 403, response.text[-3000:])

	def test_get_list_v2(self):
		# test 2: fetch documents without params
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIn("data", response.json)

	def test_get_list_limit_v2(self):
		# test 3: fetch data with limit
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "limit": 2})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json["data"]), 2)

	def test_get_list_dict_v2(self):
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

	def test_get_list_default_order_by_v2(self):
		# without an explicit order_by, results should fall back to the
		# doctype's configured sort order (ToDo => creation desc)
		response = self.get(
			self.resource(self.DOCTYPE),
			{"sid": self.sid, "fields": '["creation"]', "limit": 5},
		)
		self.assertEqual(response.status_code, 200)
		creations = [row["creation"] for row in response.json["data"]]
		self.assertEqual(creations, sorted(creations, reverse=True))

	def test_get_list_fields_v2(self):
		# test 6: fetch response with fields
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "fields": '["description"]'})
		self.assertEqual(response.status_code, 200)
		json = frappe._dict(response.json)
		self.assertIn("description", json.data[0])

	def test_create_document_v2(self):
		data = {"description": frappe.mock("paragraph"), "sid": self.sid}
		response = self.post(self.resource(self.DOCTYPE), data)
		self.assertEqual(response.status_code, 200)
		docname = response.json["data"]["name"]
		self.assertIsInstance(docname, str)
		self.GENERATED_DOCUMENTS.append(docname)

	def test_copy_document_v2(self):
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

	def test_delete_document_v2(self):
		doc_to_delete = choice(self.GENERATED_DOCUMENTS)
		response = self.delete(self.resource(self.DOCTYPE, doc_to_delete), data={"sid": self.sid})
		self.assertEqual(response.status_code, 202)
		self.assertDictEqual(response.json, {"data": "ok"})

		response = self.get(self.resource(self.DOCTYPE, doc_to_delete))
		self.assertEqual(response.status_code, 404)
		self.GENERATED_DOCUMENTS.remove(doc_to_delete)

	def test_execute_doc_method_v2(self):
		response = self.get(self.resource("Website Theme", "Standard", "method", "get_apps"))
		self.assertEqual(response.json["data"][0]["name"], "frappe")

	def test_execute_doc_method_v2_validates_http_method(self):
		doc = frappe.get_doc("Website Theme", "Standard")
		method = getattr(doc.get_apps, "__func__", doc.get_apps)

		with (
			patch.dict(frappe.allowed_http_methods_for_whitelisted_func, {method: ["POST"]}),
			suppress_stdout(),
		):
			response = self.get(
				self.resource("Website Theme", "Standard", "method", "get_apps"), {"sid": self.sid}
			)

		self.assertEqual(response.status_code, 403, response.get_data(as_text=True)[-3000:])

	def test_update_document_v2(self):
		generated_desc = frappe.mock("paragraph")
		data = {"description": generated_desc, "sid": self.sid}
		random_doc = choice(self.GENERATED_DOCUMENTS)

		response = self.patch(self.resource(self.DOCTYPE, random_doc), data=data)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["description"], generated_desc)

		response = self.get(self.resource(self.DOCTYPE, random_doc))
		self.assertEqual(response.json["data"]["description"], generated_desc)

	def test_delete_document_non_existing_v2(self):
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

	def test_ping_v2(self):
		response = self.get(self.method("ping"))
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertEqual(response.json["data"], "pong")

	def test_get_user_info_v2(self):
		# server-to-server only
		response = self.get(self.method("frappe.realtime.get_user_info"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json.get("data"), {})

	def test_auth_cycle_v2(self):
		global authorization_token

		generate_admin_keys()
		user = frappe.get_doc("User", "Administrator")
		api_key, api_secret = user.api_key, user.get_password("api_secret")
		authorization_token = f"{api_key}:{api_secret}"
		response = self.get(self.method("frappe.auth.get_logged_user"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"], "Administrator")

		authorization_token = None

	def test_404s_v2(self):
		response = self.get(self.get_path("rest"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)
		response = self.get(self.resource("User", "NonExistent@s.com"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)

	def test_shorthand_controller_methods_v2(self):
		shorthand_response = self.get(self.method("User", "get_all_roles"), {"sid": self.sid})
		self.assertIn("Website Manager", shorthand_response.json["data"])

		expanded_response = self.get(
			self.method("frappe.core.doctype.user.user.get_all_roles"), {"sid": self.sid}
		)
		self.assertEqual(expanded_response.data, shorthand_response.data)

	def test_logout_v2(self):
		self.post(self.method("logout"), {"sid": self.sid})
		response = self.get(self.method("ping"))
		self.assertFalse(response.request.cookies["sid"])

	def test_run_doc_method_in_memory_v2(self):
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

	def test_logs_v2(self):
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

	def test_add_comment_v2(self):
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

	def cleanup_docs(self, docs: list, job_id: str | None = None):
		"""Delete `docs`, waiting for `job_id` first: the job touches these same rows."""
		if job_id:
			wait_for_job(job_id)
		for doc in docs:
			frappe.delete_doc_if_exists(self.DOCTYPE, doc.name)
		frappe.db.commit()  # nosemgrep

	def test_bulk_delete_docs_single_doctype_v2(self):
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

	def test_bulk_delete_docs_partial_failure_v2(self):
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

	def test_bulk_delete_cross_doctype_v2(self):
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

	def test_bulk_delete_invalid_format_v2(self):
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

	def test_bulk_update_docs_single_doctype_v2(self):
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

	def test_bulk_update_cross_doctype_v2(self):
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

	def test_bulk_update_partial_failure_v2(self):
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

	def test_bulk_update_invalid_format_v2(self):
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

	def test_bulk_enqueue_v2(self):
		# Create 25 docs
		docs = [
			frappe.get_doc({"doctype": self.DOCTYPE, "description": f"To delete {i}"}).insert()
			for i in range(25)
		]
		frappe.db.commit()  # nosemgrep

		# Late-bound on purpose: cleanup sees the job_id assigned below.
		job_id = None
		self.addCleanup(lambda: self.cleanup_docs(docs, job_id))

		# Bulk delete > 20 docs
		names = [doc.name for doc in docs]
		response = self.post(
			self.resource(self.DOCTYPE, "bulk_delete"),
			{"names": names, "sid": self.sid},
		)

		self.assertEqual(response.status_code, 202)
		self.assertIn("job_id", response.json["data"])
		job_id = response.json["data"]["job_id"]

	def test_bulk_update_enqueue_v2(self):
		# Create 25 docs
		docs = [
			frappe.get_doc({"doctype": self.DOCTYPE, "description": f"To update {i}"}).insert()
			for i in range(25)
		]
		frappe.db.commit()  # nosemgrep

		# Late-bound on purpose: cleanup sees the job_id assigned below.
		job_id = None
		self.addCleanup(lambda: self.cleanup_docs(docs, job_id))

		# Bulk update > 20 docs
		updates = [{"name": doc.name, "description": "Updated"} for doc in docs]
		response = self.post(
			self.resource(self.DOCTYPE, "bulk_update"),
			{"docs": updates, "sid": self.sid},
		)

		self.assertEqual(response.status_code, 202)
		self.assertIn("job_id", response.json["data"])
		job_id = response.json["data"]["job_id"]


class TestDocTypeAPIV2(FrappeAPITestCase):
	version = "v2"

	def setUp(self) -> None:
		self.post(self.method("login"), {"sid": self.sid})
		return super().setUp()

	def test_meta_v2(self):
		response = self.get(self.doctype_path("ToDo", "meta"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["name"], "ToDo")

	def test_count_v2(self):
		response = self.get(self.doctype_path("ToDo", "count"))
		self.assertIsInstance(response.json["data"], int)


class TestDiscoveryAPIV2(FrappeAPITestCase):
	version = "v2"
	TEST_USER = "api-discovery-user@example.com"

	@classmethod
	def tearDownClass(cls):
		frappe.delete_doc_if_exists("User", cls.TEST_USER, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self) -> None:
		self.post(self.method("login"), {"sid": self.sid})
		discovery.clear_cache()
		discovery.build_cache()
		return super().setUp()

	def discovery_path(self, *parts):
		return self.get_path("discovery", *parts)

	def non_developer_sid(self) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		if not frappe.db.exists("User", self.TEST_USER):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": self.TEST_USER,
					"first_name": "API Discovery User",
					"send_welcome_email": 0,
				}
			)
			user.append_roles("Website Manager")
			user.insert(ignore_permissions=True)
			frappe.db.commit()

		set_request(path="/")
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()
		frappe.local.login_manager.login_as(self.TEST_USER)
		return frappe.session.sid

	def test_search_v2(self):
		response = self.get(
			self.discovery_path("search"),
			{"sid": self.sid, "q": "test_api test"},
		)
		self.assertEqual(response.status_code, 200)
		results = response.json["data"]["results"]
		self.assertTrue(
			any(
				item.get("path") == "frappe.tests.test_api.test" and item["kind"] == "rpc" for item in results
			)
		)
		self.assertTrue(all("docstring" not in item for item in results))

		docstring_response = self.get(
			self.discovery_path("search"),
			{"sid": self.sid, "q": "parameter metadata"},
		)
		self.assertEqual(docstring_response.status_code, 200)
		self.assertTrue(
			any(
				item.get("path") == "frappe.tests.test_api.test"
				for item in docstring_response.json["data"]["results"]
			)
		)

		controller_response = self.get(
			self.discovery_path("search"),
			{"sid": self.sid, "q": "User populate_role_profile_roles"},
		)
		self.assertEqual(controller_response.status_code, 200)
		self.assertTrue(
			all(item["kind"] == "doctype" for item in controller_response.json["data"]["results"])
		)
		self.assertIn(
			{
				"type": "method",
				"doctype": "User",
				"method": "populate_role_profile_roles",
			},
			[
				{key: item[key] for key in ("type", "doctype", "method")}
				for item in controller_response.json["data"]["results"]
				if item.get("doctype")
			],
		)
		user_response = self.get(
			self.discovery_path("search"),
			{"sid": self.sid, "q": "User"},
		)
		self.assertTrue(
			any(
				item.get("doctype") == "User" and item.get("method") == "populate_role_profile_roles"
				for item in user_response.json["data"]["results"]
			)
		)
		inherited_response = self.get(
			self.discovery_path("search"),
			{"sid": self.sid, "q": "User add_comment"},
		)
		self.assertFalse(
			any(
				item.get("doctype") == "User" and item.get("method") == "add_comment"
				for item in inherited_response.json["data"]["results"]
			)
		)

	def test_doctype_methods_v2(self):
		response = self.get(self.discovery_path("doctype", "User"), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		methods = {item["method"]: item for item in response.json["data"]["methods"]}

		self.assertEqual(methods["populate_role_profile_roles"]["kind"], "doctype")
		self.assertNotIn("submit", methods)

		submittable_response = self.get(self.discovery_path("doctype", "DuckDB Sync"), {"sid": self.sid})
		self.assertEqual(submittable_response.status_code, 200)
		self.assertTrue(
			any(item["method"] == "submit" for item in submittable_response.json["data"]["methods"])
		)

	def test_doctype_method_document_v2(self):
		response = self.get(
			self.discovery_path("doctype", "User", "method", "add_comment"),
			{"sid": self.sid},
		)
		self.assertEqual(response.status_code, 200)
		data = response.json["data"]
		self.assertEqual(data["type"], "method")
		self.assertEqual(data["kind"], "doctype")
		self.assertEqual(data["doctype"], "User")
		self.assertEqual(data["method"], "add_comment")
		self.assertEqual(data["defined_in"], "frappe.model.document.Document")
		self.assertEqual(data["endpoint"], "/api/v2/document/User/{name}/method/add_comment")
		self.assertEqual(data["http_methods"], ["GET", "POST"])
		self.assertEqual(data["permission"], {"GET": "read", "POST": "write"})
		self.assertTrue(any(param["name"] == "comment_type" for param in data["params"]))
		self.assertIn("source", data)
		self.assertIn("def add_comment(", data["source"])

	def test_doctype_method_not_found_v2(self):
		paths = (
			self.discovery_path("doctype", "Missing DocType"),
			self.discovery_path("doctype", "User", "method", "validate"),
		)
		for path in paths:
			with self.subTest(path=path), suppress_stdout():
				response = self.get(path, {"sid": self.sid})
			self.assertEqual(response.status_code, 404)

	def test_methods_v2(self):
		root_response = self.get(self.discovery_path(), {"sid": self.sid})
		self.assertEqual(root_response.status_code, 200)
		self.assertGreater(root_response.json["data"]["resources"]["doctype_methods"], 0)
		self.assertEqual(
			root_response.json["data"]["links"]["doctype_method"],
			"/api/v2/discovery/doctype/{doctype}/method/{method}",
		)

		index_response = self.get(self.discovery_path("method"), {"sid": self.sid})
		self.assertEqual(index_response.status_code, 200)
		method = next(
			item
			for item in index_response.json["data"]["methods"]
			if item.get("path") == "frappe.tests.test_api.test"
		)
		self.assertEqual(method["kind"], "rpc")
		self.assertEqual(method["description"], "Exercise RPC success and failure responses.")
		doctype_method = next(
			item
			for item in index_response.json["data"]["methods"]
			if item.get("doctype") == "User" and item.get("method") == "populate_role_profile_roles"
		)
		self.assertEqual(doctype_method["kind"], "doctype")
		self.assertFalse(
			any(
				item.get("doctype") == "User" and item.get("method") == "add_comment"
				for item in index_response.json["data"]["methods"]
			)
		)

		method_response = self.get(
			self.discovery_path("method", "frappe.tests.test_api.test"), {"sid": self.sid}
		)
		self.assertEqual(method_response.status_code, 200)
		data = method_response.json["data"]
		self.assertEqual(data["kind"], "rpc")
		self.assertEqual(data["path"], "frappe.tests.test_api.test")
		self.assertEqual(
			data["docstring"],
			"Exercise RPC success and failure responses.\n\n"
			"Used by API discovery tests to verify parameter metadata.",
		)
		self.assertTrue(any(param["name"] == "message" for param in data["params"]))
		self.assertTrue(all("kind" not in param for param in data["params"]))
		self.assertTrue(
			any(
				param["name"] == "optional_message" and param["type"] == "str | None"
				for param in data["params"]
			)
		)
		# frappe opts into source exposure via the `expose_discovery_source` hook
		self.assertIn("source", data)
		self.assertIn("def test(", data["source"])

	def test_method_source_hidden_without_hook_v2(self):
		real_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "expose_discovery_source":
				return []
			return real_get_hooks(hook, *args, **kwargs)

		with patch.object(frappe, "get_hooks", side_effect=get_hooks):
			response = self.get(
				self.discovery_path("method", "frappe.tests.test_api.test"), {"sid": self.sid}
			)
			doctype_response = self.get(
				self.discovery_path("doctype", "User", "method", "add_comment"),
				{"sid": self.sid},
			)
		self.assertEqual(response.status_code, 200)
		self.assertNotIn("source", response.json["data"])
		self.assertEqual(doctype_response.status_code, 200)
		self.assertNotIn("source", doctype_response.json["data"])

	def test_cold_cache_returns_retryable_response_v2(self):
		discovery.clear_cache()
		with suppress_stdout(), patch("frappe.utils.error.log_error") as log_error:
			response = self.get(self.discovery_path(), {"sid": self.sid})
		self.assertEqual(response.status_code, 503)
		self.assertNotIn("Retry-After", response.headers)
		log_error.assert_not_called()

	def test_discovery_requires_developer_role_v2(self):
		sid = self.non_developer_sid()
		paths = (
			self.discovery_path(),
			self.discovery_path("search"),
			self.discovery_path("method"),
			self.discovery_path("method", "frappe.tests.test_api.test"),
			self.discovery_path("doctype", "User"),
			self.discovery_path("doctype", "User", "method", "add_comment"),
		)
		for path in paths:
			with self.subTest(path=path):
				with suppress_stdout():
					response = self.get(path, {"sid": sid})
				self.assertEqual(response.status_code, 403, response.get_data(as_text=True)[-3000:])


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

	def test_reads_v2(self):
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
def test(*, fail: int | bool = False, handled: int | bool = True, message: str = "Failed"):
	if fail:
		if handled:
			frappe.throw(message)
		else:
			1 / 0
	else:
		frappe.msgprint(message)


class TestIncludePartsV2(FrappeAPITestCase):
	"""`include=` parts beside a document read, and `include=children` beside a meta read."""

	version = "v2"
	TEST_USER = "api-include-user@example.com"

	@classmethod
	def setUpClass(cls):
		# the test client answers on another thread, so fixtures are committed to be visible there
		super().setUpClass()
		if not frappe.db.exists("User", cls.TEST_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.TEST_USER,
					"first_name": "Include User",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		cls.todo = frappe.get_doc(
			{"doctype": "ToDo", "description": frappe.generate_hash(), "allocated_to": cls.TEST_USER}
		).insert()
		cls.assignment = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": frappe.generate_hash(),
				"allocated_to": cls.TEST_USER,
				"reference_type": "ToDo",
				"reference_name": cls.todo.name,
			}
		).insert()
		frappe.share.add("ToDo", cls.todo.name, cls.TEST_USER, write=1)
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "ToDo",
				"reference_name": cls.todo.name,
				"content": "a comment",
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Favourite",
				"user": cls.TEST_USER,
				"reference_doctype": "ToDo",
				"reference_name": cls.todo.name,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.set_user("Administrator")
		frappe.delete_doc_if_exists("ToDo", cls.assignment.name, force=True)
		frappe.delete_doc_if_exists("ToDo", cls.todo.name, force=True)
		frappe.delete_doc_if_exists("User", cls.TEST_USER, force=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	@cached_property
	def user_sid(self) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		original_request = getattr(frappe.local, "request", None)
		set_request(path="/")
		try:
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as(self.TEST_USER)
			return frappe.session.sid
		finally:
			frappe.local.request = original_request

	def read(self, include: str, name: str | None = None):
		return self.get(
			self.resource("ToDo", name or self.todo.name), {"sid": self.user_sid, "include": include}
		)

	def seed_seen(self, users: list[str]):
		frappe.db.set_value("ToDo", self.todo.name, "_seen", json.dumps(users), update_modified=False)
		frappe.db.commit()  # nosemgrep

	def test_parts_beside_the_document(self):
		response = self.read("permissions,attachments,assignments,shares,tags,favourites,comments,users")
		self.assertEqual(response.status_code, 200, response.json)
		body = response.json
		self.assertEqual(body["data"]["name"], self.todo.name)
		self.assertEqual(body["permissions"]["read"], 1)
		self.assertEqual(body["attachments"], [])
		self.assertEqual(body["assignments"][0]["user"], self.TEST_USER)
		self.assertNotIn("allocated_to", body["assignments"][0])
		self.assertEqual(
			body["shares"], [{"user": self.TEST_USER, "read": 1, "write": 1, "submit": 0, "share": 0}]
		)
		self.assertEqual(body["tags"], [])
		self.assertEqual(body["favourites"][0]["user"], self.TEST_USER)
		self.assertIn("a comment", body["comments"][0]["content"])
		self.assertEqual(body["users"][self.TEST_USER]["full_name"], "Include User")
		self.assertIn("Administrator", body["users"])

	def test_bare_read_has_no_parts_and_marks_nothing(self):
		with patch.object(Document, "add_seen") as add_seen:
			response = self.read("")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(set(response.json), {"data"})
		add_seen.assert_not_called()

	def test_seen_marks_and_returns_the_list(self):
		# a GET's write is rolled back under test, so the mark is asserted on the call
		self.seed_seen(["other@example.com"])
		with patch.object(Document, "add_seen") as add_seen:
			response = self.read("seen")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["seen"], ["other@example.com", self.TEST_USER])
		add_seen.assert_called_once()

	def test_users_ignores_parts_that_name_no_user(self):
		frappe.get_doc({"doctype": "Tag", "name": "read"}).insert(
			ignore_permissions=True, ignore_if_duplicate=True
		)
		frappe.db.commit()  # nosemgrep
		from frappe.desk.doctype.tag.tag import add_tag

		add_tag("read", "ToDo", self.todo.name)
		frappe.db.commit()  # nosemgrep
		response = self.read("permissions,tags,link_titles,users")
		self.assertEqual(response.json["tags"], ["read"])
		self.assertEqual(set(response.json["users"]), {"Administrator"})

	def test_include_must_be_a_string(self):
		with suppress_stdout():
			response = self.get(self.resource("ToDo", self.todo.name), {"sid": self.sid, "include": ["seen"]})
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "ValidationError")

	def test_users_covers_the_seen_list(self):
		self.seed_seen(["other@example.com"])
		with patch.object(Document, "add_seen"):
			response = self.read("seen,users")
		self.assertIn(self.TEST_USER, response.json["users"])

	def test_seen_does_not_mark_twice(self):
		self.seed_seen([self.TEST_USER])
		with patch.object(Document, "add_seen") as add_seen:
			response = self.read("seen")
		self.assertEqual(response.json["seen"], [self.TEST_USER])
		add_seen.assert_not_called()

	def test_unknown_part_is_an_error(self):
		with suppress_stdout():
			response = self.read("permissions,views")
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "UnknownPartError")
		self.assertNotIn("permissions", response.json)

	def test_meta_children(self):
		response = self.get(self.doctype_path("User", "meta"), {"sid": self.user_sid, "include": "children"})
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"]["name"], "User")
		self.assertEqual(response.json["data"]["masked_fields"], [])
		children = {child["name"]: child for child in response.json["children"]}
		self.assertIn("Has Role", children)
		self.assertEqual(children["Has Role"]["masked_fields"], [])

	def test_meta_unknown_part_is_an_error(self):
		with suppress_stdout():
			response = self.get(
				self.doctype_path("User", "meta"), {"sid": self.user_sid, "include": "fields"}
			)
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "UnknownPartError")

	def test_list_or_filters(self):
		response = self.get(
			self.resource("ToDo"),
			{
				"sid": self.sid,
				"fields": '["name"]',
				"or_filters": json.dumps(
					[["name", "=", self.todo.name], ["description", "=", self.assignment.description]]
				),
			},
		)
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(len(response.json["data"]), 2)

	def test_list_or_filters_shape(self):
		with suppress_stdout():
			response = self.get(self.resource("ToDo"), {"sid": self.sid, "or_filters": '"name"'})
		self.assertEqual(response.status_code, 417)


class TestListPartsV2(FrappeAPITestCase):
	"""`include=count` beside a list read, and the link-field search route."""

	version = "v2"

	@classmethod
	def setUpClass(cls):
		# the test client answers on another thread, so fixtures are committed to be visible there
		super().setUpClass()
		cls.prefix = f"api-search-{frappe.generate_hash(length=8)}"
		cls.todos = [
			frappe.get_doc({"doctype": "ToDo", "description": f"{cls.prefix} {word}"}).insert()
			for word in ("alpha", "bravo", "charlie")
		]
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for todo in cls.todos:
			frappe.delete_doc_if_exists("ToDo", todo.name, force=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	@property
	def filters(self) -> str:
		return json.dumps({"description": ["like", f"{self.prefix}%"]})

	def list(self, **params):
		return self.get(self.resource("ToDo"), {"sid": self.sid, "filters": self.filters, **params})

	def search(self, **params):
		return self.get(self.doctype_path("ToDo", "search"), {"sid": self.sid, **params})

	def test_count_beside_the_list(self):
		response = self.list(include="count", limit=1)
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(len(response.json["data"]), 1)
		self.assertTrue(response.json["has_next_page"])
		self.assertEqual(response.json["count"], 3)
		self.assertFalse(response.json["count_capped"])
		# get_count's own ten-minute cache header must not reach the list response
		self.assertNotIn("max-age=600", response.headers["Cache-Control"])

	def test_count_stops_at_the_cap(self):
		with patch("frappe.api.include.COUNT_CAP", 2):
			response = self.list(include="count")
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(len(response.json["data"]), 3)
		self.assertEqual(response.json["count"], 2)
		self.assertTrue(response.json["count_capped"])

	def test_count_of_exactly_the_cap_is_not_capped(self):
		with patch("frappe.api.include.COUNT_CAP", 3):
			response = self.list(include="count")
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["count"], 3)
		self.assertFalse(response.json["count_capped"])

	def test_count_is_null_on_timeout(self):
		with patch("frappe.desk.reportview.count_rows", return_value=None):
			response = self.list(include="count")
		self.assertEqual(response.status_code, 200, response.json)
		self.assertIsNone(response.json["count"])
		self.assertFalse(response.json["count_capped"])

	def test_count_follows_or_filters(self):
		or_filters = json.dumps([["name", "=", self.todos[0].name], ["name", "=", self.todos[1].name]])
		response = self.list(include="count", or_filters=or_filters)
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["count"], 2)

	def test_count_follows_group_by(self):
		# the fixtures share one status; a grouped list of two statuses counts two groups, not three rows
		closed = self.todos[2].name
		frappe.db.set_value("ToDo", closed, "status", "Closed")
		frappe.db.commit()  # nosemgrep
		try:
			response = self.list(include="count", fields=json.dumps(["status"]), group_by="status")
		finally:
			frappe.db.set_value("ToDo", closed, "status", "Open")
			frappe.db.commit()  # nosemgrep
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(len(response.json["data"]), 2)
		self.assertEqual(response.json["count"], 2)

	def test_no_count_without_include(self):
		for params in ({}, {"include": ""}):
			response = self.list(**params)
			self.assertEqual(response.status_code, 200, response.json)
			self.assertEqual(set(response.json), {"data", "has_next_page"})

	def test_list_unknown_part_is_an_error(self):
		with suppress_stdout():
			response = self.list(include="count,totals")
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "UnknownPartError")
		self.assertNotIn("count", response.json)

	def test_search_rows(self):
		response = self.search(txt=self.prefix)
		self.assertEqual(response.status_code, 200, response.json)
		rows = response.json["data"]
		self.assertEqual({row["value"] for row in rows}, {todo.name for todo in self.todos})
		self.assertEqual(set(rows[0]), {"value", "label", "description"})
		self.assertEqual(response.headers["Cache-Control"], "private,max-age=60,stale-while-revalidate=300")

	def test_search_limit_and_start(self):
		first = self.search(txt=self.prefix, limit=2)
		self.assertEqual(len(first.json["data"]), 2)
		rest = self.search(txt=self.prefix, limit=2, start=2)
		self.assertEqual(len(rest.json["data"]), 1)
		self.assertNotIn(rest.json["data"][0]["value"], [row["value"] for row in first.json["data"]])

	def test_search_takes_filters(self):
		response = self.search(txt=self.prefix, filters=json.dumps({"name": self.todos[1].name}))
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual([row["value"] for row in response.json["data"]], [self.todos[1].name])

	def test_search_limit_zero_falls_back_to_the_default_page(self):
		extra = [
			frappe.get_doc({"doctype": "ToDo", "description": f"{self.prefix} extra {index}"}).insert()
			for index in range(8)
		]
		frappe.db.commit()  # nosemgrep
		try:
			response = self.search(txt=self.prefix, limit=0)
			self.assertEqual(response.status_code, 200, response.json)
			self.assertEqual(len(response.json["data"]), 10)
		finally:
			for todo in extra:
				frappe.delete_doc_if_exists("ToDo", todo.name, force=True)
			frappe.db.commit()  # nosemgrep

	def test_search_user_through_the_standard_query(self):
		# User routes to user_query, which reads the filters as a dict
		response = self.get(
			self.doctype_path("User", "search"),
			{
				"sid": self.sid,
				"txt": "Admin",
				"filters": json.dumps({"enabled": 1, "user_type": "System User"}),
			},
		)
		self.assertEqual(response.status_code, 200, response.json)
		self.assertIn("Administrator", [row["value"] for row in response.json["data"]])

	def test_search_refuses_a_guest(self):
		# no suppress_stdout: the refusal prints, and a None stdout turns that into a 500
		response = self.get(self.doctype_path("ToDo", "search"), {"sid": "Guest", "txt": self.prefix})
		self.assertEqual(response.status_code, 403)


class TestCollaborationWritesV2(FrappeAPITestCase):
	"""`POST`, `DELETE` and `PATCH` on the collaboration parts of a document route."""

	version = "v2"
	TEST_USER = "api-collab-user@example.com"
	PEER = "api-collab-peer@example.com"
	# adding a tag creates a Tag master that outlives the class; these are the ones the tests add
	TAGS = ("urgent", "slashed")

	@classmethod
	def setUpClass(cls):
		# the test client answers on another thread, so fixtures are committed to be visible there
		super().setUpClass()
		for email in (cls.TEST_USER, cls.PEER):
			cls.make_user(email)
		cls.todo = cls.make_todo()
		# owned by Administrator and allocated to someone else, so TEST_USER cannot read it
		cls.unreadable = cls.make_todo(cls.PEER)
		cls.note = frappe.get_doc({"doctype": "Note", "title": frappe.generate_hash(), "public": 1}).insert()
		slash = cls.make_todo()
		cls.slash_name = frappe.rename_doc("ToDo", slash.name, f"SO/2026/{slash.name}", force=True)
		cls.admin_comment = cls.make_comment(cls.todo.name)
		cls.other_comment = cls.make_comment(cls.slash_name)
		frappe.db.commit()  # nosemgrep

	@classmethod
	def make_user(cls, email: str):
		if frappe.db.exists("User", email):
			return
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Collab User",
				"send_welcome_email": 0,
				"document_follow_notify": 1,
			}
		).insert(ignore_permissions=True)
		user.add_roles("Desk User")

	@classmethod
	def make_todo(cls, allocated_to: str | None = None):
		return frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": frappe.generate_hash(),
				"allocated_to": allocated_to or cls.TEST_USER,
			}
		).insert()

	@classmethod
	def make_comment(cls, name: str) -> str:
		return (
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"reference_doctype": "ToDo",
					"reference_name": name,
					"content": "a comment",
				}
			)
			.insert()
			.name
		)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.set_user("Administrator")
		frappe.delete_doc_if_exists("ToDo", cls.slash_name, force=True)
		frappe.delete_doc_if_exists("ToDo", cls.todo.name, force=True)
		frappe.delete_doc_if_exists("ToDo", cls.unreadable.name, force=True)
		frappe.delete_doc_if_exists("Note", cls.note.name, force=True)
		for tag in cls.TAGS:
			frappe.delete_doc_if_exists("Tag", tag, force=True)
		for email in (cls.TEST_USER, cls.PEER):
			frappe.delete_doc_if_exists("User", email, force=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	@cached_property
	def user_sid(self) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		original_request = getattr(frappe.local, "request", None)
		set_request(path="/")
		try:
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as(self.TEST_USER)
			return frappe.session.sid
		finally:
			frappe.local.request = original_request

	def part(self, *parts, doctype: str = "ToDo", name: str | None = None):
		return self.resource(doctype, name or self.todo.name, *parts)

	def add(self, path: str, body: dict | None = None, sid: str | None = None):
		return self.post(path, {"sid": sid or self.user_sid, **(body or {})})

	def remove(self, path: str, sid: str | None = None):
		return self.delete(path, data={"sid": sid or self.user_sid})

	def edit(self, path: str, body: dict, sid: str | None = None):
		return self.patch(path, {"sid": sid or self.user_sid, **body})

	def test_assignment_add_and_remove(self):
		response = self.add(self.part("assignments"), {"user": self.PEER, "description": "look"})
		self.assertEqual(response.status_code, 200, response.json)
		rows = response.json["data"]["assignments"]
		self.assertEqual(rows[0]["user"], self.PEER)
		self.assertEqual(set(rows[0]), {"user", "description", "priority", "date"})
		self.assertIn(self.PEER, response.json["data"]["users"])

		response = self.remove(self.part("assignments", self.PEER))
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"]["assignments"], [])
		frappe.db.rollback()
		status = frappe.db.get_value(
			"ToDo",
			{"reference_type": "ToDo", "reference_name": self.todo.name, "allocated_to": self.PEER},
			"status",
		)
		self.assertEqual(status, "Cancelled")

	def test_assignment_rejects_an_unstringy_option(self):
		with suppress_stdout():
			response = self.add(self.part("assignments"), {"user": self.PEER, "priority": ["High"]})
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "InvalidRequestError")

	def test_assignment_needs_write_on_the_document(self):
		# not under suppress_stdout: it sets sys.stdout to None, and the share lookup this
		# refusal walks prints a deprecation warning
		response = self.add(
			self.part("assignments", doctype="Note", name=self.note.name), {"user": self.PEER}
		)
		self.assertEqual(response.status_code, 403, response.json)
		self.assertEqual(response.json["errors"][0]["type"], "PermissionError")

	def test_share_upserts_one_row(self):
		self.add(self.part("shares"), {"user": self.PEER, "write": 1})
		response = self.add(self.part("shares"), {"user": self.PEER, "write": 0, "share": 1})
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(
			response.json["data"]["shares"],
			[{"user": self.PEER, "read": 1, "write": 0, "submit": 0, "share": 1}],
		)
		self.assertIn(self.PEER, response.json["data"]["users"])
		response = self.remove(self.part("shares", self.PEER))
		self.assertEqual(response.json["data"]["shares"], [])

	def test_share_with_everyone(self):
		response = self.add(self.part("shares"), {"user": "everyone"})
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"]["shares"][0]["user"], "everyone")
		self.assertNotIn("everyone", response.json["data"]["users"])
		response = self.remove(self.part("shares", "everyone"))
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"]["shares"], [])

	def test_share_cannot_drop_read(self):
		with suppress_stdout():
			response = self.add(self.part("shares"), {"user": self.PEER, "read": 0})
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "InvalidRequestError")

	def test_share_needs_the_share_right(self):
		response = self.add(self.part("shares", doctype="Note", name=self.note.name), {"user": self.PEER})
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json["errors"][0]["type"], "PermissionError")

	def test_tag_add_and_remove(self):
		response = self.add(self.part("tags"), {"tag": "urgent"})
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"], {"tags": ["urgent"]})
		response = self.remove(self.part("tags", "urgent"))
		self.assertEqual(response.json["data"], {"tags": []})

	def test_tag_needs_write(self):
		response = self.add(self.part("tags", doctype="Note", name=self.note.name), {"tag": "urgent"})
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json["errors"][0]["type"], "PermissionError")

	def test_tag_rejects_a_comma(self):
		with suppress_stdout():
			response = self.add(self.part("tags"), {"tag": "a,b"})
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "InvalidRequestError")

	def test_favourite_add_and_remove(self):
		response = self.add(self.part("favourites"))
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"]["favourites"][0]["user"], self.TEST_USER)
		self.assertIn(self.TEST_USER, response.json["data"]["users"])
		# the answer names the row it just made, so the caller need not guess it from the part
		self.assertEqual(response.json["data"]["file"], rows[0]["name"])
		response = self.remove(self.part("favourites"))
		self.assertEqual(response.json["data"]["favourites"], [])

	def test_follow_add_read_and_remove(self):
		path = self.part("follows", doctype="Note", name=self.note.name)
		response = self.add(path)
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"], {"follows": True})
		response = self.get(
			self.resource("Note", self.note.name), {"sid": self.user_sid, "include": "follows"}
		)
		self.assertIs(response.json["follows"], True)
		response = self.remove(path)
		self.assertEqual(response.json["data"], {"follows": False})

	def test_declined_follow_answers_with_the_true_state(self):
		with suppress_stdout():
			response = self.add(self.part("follows"))
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"], {"follows": False})

	def test_comment_add_edit_and_remove(self):
		response = self.add(self.part("comments"), {"content": "hello"})
		self.assertEqual(response.status_code, 200, response.json)
		mine = [row for row in response.json["data"]["comments"] if row["owner"] == self.TEST_USER]
		self.assertIn("hello", mine[0]["content"])
		self.assertIn(self.TEST_USER, response.json["data"]["users"])

		response = self.edit(self.part("comments", mine[0]["name"]), {"content": "edited"})
		self.assertEqual(response.status_code, 200, response.json)
		contents = [row["content"] for row in response.json["data"]["comments"]]
		self.assertTrue(any("edited" in content for content in contents))

		response = self.remove(self.part("comments", mine[0]["name"]))
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual([row["name"] for row in response.json["data"]["comments"]], [self.admin_comment])

	def test_comment_on_an_unreadable_record_is_refused(self):
		response = self.add(self.part("comments", name=self.unreadable.name), {"content": "hello"})
		self.assertEqual(response.status_code, 403, response.json)
		self.assertEqual(response.json["errors"][0]["type"], "PermissionError")

	def test_comment_of_another_user_cannot_be_removed(self):
		with suppress_stdout():
			response = self.remove(self.part("comments", self.admin_comment))
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json["errors"][0]["type"], "PermissionError")
		self.assertTrue(frappe.db.exists("Comment", self.admin_comment))

	def test_comment_of_another_user_cannot_be_edited(self):
		with suppress_stdout():
			response = self.edit(self.part("comments", self.admin_comment), {"content": "mine now"})
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json["errors"][0]["type"], "PermissionError")

	def test_comment_on_another_record_cannot_be_removed(self):
		with suppress_stdout():
			response = self.remove(self.part("comments", self.other_comment))
		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.json["errors"][0]["type"], "DoesNotExistError")
		self.assertTrue(frappe.db.exists("Comment", self.other_comment))

	def test_bad_body_is_an_error(self):
		with suppress_stdout():
			response = self.add(self.part("tags"), {"tag": ""})
		self.assertEqual(response.status_code, 417)
		self.assertEqual(response.json["errors"][0]["type"], "InvalidRequestError")

	def test_key_rules(self):
		with suppress_stdout():
			keyless = self.remove(self.part("favourites", "someone"))
			keyed = self.remove(self.part("tags"))
			edited = self.edit(self.part("tags", "urgent"), {"tag": "x"})
		self.assertEqual(keyless.status_code, 417)
		self.assertEqual(keyed.status_code, 417)
		self.assertEqual(edited.status_code, 417)
		self.assertEqual(edited.json["errors"][0]["type"], "ValidationError")

	def test_unknown_part_is_not_a_route(self):
		with suppress_stdout():
			response = self.add(self.part("views"))
		self.assertEqual(response.status_code, 404)

	def test_slash_named_record_routes(self):
		name = self.slash_name
		response = self.get(self.resource("ToDo", name), {"sid": self.user_sid, "include": "tags"})
		self.assertEqual(response.json["data"]["name"], name)
		response = self.add(self.part("tags", name=name), {"tag": "slashed"})
		self.assertEqual(response.json["data"], {"tags": ["slashed"]}, response.json)
		response = self.remove(self.part("tags", "slashed", name=name))
		self.assertEqual(response.json["data"], {"tags": []}, response.json)
		response = self.add(self.part("favourites", name=name))
		self.assertEqual(response.json["data"]["favourites"][0]["user"], self.TEST_USER)
		response = self.remove(self.part("favourites", name=name))
		self.assertEqual(response.json["data"]["favourites"], [])
		response = self.edit(self.resource("ToDo", name), {"description": "still a document"})
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"]["description"], "still a document")
		response = self.remove(self.resource("ToDo", name))
		self.assertEqual(response.status_code, 202, response.json)
		frappe.db.rollback()
		self.assertFalse(frappe.db.exists("ToDo", name))


class TestSessionAPIV2(FrappeAPITestCase):
	version = "v2"

	def session_path(self):
		return self.get_path("session")

	def test_session_v2(self):
		response = self.get(self.session_path(), {"sid": self.sid})
		self.assertEqual(response.status_code, 200, response.json)
		data = response.json["data"]
		self.assertEqual(data["user"]["name"], "Administrator")
		self.assertIsInstance(data["roles"], list)
		self.assertIn("System Manager", data["roles"])
		self.assertTrue(data["lang"])
		self.assertTrue(data["timezone"])
		self.assertIsInstance(data["defaults"], dict)

	def test_session_serves_a_guest_v2(self):
		response = self.get(self.session_path(), {"sid": "Guest"})
		self.assertEqual(response.status_code, 200, response.json)
		data = response.json["data"]
		self.assertEqual(data["user"]["name"], "Guest")
		self.assertIn("Guest", data["roles"])

	def test_session_withholds_site_defaults_from_a_guest_v2(self):
		frappe.db.set_default("api_v2_guest_defaults_probe", "leaked")
		frappe.db.commit()  # nosemgrep
		try:
			response = self.get(self.session_path(), {"sid": "Guest"})
			self.assertEqual(response.status_code, 200, response.json)
			self.assertEqual(response.json["data"]["defaults"], {})
		finally:
			frappe.defaults.clear_default("api_v2_guest_defaults_probe")
			frappe.db.commit()  # nosemgrep


class TestFileRoutesV2(FrappeAPITestCase):
	"""Uploading through `POST /document/File`, and the `attachments` sub-resource."""

	version = "v2"
	TEST_USER = "api-file-user@example.com"
	READER = "api-file-reader@example.com"

	@classmethod
	def setUpClass(cls):
		# the test client answers on another thread, so fixtures are committed to be visible there
		super().setUpClass()
		for email in (cls.TEST_USER, cls.READER):
			cls.make_user(email)
		cls.todo = cls.make_todo()
		cls.other = cls.make_todo()
		frappe.db.commit()  # nosemgrep

	@classmethod
	def make_user(cls, email: str):
		if frappe.db.exists("User", email):
			return
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "File User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		user.add_roles("Desk User")

	@classmethod
	def make_todo(cls):
		return frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": frappe.generate_hash(),
				"allocated_to": cls.TEST_USER,
			}
		).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.set_user("Administrator")
		for todo in (cls.todo, cls.other):
			for name in frappe.get_all(
				"File",
				filters={"attached_to_doctype": "ToDo", "attached_to_name": todo.name},
				pluck="name",
			):
				frappe.delete_doc_if_exists("File", name, force=True)
			frappe.delete_doc_if_exists("ToDo", todo.name, force=True)
		for email in (cls.TEST_USER, cls.READER):
			frappe.delete_doc_if_exists("User", email, force=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def sid_of(self, user: str) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		original_request = getattr(frappe.local, "request", None)
		set_request(path="/")
		try:
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as(user)
			return frappe.session.sid
		finally:
			frappe.local.request = original_request

	@cached_property
	def user_sid(self) -> str:
		return self.sid_of(self.TEST_USER)

	def upload(self, path: str, content: bytes, file_name: str, **fields):
		"""A multipart POST, the way the browser's chunk loop sends one."""
		data = {"file": (BytesIO(content), file_name), "sid": self.user_sid, **fields}
		return make_request(target=self.TEST_CLIENT.post, args=(path,), kwargs={"data": data})

	def attachments_path(self, name: str, file_name: str | None = None) -> str:
		parts = ("ToDo", name, "attachments")
		return self.resource(*parts, file_name) if file_name else self.resource(*parts)

	def attach_one(self, todo_name: str, file_name: str) -> str:
		"""Upload a file to the document and return its File name, as the answer reports it."""
		response = self.upload(self.attachments_path(todo_name), b"hello", file_name)
		self.assertEqual(response.status_code, 200, response.json)
		return response.json["data"]["attachments"][0]["name"]

	def test_detached_upload_creates_a_file(self):
		response = self.upload(
			self.resource("File"), b"hello", "detached.txt", is_private="1", folder="Home/Attachments"
		)
		self.assertEqual(response.status_code, 200, response.json)
		data = response.json["data"]
		self.assertEqual(data["file_name"], "detached.txt")
		self.assertTrue(data["file_url"])
		frappe.delete_doc_if_exists("File", data["name"], force=True)

	def test_the_file_route_does_not_take_over_the_file_list(self):
		# the static POST rule shares its path with the dynamic list rule
		response = self.get(self.resource("File"), {"sid": self.sid, "limit": 1})
		self.assertEqual(response.status_code, 200, response.json)
		self.assertIsInstance(response.json["data"], list)

	def test_json_create_is_still_a_plain_insert(self):
		response = self.post(
			self.resource("File"),
			{
				"sid": self.sid,
				"file_name": "base64.txt",
				"is_private": 1,
				"content": b64encode(b"hello").decode(),
				"decode": True,
			},
		)
		self.assertEqual(response.status_code, 200, response.json)
		self.assertEqual(response.json["data"]["file_name"], "base64.txt")
		frappe.delete_doc_if_exists("File", response.json["data"]["name"], force=True)

	def test_a_method_field_is_refused_on_the_document_route(self):
		response = self.upload(self.resource("File"), b"hello", "redirect.txt", method="frappe.ping")
		self.assertEqual(response.status_code, 417, response.json)

	def test_attach_answers_with_the_refreshed_part(self):
		response = self.upload(self.attachments_path(self.todo.name), b"hello", "attached.txt")
		self.assertEqual(response.status_code, 200, response.json)
		rows = response.json["data"]["attachments"]
		self.assertEqual([row["file_name"] for row in rows], ["attached.txt"])
		# the part carries who uploaded it and when, and the users key names them
		self.assertEqual(rows[0]["owner"], self.TEST_USER)
		self.assertTrue(rows[0]["creation"])
		self.assertIn(self.TEST_USER, response.json["data"]["users"])

	def test_a_chunk_that_is_not_the_last_answers_with_no_file(self):
		response = self.upload(
			self.attachments_path(self.todo.name),
			b"half",
			"chunked.txt",
			chunk_index="0",
			total_chunk_count="2",
			chunk_byte_offset="0",
			total_file_size="8",
		)
		self.assertEqual(response.status_code, 200, response.json)
		self.assertIsNone(response.json["data"])

	def test_attach_needs_write_on_the_document(self):
		data = {"file": (BytesIO(b"hello"), "denied.txt"), "sid": self.sid_of(self.READER)}
		response = make_request(
			target=self.TEST_CLIENT.post,
			args=(self.attachments_path(self.todo.name),),
			kwargs={"data": data},
		)
		self.assertEqual(response.status_code, 403, response.json)

	def test_attach_without_bytes_is_an_error(self):
		response = self.post(self.attachments_path(self.todo.name), {"sid": self.user_sid})
		self.assertEqual(response.status_code, 417, response.json)

	def test_detach_deletes_the_file(self):
		file_name = self.attach_one(self.todo.name, "gone.txt")
		response = self.delete(
			self.attachments_path(self.todo.name, file_name), query_string={"sid": self.user_sid}
		)
		self.assertEqual(response.status_code, 200, response.json)
		# another test attaches to the same document, so the part is read for this file alone
		names = [row["name"] for row in response.json["data"]["attachments"]]
		self.assertNotIn(file_name, names)
		# the request ran on another thread: end this one's read view before asking the database
		frappe.db.rollback()
		self.assertFalse(frappe.db.exists("File", file_name))

	def test_detach_refuses_a_file_on_another_document(self):
		file_name = self.attach_one(self.other.name, "elsewhere.txt")
		response = self.delete(
			self.attachments_path(self.todo.name, file_name), query_string={"sid": self.user_sid}
		)
		self.assertEqual(response.status_code, 404, response.json)
		frappe.db.rollback()
		self.assertTrue(frappe.db.exists("File", file_name))
		frappe.delete_doc_if_exists("File", file_name, force=True)

	def test_a_file_response_passes_through_the_v2_method_route(self):
		response = self.get(
			self.method("frappe.core.doctype.data_import.data_import.download_template"),
			{
				"sid": self.sid,
				"doctype": "ToDo",
				"export_fields": {"ToDo": ["description"]},
				"export_records": "blank_template",
				"file_type": "CSV",
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn("text/csv", response.headers["Content-Type"])
		self.assertIn("Description", response.get_data(as_text=True))
