from unittest.mock import patch

import frappe
from frappe.studio.ai.api import run
from frappe.studio.doctype.studio_app.test_studio_app import make_studio_app, make_studio_page
from frappe.tests import IntegrationTestCase


class TestApi(IntegrationTestCase):
	def setUp(self):
		app = make_studio_app(app_name="ai-" + frappe.generate_hash(length=8))
		self.page = make_studio_page(app.name)

	def test_a_second_turn_is_refused_while_one_is_queued(self):
		with (
			patch("frappe.studio.ai.api.llm.get_api_key", return_value="key"),
			patch("frappe.studio.ai.api.is_job_enqueued", return_value=True),
			patch("frappe.enqueue") as enqueue,
		):
			result = run(prompt="hi", page_context="{}", page_id=self.page.name)

		self.assertEqual(result["status"], "busy")
		self.assertEqual(frappe.local.response.http_status_code, 429)
		enqueue.assert_not_called()
		self.assertFalse(frappe.db.exists("Studio AI Message", {"content": "hi"}))
