import typing
from random import choice
from unittest.mock import patch

import requests

import frappe
from frappe.api import discovery
from frappe.core.doctype.user.user import generate_keys
from frappe.installer import update_site_config
from frappe.tests.test_api import FrappeAPITestCase, make_request, suppress_stdout
from frappe.tests.utils import toggle_test_mode, whitelist_for_tests
from frappe.utils import get_test_client

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


class TestApiV2UpdatePermissions(FrappeAPITestCase):
	version = "v2"

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.user = "api.permissions@example.com"
		self.created_user = not frappe.db.exists("User", self.user)
		if self.created_user:
			frappe.get_doc(
				doctype="User", email=self.user, first_name="API Permissions", send_welcome_email=0
			).insert()
		keys = generate_keys(self.user)
		self.authorization = f"token {keys['api_key']}:{keys['api_secret']}"
		self.names = []
		for allocated_to in (self.user, None):
			doc = frappe.get_doc(
				doctype="ToDo", description="API v2 permission fixture", allocated_to=allocated_to
			).insert()
			self.names.append(doc.name)
		# Requests use a separate connection and must see these fixtures.
		frappe.db.commit()  # nosemgrep

	def tearDown(self):
		try:
			frappe.set_user("Administrator")
			for name in self.names:
				frappe.delete_doc_if_exists("ToDo", name)
			if self.created_user:
				frappe.delete_doc("User", self.user)
			frappe.db.commit()  # nosemgrep
		finally:
			super().tearDown()

	def update_document(self, name, data):
		return make_request(
			get_test_client(use_cookies=False).put,
			args=(self.resource("ToDo", name),),
			kwargs={"json": data, "headers": {"Authorization": self.authorization}},
			site=frappe.local.site,
		)

	def test_update_cannot_grant_access_using_payload(self):
		name = self.names[1]
		for field in ("allocated_to", "assigned_by", "owner"):
			with self.subTest(field=field):
				before = frappe.db.get_value("ToDo", name, field)
				response = self.update_document(name, {field: self.user})
				self.assertEqual(response.status_code, 403)
				self.assertEqual(frappe.db.get_value("ToDo", name, field), before)

	def test_permitted_update_still_succeeds(self):
		name = self.names[0]
		response = self.update_document(name, {"description": "Permitted API update"})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(frappe.db.get_value("ToDo", name, "description"), "Permitted API update")


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
	DESK_USER = "api-discovery-desk-user@example.com"
	WEBSITE_USER = "api-discovery-website-user@example.com"

	@classmethod
	def tearDownClass(cls):
		for user in (cls.DESK_USER, cls.WEBSITE_USER):
			frappe.delete_doc_if_exists("User", user, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self) -> None:
		self.post(self.method("login"), {"sid": self.sid})
		discovery.clear_cache()
		discovery.build_cache()
		return super().setUp()

	def discovery_path(self, *parts):
		return self.get_path("discovery", *parts)

	def user_sid(self, email: str, *roles: str) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "API Discovery User",
					"send_welcome_email": 0,
				}
			)
			user.append_roles(*roles)
			user.insert(ignore_permissions=True)
			# HTTP requests use another connection and must see this user.
			frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit

		set_request(path="/")
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()
		frappe.local.login_manager.login_as(email)
		return frappe.session.sid

	def discovery_paths(self):
		return (
			self.discovery_path(),
			self.discovery_path("search"),
			self.discovery_path("method"),
			self.discovery_path("method", "frappe.tests.test_api.test"),
			self.discovery_path("doctype", "User"),
			self.discovery_path("doctype", "User", "method", "add_comment"),
		)

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

	def test_discovery_allows_desk_user_v2(self):
		sid = self.user_sid(self.DESK_USER, "Website Manager")
		for path in self.discovery_paths():
			with self.subTest(path=path):
				response = self.get(path, {"sid": sid})
				self.assertEqual(response.status_code, 200)

	def test_discovery_rejects_website_user_v2(self):
		sid = self.user_sid(self.WEBSITE_USER)
		for path in self.discovery_paths():
			with self.subTest(path=path):
				with suppress_stdout():
					response = self.get(path, {"sid": sid})
				self.assertEqual(response.status_code, 403)


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
