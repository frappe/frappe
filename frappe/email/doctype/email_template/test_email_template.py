# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.email.doctype.email_template.email_template import get_email_template
from frappe.tests import IntegrationTestCase


class TestEmailTemplate(IntegrationTestCase):
	def test_get_email_template_returns_use_html(self):
		html_template = frappe.get_doc(
			doctype="Email Template",
			subject="Hello {{ name }}",
			use_html=1,
			response_html='<div style="border: 1px solid red">Hi {{ name }}</div>',
		).insert(set_name="_Test HTML Email Template")
		text_template = frappe.get_doc(
			doctype="Email Template",
			subject="Hello {{ name }}",
			response="Hi {{ name }}",
		).insert(set_name="_Test Text Email Template")
		user = create_user("email_template_reader@example.com", "Desk User")

		with self.set_user(user.name):
			html = get_email_template(html_template.name, {"name": "test@example.com"})
			text = get_email_template(text_template.name, {"name": "test@example.com"})

		self.assertEqual(html["use_html"], 1)
		self.assertEqual(html["message"], '<div style="border: 1px solid red">Hi test@example.com</div>')
		self.assertEqual(text["use_html"], 0)
		self.assertEqual(text["subject"], "Hello test@example.com")
