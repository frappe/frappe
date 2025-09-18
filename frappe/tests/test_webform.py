import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response
from frappe.www.list import get_list_context


class TestWebform(IntegrationTestCase):
	def test_webform_publish_functionality(self):
		request_data = frappe.get_doc("Web Form", "request-data")
		# publish webform
		request_data.published = True
		request_data.save()
		set_request(method="GET", path="request-data/new")
		response = get_response()
		self.assertEqual(response.status_code, 200)

		# un-publish webform
		request_data.published = False
		request_data.save()
		response = get_response()
		self.assertEqual(response.status_code, 404)

	def test_get_context_hook_of_webform(self):
		create_custom_doctype()
		create_webform()

		# check context for apps without any hook
		context_list = get_list_context("", "Custom Doctype", "test-webform")
		self.assertFalse(context_list)

		# create a hook to get webform_context
		set_webform_hook(
			"webform_list_context",
			"frappe.www._test._test_webform.webform_list_context",
		)
		# check context for apps with hook
		context_list = get_list_context("", "Custom Doctype", "test-webform")
		self.assertTrue(context_list)


def create_custom_doctype():
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Custom Doctype",
			"module": "Core",
			"custom": 1,
			"fields": [{"label": "Title", "fieldname": "title", "fieldtype": "Data"}],
		}
	).insert(ignore_if_duplicate=True)


def create_webform():
	frappe.get_doc(
		{
			"doctype": "Web Form",
			"module": "Core",
			"title": "Test Webform",
			"route": "test-webform",
			"doc_type": "Custom Doctype",
			"web_form_fields": [
				{
					"doctype": "Web Form Field",
					"fieldname": "title",
					"fieldtype": "Data",
					"label": "Title",
				}
			],
		}
	).insert(ignore_if_duplicate=True)


def set_webform_hook(key, value):
	from frappe import hooks

	# reset hooks
	for hook in "webform_list_context":
		if hasattr(hooks, hook):
			delattr(hooks, hook)

	setattr(hooks, key, value)
	frappe.client_cache.delete_value("app_hooks")
