import typing
from random import choice
from unittest.mock import patch

import requests

import frappe
from frappe.api import discovery
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

	def test_unauthorized_call_v2(self):
		# test 1: fetch documents without auth
		response = requests.get(self.resource("User"))
		self.assertEqual(response.status_code, 403)

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

		self.assertEqual(response.status_code, 403)

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

	def setUp(self) -> None:
		self.post(self.method("login"), {"sid": self.sid})
		discovery.clear_cache()
		discovery.build_cache()
		return super().setUp()

	def discovery_path(self, *parts):
		return self.get_path("discovery", *parts)

	def test_root_v2(self):
		response = self.get(self.discovery_path(), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		data = response.json["data"]
		self.assertEqual(data["type"], "discovery")
		self.assertIn("methods", data["resources"])
		self.assertNotIn("doctypes", data["resources"])
		self.assertNotIn("reports", data["resources"])
		self.assertIn("search", data["links"])
		self.assertEqual(data["links"]["methods"], "/api/v2/discovery/method")
		self.assertEqual(data["links"]["method"], "/api/v2/discovery/method/{method}")
		self.assertNotIn("doctypes", data)
		self.assertNotIn("reports", data)

	def test_search_v2(self):
		response = self.get(
			self.discovery_path("search"),
			{"sid": self.sid, "q": "test_api test"},
		)
		self.assertEqual(response.status_code, 200)
		results = response.json["data"]["results"]
		self.assertTrue(any(item.get("path") == "frappe.tests.test_api.test" for item in results))
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

	def test_methods_v2(self):
		index_response = self.get(self.discovery_path("method"), {"sid": self.sid})
		self.assertEqual(index_response.status_code, 200)
		method = next(
			item
			for item in index_response.json["data"]["methods"]
			if item["path"] == "frappe.tests.test_api.test"
		)
		self.assertEqual(method["description"], "Exercise RPC success and failure responses.")
		self.assertNotIn("docstring", method)
		self.assertNotIn("module", method)
		self.assertNotIn("name", method)
		self.assertNotIn("http_methods", method)
		self.assertNotIn("confidence", method)

		method_response = self.get(
			self.discovery_path("method", "frappe.tests.test_api.test"), {"sid": self.sid}
		)
		self.assertEqual(method_response.status_code, 200)
		data = method_response.json["data"]
		self.assertEqual(data["path"], "frappe.tests.test_api.test")
		self.assertNotIn("confidence", data)
		self.assertNotIn("resolved_path", data)
		self.assertNotIn("source", data)
		self.assertNotIn("module", data)
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

	def test_cold_cache_returns_retryable_response_v2(self):
		discovery.clear_cache()
		with suppress_stdout():
			response = self.get(self.discovery_path(), {"sid": self.sid})
		self.assertEqual(response.status_code, 503)
		self.assertNotIn("Retry-After", response.headers)


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
	frappe.db.commit()


@whitelist_for_tests()
def test(*, fail: int | bool = False, handled: int | bool = True, message: str = "Failed"):
	if fail:
		if handled:
			frappe.throw(message)
		else:
			1 / 0
	else:
		frappe.msgprint(message)
