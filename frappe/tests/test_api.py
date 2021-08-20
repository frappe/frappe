import unittest
from random import choice

import requests
from semantic_version import Version

import frappe
from frappe.utils import get_site_url


def maintain_state(f):
	def wrapper(*args, **kwargs):
		frappe.db.rollback()
		r = f(*args, **kwargs)
		frappe.db.commit()
		return r

	return wrapper


class TestResourceAPI(unittest.TestCase):
	SITE_URL = get_site_url(frappe.local.site)
	RESOURCE_URL = f"{SITE_URL}/api/resource"
	DOCTYPE = "ToDo"
	GENERATED_DOCUMENTS = []

	@classmethod
	@maintain_state
	def setUpClass(self):
		for _ in range(10):
			doc = frappe.get_doc(
				{"doctype": "ToDo", "description": frappe.mock("paragraph")}
			).insert()
			self.GENERATED_DOCUMENTS.append(doc.name)

	@classmethod
	@maintain_state
	def tearDownClass(self):
		for name in self.GENERATED_DOCUMENTS:
			frappe.delete_doc_if_exists(self.DOCTYPE, name)

	@property
	def sid(self):
		if not getattr(self, "_sid", None):
			self._sid = requests.post(
				f"{self.SITE_URL}/api/method/login",
				data={
					"usr": "Administrator",
					"pwd": frappe.conf.admin_password or "admin",
				},
			).cookies.get("sid")

		return self._sid

	def get(self, path, params=""):
		return requests.get(f"{self.RESOURCE_URL}/{path}?sid={self.sid}{params}")

	def post(self, path, data):
		return requests.post(
			f"{self.RESOURCE_URL}/{path}?sid={self.sid}", data=frappe.as_json(data)
		)

	def put(self, path, data):
		return requests.put(
			f"{self.RESOURCE_URL}/{path}?sid={self.sid}", data=frappe.as_json(data)
		)

	def delete(self, path):
		return requests.delete(f"{self.RESOURCE_URL}/{path}?sid={self.sid}")

	def test_unauthorized_call(self):
		# test 1: fetch documents without auth
		response = requests.get(f"{self.RESOURCE_URL}/{self.DOCTYPE}")
		self.assertEqual(response.status_code, 403)

	def test_get_list(self):
		# test 2: fetch documents without params
		response = self.get(self.DOCTYPE)
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json(), dict)
		self.assertIn("data", response.json())

	def test_get_list_limit(self):
		# test 3: fetch data with limit
		response = self.get(self.DOCTYPE, "&limit=2")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()["data"]), 2)

	def test_get_list_dict(self):
		# test 4: fetch response as (not) dict
		response = self.get(self.DOCTYPE, "&as_dict=True")
		json = frappe._dict(response.json())
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json.data, list)
		self.assertIsInstance(json.data[0], dict)

		response = self.get(self.DOCTYPE, "&as_dict=False")
		json = frappe._dict(response.json())
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json.data, list)
		self.assertIsInstance(json.data[0], list)

	def test_get_list_debug(self):
		# test 5: fetch response with debug
		response = self.get(self.DOCTYPE, "&debug=true")
		self.assertEqual(response.status_code, 200)
		self.assertIn("exc", response.json())
		self.assertIsInstance(response.json()["exc"], str)
		self.assertIsInstance(eval(response.json()["exc"]), list)

	def test_get_list_fields(self):
		# test 6: fetch response with fields
		response = self.get(self.DOCTYPE, r'&fields=["description"]')
		self.assertEqual(response.status_code, 200)
		json = frappe._dict(response.json())
		self.assertIn("description", json.data[0])

	def test_create_document(self):
		# test 7: POST method on /api/resource to create doc
		data = {"description": frappe.mock("paragraph")}
		response = self.post(self.DOCTYPE, data)
		self.assertEqual(response.status_code, 200)
		docname = response.json()["data"]["name"]
		self.assertIsInstance(docname, str)
		self.GENERATED_DOCUMENTS.append(docname)

	def test_update_document(self):
		# test 8: PUT method on /api/resource to update doc
		generated_desc = frappe.mock("paragraph")
		data = {"description": generated_desc}
		random_doc = choice(self.GENERATED_DOCUMENTS)
		desc_before_update = frappe.db.get_value(self.DOCTYPE, random_doc, "description")

		response = self.put(f"{self.DOCTYPE}/{random_doc}", data=data)
		self.assertEqual(response.status_code, 200)
		self.assertNotEqual(response.json()["data"]["description"], desc_before_update)
		self.assertEqual(response.json()["data"]["description"], generated_desc)

	def test_delete_document(self):
		# test 9: DELETE method on /api/resource
		doc_to_delete = choice(self.GENERATED_DOCUMENTS)
		response = self.delete(f"{self.DOCTYPE}/{doc_to_delete}")
		self.assertEqual(response.status_code, 202)
		self.assertDictEqual(response.json(), {"message": "ok"})
		self.GENERATED_DOCUMENTS.remove(doc_to_delete)

		non_existent_doc = frappe.generate_hash(length=12)
		response = self.delete(f"{self.DOCTYPE}/{non_existent_doc}")
		self.assertEqual(response.status_code, 404)
		self.assertDictEqual(response.json(), {})


class TestMethodAPI(unittest.TestCase):
	METHOD_URL = f"{get_site_url(frappe.local.site)}/api/method"

	def test_version(self):
		# test 1: test for /api/method/version
		response = requests.get(f"{self.METHOD_URL}/version")
		json = frappe._dict(response.json())

		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json, dict)
		self.assertIsInstance(json.message, str)
		self.assertEqual(Version(json.message), Version(frappe.__version__))

	def test_ping(self):
		# test 2: test for /api/method/ping
		response = requests.get(f"{self.METHOD_URL}/ping")
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json(), dict)
		self.assertEqual(response.json()['message'], "pong")
