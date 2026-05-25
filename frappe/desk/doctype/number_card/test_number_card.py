# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.doctype.number_card.number_card import get_cards_for_user
from frappe.tests.utils import FrappeTestCase


class TestNumberCard(FrappeTestCase):
	def test_link_search_hides_cards_from_blocked_modules(self):
		user = "test2@example.com"
		blocked_module = "Contacts"
		blocked_card_name = "Test Blocked Module Card"
		allowed_card_name = "Test No Module Card"

		frappe.set_user("Administrator")

		admin_blocked = frappe.get_cached_doc("User", "Administrator").get_blocked_modules()
		self.assertNotIn(blocked_module, admin_blocked, f"{blocked_module} globally blocked — test invalid")

		for card_name in (blocked_card_name, allowed_card_name):
			frappe.delete_doc("Number Card", card_name, ignore_missing=True, force=True)
			self.addCleanup(
				lambda c=card_name: frappe.delete_doc("Number Card", c, ignore_missing=True, force=True)
			)

		user_doc = frappe.get_doc("User", user)
		if blocked_module not in {d.module for d in user_doc.block_modules}:
			user_doc.append("block_modules", {"module": blocked_module})
			user_doc.save(ignore_permissions=True)
			frappe.clear_document_cache("User", user)

		def restore_blocks():
			doc = frappe.get_doc("User", user)
			doc.block_modules = {d for d in doc.block_modules if d.module != blocked_module}
			doc.save(ignore_permissions=True)
			frappe.clear_document_cache("User", user)

		self.addCleanup(restore_blocks)

		frappe.get_doc(
			{
				"doctype": "Number Card",
				"label": blocked_card_name,
				"type": "Document Type",
				"document_type": "ToDo",
				"function": "Count",
				"is_public": 1,
				"module": blocked_module,
			}
		).insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Number Card",
				"label": allowed_card_name,
				"type": "Document Type",
				"document_type": "ToDo",
				"function": "Count",
				"is_public": 1,
			}
		).insert(ignore_permissions=True)

		frappe.set_user(user)
		try:
			blocked_results = get_cards_for_user(
				doctype="Number Card",
				txt=blocked_card_name,
				searchfield="name",
				start=0,
				page_len=20,
				filters={},
			)
			allowed_results = get_cards_for_user(
				doctype="Number Card",
				txt=allowed_card_name,
				searchfield="name",
				start=0,
				page_len=20,
				filters={},
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual([row[0] for row in blocked_results], [])
		self.assertEqual([row[0] for row in allowed_results], [allowed_card_name])
