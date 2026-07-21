# Copyright (c) 2021, FOSS United and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDiscussionReply(FrappeTestCase):
	def make_reply(self, reply):
		topic = frappe.get_doc({"doctype": "Discussion Topic", "title": "Test Topic"}).insert(
			ignore_permissions=True
		)
		with patch.object(frappe, "publish_realtime") as mock_publish:
			doc = frappe.get_doc({"doctype": "Discussion Reply", "topic": topic.name, "reply": reply}).insert(
				ignore_permissions=True
			)

		update_calls = [
			call for call in mock_publish.call_args_list if call.kwargs.get("event") == "update_message"
		]
		self.assertEqual(len(update_calls), 1, "expected exactly one update_message realtime event")
		rendered = update_calls[0].kwargs["message"]["reply"]
		return doc, rendered

	def test_common_markdown_formatting_is_preserved(self):
		reply = (
			"**bold text**, *italic text*, and a [real link](https://frappe.io).\n\n"
			"```python\nprint('hello')\n```"
		)
		_, rendered = self.make_reply(reply)

		self.assertIn("<strong>bold text</strong>", rendered)
		self.assertIn("<em>italic text</em>", rendered)
		self.assertIn('<a href="https://frappe.io"', rendered)
		self.assertIn("real link</a>", rendered)
		self.assertIn("<code", rendered)
		self.assertIn("print('hello')", rendered)

	def test_javascript_uri_link_is_neutralised(self):
		reply = "[clickme](javascript:alert(document.cookie))"
		_, rendered = self.make_reply(reply)

		self.assertNotIn("javascript:", rendered)
		self.assertIn("clickme</a>", rendered)

	def test_script_tag_is_neutralised(self):
		reply = "before <script>alert(document.cookie)</script> after"
		_, rendered = self.make_reply(reply)

		self.assertNotIn("<script>", rendered)
		self.assertIn("&lt;script&gt;", rendered)
		self.assertIn("before", rendered)
		self.assertIn("after", rendered)
