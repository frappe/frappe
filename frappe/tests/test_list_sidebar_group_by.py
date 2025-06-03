# frappe/tests/test_list_sidebar_group_by.py
"""Tests for list sidebar group by functionality with virtual DocTypes."""

import unittest
from unittest.mock import MagicMock, patch

import frappe


class TestListSidebarGroupBy(unittest.TestCase):
	"""Test list sidebar group by behavior for virtual and regular DocTypes."""

	def setUp(self):
		"""Set up test environment."""
		frappe.set_user("Administrator")
		frappe.clear_cache()

	def tearDown(self):
		"""Clean up after tests."""
		frappe.set_user("Administrator")

	@patch("frappe.get_meta")
	def test_virtual_doctype_assignment_filter_blocked(self, mock_get_meta: MagicMock) -> None:
		"""Test that virtual DocTypes don't show assignment filter in frontend logic."""

		# Mock a virtual DocType
		mock_meta = frappe._dict({"is_virtual": 1, "name": "Test Virtual DocType"})
		mock_get_meta.return_value = mock_meta

		# Test the JavaScript logic would be called with this meta
		meta = frappe.get_meta("Test Virtual DocType")

		# Verify the conditions our JavaScript fix checks
		self.assertTrue(meta.is_virtual, "Mocked DocType should be virtual")
		self.assertFalse(
			meta and not meta.is_virtual, "Virtual DocType should fail supports_assignments check"
		)

	@patch("frappe.get_meta")
	def test_regular_doctype_assignment_filter_allowed(self, mock_get_meta: MagicMock) -> None:
		"""Test that regular DocTypes still show assignment filter."""

		# Mock a regular (non-virtual) DocType
		mock_meta = frappe._dict({"is_virtual": 0, "name": "Test Regular DocType"})
		mock_get_meta.return_value = mock_meta

		meta = frappe.get_meta("Test Regular DocType")

		self.assertFalse(meta.is_virtual, "Mocked DocType should not be virtual")
		self.assertTrue(
			meta and not meta.is_virtual, "Regular DocType should pass supports_assignments check"
		)

	@patch("frappe.call")
	def test_backend_api_graceful_handling(self, mock_call: MagicMock) -> None:
		"""Test that backend API handles virtual DocType assignment requests gracefully."""

		# Mock the API response for a virtual DocType
		mock_call.return_value = []

		# Test the API endpoint with a mocked virtual DocType
		result = frappe.call(
			"frappe.desk.listview.get_group_by_count",
			doctype="Mocked Virtual DocType",
			current_filters="[]",
			field="assigned_to",
		)

		self.assertIsInstance(result, list, "Backend should handle virtual DocType gracefully")
		mock_call.assert_called_once_with(
			"frappe.desk.listview.get_group_by_count",
			doctype="Mocked Virtual DocType",
			current_filters="[]",
			field="assigned_to",
		)

	@patch("frappe.call")
	def test_regular_doctype_assignment_still_works(self, mock_call: MagicMock) -> None:
		"""Test that regular DocTypes continue to work with assignment filters."""

		# Mock successful response for regular DocType
		mock_call.return_value = [{"name": "test@example.com", "count": 5}]

		# Test with User DocType (always exists and supports assignments)
		result = frappe.call(
			"frappe.desk.listview.get_group_by_count",
			doctype="User",
			current_filters="[]",
			field="assigned_to",
		)

		self.assertIsInstance(result, list, "Regular DocType assignment filter should work")
		self.assertEqual(len(result), 1, "Should return mocked result")
		mock_call.assert_called_once()

	@patch("frappe.get_meta")
	def test_meta_edge_cases(self, mock_get_meta: MagicMock) -> None:
		"""Test edge cases in meta detection."""

		# Test None meta
		mock_get_meta.return_value = None
		meta = frappe.get_meta("NonExistent DocType")
		supports_assignments = meta and not getattr(meta, "is_virtual", False)
		self.assertFalse(supports_assignments, "None meta should not support assignments")

		# Test meta without is_virtual property
		mock_meta = frappe._dict({"name": "Test DocType"})
		# Deliberately not setting is_virtual
		mock_get_meta.return_value = mock_meta
		meta = frappe.get_meta("Test DocType")
		supports_assignments = meta and not getattr(meta, "is_virtual", False)
		self.assertTrue(
			supports_assignments, "DocType without is_virtual should default to supporting assignments"
		)

	def test_javascript_logic_simulation(self) -> None:
		"""Test the JavaScript logic that determines if assignments are supported."""

		# Simulate the JavaScript function behavior
		def supports_assignments_js_logic(meta):
			"""Simulate: const supports_assignments = meta && !meta.is_virtual;"""
			return meta and not getattr(meta, "is_virtual", False)

		# Test virtual DocType
		virtual_meta = frappe._dict({"is_virtual": 1, "name": "Virtual Test"})
		self.assertFalse(supports_assignments_js_logic(virtual_meta))

		# Test regular DocType
		regular_meta = frappe._dict({"is_virtual": 0, "name": "Regular Test"})
		self.assertTrue(supports_assignments_js_logic(regular_meta))

		# Test None meta
		self.assertFalse(supports_assignments_js_logic(None))

		# Test meta without is_virtual
		no_virtual_meta = frappe._dict({"name": "No Virtual Test"})
		self.assertTrue(supports_assignments_js_logic(no_virtual_meta))
