import typing
from random import choice

import requests

import frappe
from frappe.installer import update_site_config
from frappe.tests.test_api import FrappeAPITestCase, suppress_stdout

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
	def setUpClass(cls) -> None:
		super().setUpClass()
		for _ in range(20):
			doc = frappe.get_doc({"doctype": "ToDo", "description": frappe.mock("paragraph")}).insert()
			cls.GENERATED_DOCUMENTS = []
			cls.GENERATED_DOCUMENTS.append(doc.name)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls) -> None:
		for name in cls.GENERATED_DOCUMENTS:
			frappe.delete_doc_if_exists(cls.DOCTYPE, name)
		frappe.db.commit()

	def test_unauthorized_call(self) -> None:
		# test 1: fetch documents without auth
		response = requests.get(self.resource(self.DOCTYPE))
		self.assertEqual(response.status_code, 403)

	def test_get_list(self) -> None:
		# test 2: fetch documents without params
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIn("data", response.json)

	def test_get_list_limit(self) -> None:
		# test 3: fetch data with limit
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "limit": 2})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json["data"]), 2)

	def test_get_list_dict(self) -> None:
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

	def test_get_list_fields(self) -> None:
		# test 6: fetch response with fields
		response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "fields": '["description"]'})
		self.assertEqual(response.status_code, 200)
		json = frappe._dict(response.json)
		self.assertIn("description", json.data[0])

	def test_create_document(self) -> None:
		data = {"description": frappe.mock("paragraph"), "sid": self.sid}
		response = self.post(self.resource(self.DOCTYPE), data)
		self.assertEqual(response.status_code, 200)
		docname = response.json["data"]["name"]
		self.assertIsInstance(docname, str)
		self.GENERATED_DOCUMENTS.append(docname)

	def test_delete_document(self) -> None:
		doc_to_delete = choice(self.GENERATED_DOCUMENTS)
		response = self.delete(self.resource(self.DOCTYPE, doc_to_delete))
		self.assertEqual(response.status_code, 202)
		self.assertDictEqual(response.json, {"data": "ok"})

		response = self.get(self.resource(self.DOCTYPE, doc_to_delete))
		self.assertEqual(response.status_code, 404)
		self.GENERATED_DOCUMENTS.remove(doc_to_delete)

	def test_execute_doc_method(self) -> None:
		response = self.get(self.resource("Website Theme", "Standard", "method", "get_apps"))
		self.assertEqual(response.json["data"][0]["name"], "frappe")

	def test_update_document(self) -> None:
		generated_desc = frappe.mock("paragraph")
		data = {"description": generated_desc, "sid": self.sid}
		random_doc = choice(self.GENERATED_DOCUMENTS)

		response = self.patch(self.resource(self.DOCTYPE, random_doc), data=data)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["description"], generated_desc)

		response = self.get(self.resource(self.DOCTYPE, random_doc))
		self.assertEqual(response.json["data"]["description"], generated_desc)

	def test_delete_document_non_existing(self) -> None:
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

	def test_ping(self) -> None:
		response = self.get(self.method("ping"))
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertEqual(response.json["data"], "pong")

	def test_get_user_info(self) -> None:
		response = self.get(self.method("frappe.realtime.get_user_info"))
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIn(response.json.get("data").get("user"), ("Administrator", "Guest"))

	def test_auth_cycle(self) -> None:
		global authorization_token

		generate_admin_keys()
		user = frappe.get_doc("User", "Administrator")
		api_key, api_secret = user.api_key, user.get_password("api_secret")
		authorization_token = f"{api_key}:{api_secret}"
		response = self.get(self.method("frappe.auth.get_logged_user"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"], "Administrator")

		authorization_token = None

	def test_404s(self) -> None:
		response = self.get(self.get_path("rest"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)
		response = self.get(self.resource("User", "NonExistent@s.com"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)

	def test_shorthand_controller_methods(self) -> None:
		shorthand_response = self.get(self.method("User", "get_all_roles"), {"sid": self.sid})
		self.assertIn("Blogger", shorthand_response.json["data"])

		expanded_response = self.get(
			self.method("frappe.core.doctype.user.user.get_all_roles"), {"sid": self.sid}
		)
		self.assertEqual(expanded_response.data, shorthand_response.data)

	def test_logout(self) -> None:
		self.post(self.method("logout"), {"sid": self.sid})
		response = self.get(self.method("ping"))
		self.assertFalse(response.request.cookies["sid"])

	def test_run_doc_method_in_memory(self) -> None:
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

	def test_logs(self) -> None:
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

	def test_add_comment(self) -> None:
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

	def test_meta(self) -> None:
		response = self.get(self.doctype_path("ToDo", "meta"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["name"], "ToDo")

	def test_count(self) -> None:
		response = self.get(self.doctype_path("ToDo", "count"))
		self.assertIsInstance(response.json["data"], int)


class TestReadOnlyMode(FrappeAPITestCase):
	"""During migration if read only mode can be enabled.
	Test if reads work well and writes are blocked"""

	version = "v2"

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		update_site_config("allow_reads_during_maintenance", 1)
		cls.addClassCleanup(update_site_config, "maintenance_mode", 0)
		update_site_config("maintenance_mode", 1)

	def test_reads(self) -> None:
		response = self.get(self.resource("ToDo"), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIsInstance(response.json["data"], list)

	def test_blocked_writes_v2(self) -> None:
		with suppress_stdout():
			response = self.post(
				self.resource("ToDo"), {"description": frappe.mock("paragraph"), "sid": self.sid}
			)
		self.assertEqual(response.status_code, 503)
		self.assertEqual(response.json["errors"][0]["type"], "InReadOnlyMode")


def generate_admin_keys() -> None:
	from frappe.core.doctype.user.user import generate_keys

	generate_keys("Administrator")
	frappe.db.commit()


@frappe.whitelist()
def test(*, fail: bool = False, handled: bool = True, message: str = "Failed") -> None:
	if fail:
		if handled:
			frappe.throw(message)
		else:
			1 / 0
	else:
		frappe.msgprint(message)
