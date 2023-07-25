import sys
from contextlib import contextmanager
from random import choice
from threading import Thread
from time import time
from unittest.mock import patch

import requests
from semantic_version import Version
from werkzeug.test import TestResponse

import frappe
from frappe.installer import update_site_config
from frappe.tests.utils import FrappeTestCase, patch_hooks
from frappe.utils import get_site_url, get_test_client

try:
	_site = frappe.local.site
except Exception:
	_site = None

authorization_token = None


@contextmanager
def suppress_stdout():
	"""Supress stdout for tests which expectedly make noise
	but that you don't need in tests"""
	sys.stdout = None
	try:
		yield
	finally:
		sys.stdout = sys.__stdout__


def make_request(
	target: str, args: tuple | None = None, kwargs: dict | None = None
) -> TestResponse:
	t = ThreadWithReturnValue(target=target, args=args, kwargs=kwargs)
	t.start()
	t.join()
	return t._return


def patch_request_header(key, *args, **kwargs):
	if key == "Authorization":
		return f"token {authorization_token}"


class ThreadWithReturnValue(Thread):
	def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
		Thread.__init__(self, group, target, name, args, kwargs)
		self._return = None

	def run(self):
		if self._target is not None:
			with patch("frappe.app.get_site_name", return_value=_site):
				header_patch = patch("frappe.get_request_header", new=patch_request_header)
				if authorization_token:
					header_patch.start()
				self._return = self._target(*self._args, **self._kwargs)
				if authorization_token:
					header_patch.stop()

	def join(self, *args):
		Thread.join(self, *args)
		return self._return


class FrappeAPITestCase(FrappeTestCase):
	SITE = frappe.local.site
	SITE_URL = get_site_url(SITE)
	RESOURCE_URL = f"{SITE_URL}/api/resource"
	TEST_CLIENT = get_test_client()

	@property
	def sid(self) -> str:
		if not getattr(self, "_sid", None):
			from frappe.auth import CookieManager, LoginManager
			from frappe.utils import set_request

			set_request(path="/")
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as("Administrator")
			self._sid = frappe.session.sid

		return self._sid

	def get(self, path: str, params: dict | None = None, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.get, args=(path,), kwargs={"data": params, **kwargs})

	def post(self, path, data, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.post, args=(path,), kwargs={"data": data, **kwargs})

	def put(self, path, data, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.put, args=(path,), kwargs={"data": data, **kwargs})

	def delete(self, path, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.delete, args=(path,), kwargs=kwargs)


class TestResourceAPI(FrappeAPITestCase):
	DOCTYPE = "ToDo"
	GENERATED_DOCUMENTS = []

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for _ in range(10):
			doc = frappe.get_doc({"doctype": "ToDo", "description": frappe.mock("paragraph")}).insert()
			cls.GENERATED_DOCUMENTS.append(doc.name)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		for name in cls.GENERATED_DOCUMENTS:
			frappe.delete_doc_if_exists(cls.DOCTYPE, name)
		frappe.db.commit()

	def test_unauthorized_call(self):
		# test 1: fetch documents without auth
		response = requests.get(f"{self.RESOURCE_URL}/{self.DOCTYPE}")
		self.assertEqual(response.status_code, 403)

	def test_get_list(self):
		# test 2: fetch documents without params
		response = self.get(f"/api/resource/{self.DOCTYPE}", {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIn("data", response.json)

	def test_get_list_limit(self):
		# test 3: fetch data with limit
		response = self.get(f"/api/resource/{self.DOCTYPE}", {"sid": self.sid, "limit": 2})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json["data"]), 2)

	def test_get_list_dict(self):
		# test 4: fetch response as (not) dict
		response = self.get(f"/api/resource/{self.DOCTYPE}", {"sid": self.sid, "as_dict": True})
		json = frappe._dict(response.json)
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json.data, list)
		self.assertIsInstance(json.data[0], dict)

		response = self.get(f"/api/resource/{self.DOCTYPE}", {"sid": self.sid, "as_dict": False})
		json = frappe._dict(response.json)
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json.data, list)
		self.assertIsInstance(json.data[0], list)

	def test_get_list_debug(self):
		# test 5: fetch response with debug
		response = self.get(f"/api/resource/{self.DOCTYPE}", {"sid": self.sid, "debug": True})
		self.assertEqual(response.status_code, 200)
		self.assertIn("exc", response.json)
		self.assertIsInstance(response.json["exc"], str)
		self.assertIsInstance(eval(response.json["exc"]), list)

	def test_get_list_fields(self):
		# test 6: fetch response with fields
		response = self.get(
			f"/api/resource/{self.DOCTYPE}", {"sid": self.sid, "fields": '["description"]'}
		)
		self.assertEqual(response.status_code, 200)
		json = frappe._dict(response.json)
		self.assertIn("description", json.data[0])

	def test_create_document(self):
		# test 7: POST method on /api/resource to create doc
		data = {"description": frappe.mock("paragraph"), "sid": self.sid}
		response = self.post(f"/api/resource/{self.DOCTYPE}", data)
		self.assertEqual(response.status_code, 200)
		docname = response.json["data"]["name"]
		self.assertIsInstance(docname, str)
		self.GENERATED_DOCUMENTS.append(docname)

	def test_update_document(self):
		# test 8: PUT method on /api/resource to update doc
		generated_desc = frappe.mock("paragraph")
		data = {"description": generated_desc, "sid": self.sid}
		random_doc = choice(self.GENERATED_DOCUMENTS)
		desc_before_update = frappe.db.get_value(self.DOCTYPE, random_doc, "description")

		response = self.put(f"/api/resource/{self.DOCTYPE}/{random_doc}", data=data)
		self.assertEqual(response.status_code, 200)
		self.assertNotEqual(response.json["data"]["description"], desc_before_update)
		self.assertEqual(response.json["data"]["description"], generated_desc)

	def test_delete_document(self):
		# test 9: DELETE method on /api/resource
		doc_to_delete = choice(self.GENERATED_DOCUMENTS)
		response = self.delete(f"/api/resource/{self.DOCTYPE}/{doc_to_delete}")
		self.assertEqual(response.status_code, 202)
		self.assertDictEqual(response.json, {"message": "ok"})
		self.GENERATED_DOCUMENTS.remove(doc_to_delete)

		non_existent_doc = frappe.generate_hash(length=12)
		with suppress_stdout():
			response = self.delete(f"/api/resource/{self.DOCTYPE}/{non_existent_doc}")
		self.assertEqual(response.status_code, 404)
		self.assertDictEqual(response.json, {})

	def test_run_doc_method(self):
		# test 10: Run whitelisted method on doc via /api/resource
		# status_code is 403 if no other tests are run before this - it's not logged in
		self.post("/api/resource/Website Theme/Standard", {"run_method": "get_apps"})
		response = self.get("/api/resource/Website Theme/Standard", {"run_method": "get_apps"})
		self.assertIn(response.status_code, (403, 200))

		if response.status_code == 403:
			self.assertTrue(
				set(response.json.keys()) == {"exc_type", "exception", "exc", "_server_messages"}
			)
			self.assertEqual(response.json.get("exc_type"), "PermissionError")
			self.assertEqual(
				response.json.get("exception"), "frappe.exceptions.PermissionError: Not permitted"
			)
			self.assertIsInstance(response.json.get("exc"), str)

		elif response.status_code == 200:
			data = response.json.get("data")
			self.assertIsInstance(data, list)
			self.assertIsInstance(data[0], dict)


class TestMethodAPI(FrappeAPITestCase):
	METHOD_PATH = "/api/method"

	def setUp(self):
		if self._testMethodName == "test_auth_cycle":
			from frappe.core.doctype.user.user import generate_keys

			generate_keys("Administrator")
			frappe.db.commit()

	def test_version(self):
		# test 1: test for /api/method/version
		response = self.get(f"{self.METHOD_PATH}/version")
		json = frappe._dict(response.json)

		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json, dict)
		self.assertIsInstance(json.message, str)
		self.assertEqual(Version(json.message), Version(frappe.__version__))

	def test_ping(self):
		# test 2: test for /api/method/ping
		response = self.get(f"{self.METHOD_PATH}/ping")
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertEqual(response.json["message"], "pong")

	def test_get_user_info(self):
		# test 3: test for /api/method/frappe.realtime.get_user_info
		response = self.get(f"{self.METHOD_PATH}/frappe.realtime.get_user_info")
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIn(response.json.get("message").get("user"), ("Administrator", "Guest"))

	def test_auth_cycle(self):
		# test 4: Pass authorization token in request
		global authorization_token
		user = frappe.get_doc("User", "Administrator")
		api_key, api_secret = user.api_key, user.get_password("api_secret")
		authorization_token = f"{api_key}:{api_secret}"
		response = self.get("/api/method/frappe.auth.get_logged_user")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"], "Administrator")

		authorization_token = None


class TestReadOnlyMode(FrappeAPITestCase):
	"""During migration if read only mode can be enabled.
	Test if reads work well and writes are blocked"""

	REQ_PATH = "/api/resource/ToDo"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		update_site_config("allow_reads_during_maintenance", 1)
		cls.addClassCleanup(update_site_config, "maintenance_mode", 0)
		# XXX: this has potential to crumble rest of the test suite.
		update_site_config("maintenance_mode", 1)

	def test_reads(self):
		response = self.get(self.REQ_PATH, {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIsInstance(response.json["data"], list)

	def test_blocked_writes(self):
		response = self.post(self.REQ_PATH, {"description": frappe.mock("paragraph"), "sid": self.sid})
		self.assertEqual(response.status_code, 503)
		self.assertEqual(response.json["exc_type"], "InReadOnlyMode")


class TestWSGIApp(FrappeAPITestCase):
	def test_request_hooks(self):
		self.addCleanup(lambda: _test_REQ_HOOK.clear())

		with patch_hooks(
			{
				"before_request": ["frappe.tests.test_api.before_request"],
				"after_request": ["frappe.tests.test_api.after_request"],
			}
		):
			self.assertIsNone(_test_REQ_HOOK.get("before_request"))
			self.assertIsNone(_test_REQ_HOOK.get("after_request"))
			res = self.get("/api/method/ping")
			self.assertEqual(res.json, {"message": "pong"})
			self.assertLess(_test_REQ_HOOK.get("before_request"), _test_REQ_HOOK.get("after_request"))


_test_REQ_HOOK = {}


def before_request(*args, **kwargs):
	_test_REQ_HOOK["before_request"] = time()


def after_request(*args, **kwargs):
	_test_REQ_HOOK["after_request"] = time()
