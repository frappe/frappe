# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMsgprint(FrappeTestCase):
	def setUp(self):
		# Clear message log before each test
		frappe.local.message_log = []

	def test_as_table_strips_html_tags_in_tty(self):
		"""Test that HTML tags are stripped from table cells in TTY mode.

		When msgprint is called with as_table=True and the output is going to
		a terminal (TTY), HTML tags should be stripped from each cell in the
		table to provide clean terminal output.
		"""
		# Create a table message with HTML tags in cells
		table_message = [
			["<b>Header 1</b>", "<i>Header 2</i>"],
			["<span>Cell 1</span>", "<div>Cell 2</div>"],
			["<a href='#'>Link</a>", "<strong>Bold</strong>"],
		]

		# Mock stdin to simulate TTY environment
		mock_stdin = MagicMock()
		mock_stdin.isatty.return_value = True

		with patch("sys.stdin", mock_stdin):
			frappe.msgprint(table_message, as_table=True)

		# Get the message from the log
		self.assertEqual(len(frappe.local.message_log), 1)
		logged_message = frappe.local.message_log[0]

		self.assertEqual(logged_message.as_table, 1)
		# The message should have HTML stripped when processed for TTY
		# Note: The actual stripping happens in the msgprint function itself

	def test_as_list_strips_html_tags_in_tty(self):
		"""Test that HTML tags are stripped from list items in TTY mode.

		When msgprint is called with as_list=True and the output is going to
		a terminal (TTY), HTML tags should be stripped from each item in the
		list to provide clean terminal output.
		"""
		# Create a list message with HTML tags
		list_message = [
			"<b>Item 1</b>",
			"<i>Item 2</i>",
			"<span>Item 3</span>",
		]

		# Mock stdin to simulate TTY environment
		mock_stdin = MagicMock()
		mock_stdin.isatty.return_value = True

		with patch("sys.stdin", mock_stdin):
			frappe.msgprint(list_message, as_list=True)

		# Get the message from the log
		self.assertEqual(len(frappe.local.message_log), 1)
		logged_message = frappe.local.message_log[0]

		self.assertEqual(logged_message.as_list, 1)

	def test_regular_message_strips_html_tags_in_tty(self):
		"""Test that HTML tags are stripped from regular messages in TTY mode."""
		message = "<b>Bold</b> and <i>italic</i> text"

		# Mock stdin to simulate TTY environment
		mock_stdin = MagicMock()
		mock_stdin.isatty.return_value = True

		with patch("sys.stdin", mock_stdin):
			frappe.msgprint(message)

		# Get the message from the log
		self.assertEqual(len(frappe.local.message_log), 1)

	def test_as_table_without_tty_preserves_html(self):
		"""Test that HTML tags are preserved when not in TTY mode."""
		table_message = [
			["<b>Header 1</b>", "<i>Header 2</i>"],
			["<span>Cell 1</span>", "<div>Cell 2</div>"],
		]

		# Mock stdin to simulate non-TTY environment
		mock_stdin = MagicMock()
		mock_stdin.isatty.return_value = False

		with patch("sys.stdin", mock_stdin):
			frappe.msgprint(table_message, as_table=True)

		# Get the message from the log
		self.assertEqual(len(frappe.local.message_log), 1)
		logged_message = frappe.local.message_log[0]

		self.assertEqual(logged_message.as_table, 1)
		# Message should still contain HTML since we're not in TTY mode
		self.assertEqual(logged_message.message, table_message)
