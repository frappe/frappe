import json
import sys
import typing
from contextlib import contextmanager
from functools import cached_property
from random import choice
from threading import Thread
from time import time
from unittest.mock import patch
from urllib.parse import urlencode, urljoin

import requests
from filetype import guess_mime
from werkzeug.test import TestResponse

import frappe
from frappe.installer import update_site_config
from frappe.tests import IntegrationTestCase
from frappe.utils import cint, get_test_client, get_url

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
	target: str,
	args: tuple | None = None,
	kwargs: dict | None = None,
	site: str | None = None,
) -> TestResponse:
	t = ThreadWithReturnValue(target=target, args=args, kwargs=kwargs, site=site)
	t.start()
	t.join()
	return t._return


def patch_request_header(key, *args, **kwargs):
	if key == "Authorization":
		return f"token {authorization_token}"


class ThreadWithReturnValue(Thread):
	def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, site=None):
		if kwargs is None:
			kwargs = {}
		Thread.__init__(self, group, target, name, args, kwargs)
		self._return = None
		self.site = site or _site

	def run(self):
		if self._target is not None:
			with patch("frappe.app.get_site_name", return_value=self.site):
				header_patch = patch("frappe.get_request_header", new=patch_request_header)
				if authorization_token:
					header_patch.start()
				self._return = self._target(*self._args, **self._kwargs)
				if authorization_token:
					header_patch.stop()

	def join(self, *args):
		Thread.join(self, *args)
		return self._return


resource_key = {
	"": "resource",
	"v1": "resource",
	"v2": "document",
}


class FrappeAPITestCase(IntegrationTestCase):
	version = ""  # Empty implies v1
	TEST_CLIENT = get_test_client()

	@property
	def site_url(self):
		return get_url()

	def resource(self, *parts):
		return self.get_path(resource_key[self.version], *parts)

	def method(self, *method):
		return self.get_path("method", *method)

	def doctype_path(self, *method):
		return self.get_path("doctype", *method)

	def get_path(self, *parts):
		return urljoin(self.site_url, "/".join(("api", self.version, *parts)))

	@cached_property
	def sid(self) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		set_request(path="/")
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()
		frappe.local.login_manager.login_as("Administrator")
		return frappe.session.sid

	def get(self, path: str, params: dict | None = None, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.get, args=(path,), kwargs={"json": params, **kwargs})

	def post(self, path, data, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.post, args=(path,), kwargs={"json": data, **kwargs})

	def put(self, path, data, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.put, args=(path,), kwargs={"json": data, **kwargs})

	def patch(self, path, data, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.patch, args=(path,), kwargs={"json": data, **kwargs})

	def delete(self, path, **kwargs) -> TestResponse:
		return make_request(target=self.TEST_CLIENT.delete, args=(path,), kwargs=kwargs)

	def tearDown(self) -> None:
		frappe.db.rollback()
		return super().tearDown()


class TestResourceAPI(FrappeAPITestCase):
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

	def test_get_list_debug(self):
		# test 5: fetch response with debug
		with suppress_stdout():
			response = self.get(self.resource(self.DOCTYPE), {"sid": self.sid, "debug": True})
		self.assertEqual(response.status_code, 200)
		self.assertIn("_debug_messages", response.json)
		self.assertIsInstance(response.json["_debug_messages"], str)
		self.assertIsInstance(json.loads(response.json["_debug_messages"]), list)

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

	def test_update_document(self):
		generated_desc = frappe.mock("paragraph")
		data = {"description": generated_desc, "sid": self.sid}
		random_doc = choice(self.GENERATED_DOCUMENTS)

		response = self.put(self.resource(self.DOCTYPE, random_doc), data=data)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["description"], generated_desc)

		response = self.get(self.resource(self.DOCTYPE, random_doc))
		self.assertEqual(response.json["data"]["description"], generated_desc)

	def test_delete_document(self):
		doc_to_delete = choice(self.GENERATED_DOCUMENTS)
		response = self.delete(self.resource(self.DOCTYPE, doc_to_delete))
		self.assertEqual(response.status_code, 202)
		self.assertDictEqual(response.json, {"data": "ok"})

		response = self.get(self.resource(self.DOCTYPE, doc_to_delete))
		self.assertEqual(response.status_code, 404)
		self.GENERATED_DOCUMENTS.remove(doc_to_delete)

	def test_run_doc_method(self):
		# test 10: Run whitelisted method on doc via /api/resource
		# status_code is 403 if no other tests are run before this - it's not logged in
		self.post(self.resource("Website Theme", "Standard"), {"run_method": "get_apps"})
		response = self.get(self.resource("Website Theme", "Standard"), {"run_method": "get_apps"})

		self.assertIn(response.status_code, (403, 200))

		if response.status_code == 403:
			self.assertTrue(set(response.json.keys()) == {"exc_type", "exception", "exc", "_server_messages"})
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
	def test_ping(self):
		# test 2: test for /api/method/ping
		response = self.get(self.method("ping"))
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertEqual(response.json["message"], "pong")

	def test_get_user_info(self):
		# test 3: test for /api/method/frappe.realtime.get_user_info
		response = self.get(self.method("frappe.realtime.get_user_info"))
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIn(response.json.get("message").get("user"), ("Administrator", "Guest"))

	def test_auth_cycle(self):
		# test 4: Pass authorization token in request
		global authorization_token
		generate_admin_keys()
		user = frappe.get_doc("User", "Administrator")
		api_key, api_secret = user.api_key, user.get_password("api_secret")
		authorization_token = f"{api_key}:{api_secret}"
		response = self.get(self.method("frappe.auth.get_logged_user"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"], "Administrator")

		authorization_token = f"{api_key}:INCORRECT"
		response = self.get(self.method("frappe.auth.get_logged_user"))
		self.assertEqual(response.status_code, 401)

		authorization_token = "NonExistentKey:INCORRECT"
		response = self.get(self.method("frappe.auth.get_logged_user"))
		self.assertEqual(response.status_code, 401)

		authorization_token = None

	def test_404s(self):
		response = self.get(self.get_path("rest"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)
		response = self.get(self.resource("User", "NonExistent@s.com"), {"sid": self.sid})
		self.assertEqual(response.status_code, 404)

	def test_logs(self):
		method = "frappe.tests.test_api.test"

		def get_message(resp, msg_type):
			return frappe.parse_json(frappe.parse_json(frappe.parse_json(resp.json)[msg_type])[0])

		expected_message = "Failed"
		response = self.get(self.method(method), {"sid": self.sid, "message": expected_message})
		self.assertEqual(get_message(response, "_server_messages").message, expected_message)

		# Cause handled failured
		with suppress_stdout():
			response = self.get(
				self.method(method), {"sid": self.sid, "message": expected_message, "fail": True}
			)
		self.assertEqual(get_message(response, "_server_messages").message, expected_message)
		self.assertEqual(response.json["exc_type"], "ValidationError")
		self.assertIn("Traceback", response.json["exc"])

		# Cause handled failured
		with suppress_stdout():
			response = self.get(
				self.method(method),
				{"sid": self.sid, "message": expected_message, "fail": True, "handled": False},
			)
		self.assertNotIn("_server_messages", response.json)
		self.assertIn("ZeroDivisionError", response.json["exception"])  # WHY?
		self.assertIn("Traceback", response.json["exc"])

	def test_array_response(self):
		method = "frappe.tests.test_api.test_array"

		test_data = list(range(5))
		response = self.post(self.method(method), test_data)

		self.assertEqual(response.json["message"], test_data)


class TestReadOnlyMode(FrappeAPITestCase):
	"""During migration if read only mode can be enabled.
	Test if reads work well and writes are blocked"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		update_site_config("allow_reads_during_maintenance", 1)
		cls.addClassCleanup(update_site_config, "maintenance_mode", 0)
		# XXX: this has potential to crumble rest of the test suite.
		update_site_config("maintenance_mode", 1)

	def test_reads(self):
		response = self.get(self.resource("ToDo"), {"sid": self.sid})
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json, dict)
		self.assertIsInstance(response.json["data"], list)

	def test_blocked_writes(self):
		with suppress_stdout():
			response = self.post(
				self.resource("ToDo"), {"description": frappe.mock("paragraph"), "sid": self.sid}
			)
		self.assertEqual(response.status_code, 503)
		self.assertEqual(response.json["exc_type"], "InReadOnlyMode")


class TestWSGIApp(FrappeAPITestCase):
	def test_request_hooks(self):
		self.addCleanup(lambda: _test_REQ_HOOK.clear())

		with self.patch_hooks(
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


class TestResponse(FrappeAPITestCase):
	def test_generate_pdf(self):
		response = self.get(
			"/api/method/frappe.utils.print_format.download_pdf",
			{"sid": self.sid, "doctype": "User", "name": "Guest"},
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.headers["content-type"], "application/pdf")
		self.assertGreater(cint(response.headers["content-length"]), 0)

		self.assertEqual(guess_mime(response.data), "application/pdf")

	def test_binary_and_csv_response(self):
		def download_template(file_type):
			filters = json.dumps({})
			fields = json.dumps({"User": ["name"]})
			return self.post(
				"/api/method/frappe.core.doctype.data_import.data_import.download_template",
				{
					"sid": self.sid,
					"doctype": "User",
					"export_fields": fields,
					"export_filters": filters,
					"file_type": file_type,
				},
			)

		response = download_template("Excel")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.headers["content-type"], "application/octet-stream")
		self.assertGreater(cint(response.headers["content-length"]), 0)
		self.assertEqual(
			guess_mime(response.data), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
		)

		response = download_template("CSV")
		self.assertEqual(response.status_code, 200)
		self.assertIn("text/csv", response.headers["content-type"])
		self.assertGreater(cint(response.headers["content-length"]), 0)

		from frappe.desk.utils import provide_binary_file
		from frappe.utils.response import build_response

		filename = "دفتر الأستاذ العام"
		encoded_filename = filename.encode("utf-8").decode("unicode-escape", "ignore") + ".xlsx"
		provide_binary_file(filename, "xlsx", "content")

		response = build_response("binary")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.headers["content-type"], "application/octet-stream")
		self.assertGreater(cint(response.headers["content-length"]), 0)
		self.assertEqual(response.headers["content-disposition"], f'filename="{encoded_filename}"')

	def test_download_private_file_with_unique_url(self):
		test_content = frappe.generate_hash()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": test_content,
				"content": test_content,
				"is_private": 1,
			}
		)
		file.insert()

		self.assertEqual(self.get(file.unique_url, {"sid": self.sid}).text, test_content)
		self.assertEqual(self.get(file.file_url, {"sid": self.sid}).text, test_content)

	def test_login_redirects(self):
		expected_redirects = {
			"/app/user": "/app/user",
			"/app/user?enabled=1": "/app/user?enabled=1",
			"http://example.com": "/app",  # No external redirect
			"https://google.com": "/app",
			"http://localhost:8000": "/app",
			"http://localhost/app": "http://localhost/app",
		}
		for redirect, expected_redirect in expected_redirects.items():
			response = self.get(f"/login?{urlencode({'redirect-to':redirect})}", {"sid": self.sid})
			self.assertEqual(response.location, expected_redirect)


def generate_admin_keys():
	from frappe.core.doctype.user.user import generate_keys

	generate_keys("Administrator")
	frappe.db.commit()


@frappe.whitelist()
def test(*, fail=False, handled=True, message="Failed"):
	if fail:
		if handled:
			frappe.throw(message)
		else:
			1 / 0
	else:
		frappe.msgprint(message)


@frappe.whitelist(allow_guest=True)
def test_array(data):
	return data
