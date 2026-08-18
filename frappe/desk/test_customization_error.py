# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.deferred_insert import save_to_db
from frappe.desk.customization_error import (
	REPORTS_PER_HOUR,
	report_customization_error,
)
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request


def flushed_rows() -> list[frappe._dict]:
	"""The reporter defers, so a test must flush the Redis queue to see its row."""
	save_to_db(doctype="Error Log")
	return frappe.get_all(
		"Error Log",
		fields=[
			"method",
			"error",
			"fingerprint",
			"reference_doctype",
			"reference_name",
			"metadata",
		],
		order_by="creation desc",
	)


class TestCustomizationError(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Error Log")
		frappe.cache.delete_value(f"rl:customization_error:{frappe.session.user}")
		frappe.local.request = None

	def test_page_script_row_carries_a_working_reference(self):
		report_customization_error(
			source="page-script:Refund Button",
			tier="page_script",
			event="refresh",
			doctype="CRM Deal",
			message="x is not a function",
			stack="at refresh (blob:...)",
			record="CRM-DEAL-0001",
			route="/crm2/deals/CRM-DEAL-0001",
		)
		row = flushed_rows()[0]

		self.assertEqual(row.method, "Customization: page-script:Refund Button (refresh)")
		self.assertEqual(row.error, "x is not a function\n\nat refresh (blob:...)")
		self.assertEqual(row.reference_doctype, "Page Script")
		self.assertEqual(row.reference_name, "Refund Button")

		metadata = json.loads(row.metadata)
		self.assertEqual(metadata["tier"], "page_script")
		self.assertEqual(metadata["source"], "page-script:Refund Button")
		self.assertEqual(metadata["record"], {"doctype": "CRM Deal", "name": "CRM-DEAL-0001"})
		self.assertEqual(metadata["route"], "/crm2/deals/CRM-DEAL-0001")

	def test_other_tiers_carry_no_reference(self):
		for tier, source in (("extension", "audit"), ("file_script", "host")):
			with self.subTest(tier=tier):
				frappe.db.delete("Error Log")
				report_customization_error(source=source, tier=tier, event="load", message="boom", stack="")
				row = flushed_rows()[0]
				self.assertEqual(row.method, f"Customization: {source} (load)")
				self.assertFalse(row.reference_doctype)
				self.assertFalse(row.reference_name)

	def test_fingerprint_is_stable_across_differing_stacks(self):
		for stack in ("firefox trace", "chrome trace"):
			report_customization_error(
				source="page-script:A",
				tier="page_script",
				event="refresh",
				doctype="CRM Deal",
				message="boom\nsecond line differs",
				stack=stack,
			)

		rows = flushed_rows()
		self.assertEqual(len(rows), 2)
		self.assertEqual(len({row.fingerprint for row in rows}), 1)

	def test_fingerprint_splits_on_a_different_event(self):
		for event in ("refresh", "after_save"):
			report_customization_error(
				source="page-script:A", tier="page_script", event=event, message="boom", stack=""
			)
		self.assertEqual(len({row.fingerprint for row in flushed_rows()}), 2)

	def test_unknown_tier_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			report_customization_error(source="page-script:A", tier="nonsense", event="refresh")

	def test_guest_is_refused_by_the_whitelist(self):
		self.assertIn(report_customization_error, frappe.whitelisted)
		self.assertNotIn(report_customization_error, frappe.guest_methods)

	def test_rate_limit_stops_a_hand_rolled_caller(self):
		set_request(method="POST", path="/api/method/report_customization_error")
		for index in range(REPORTS_PER_HOUR):
			report_customization_error(source=f"page-script:{index}", tier="page_script", event="refresh")
		with self.assertRaises(frappe.RateLimitExceededError):
			report_customization_error(source="page-script:over", tier="page_script", event="refresh")

	def test_fields_are_truncated_server_side(self):
		report_customization_error(
			source="page-script:A",
			tier="page_script",
			event="refresh",
			message="m" * 5000,
			stack="s" * 9000,
		)
		message, stack = flushed_rows()[0].error.split("\n\n")
		self.assertEqual(len(message), 1000)
		self.assertEqual(len(stack), 4000)

	def test_non_string_field_is_refused_by_the_type_hints(self):
		"""`frappe.whitelist` validates annotated parameters before the body runs, so
		the hints — not a hand-rolled isinstance — are this endpoint's type boundary."""
		with self.assertRaises(frappe.FrappeTypeError):
			report_customization_error(
				source="page-script:A",
				tier="page_script",
				event="refresh",
				message={"not": "a string"},
			)
