# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.cache_manager import clear_controller_cache
from frappe.desk.doctype.todo.todo import ToDo
from frappe.tests.utils import FrappeTestCase


class TestHooks(FrappeTestCase):
	def test_hooks(self):
		hooks = frappe.get_hooks()
		self.assertTrue(isinstance(hooks.get("app_name"), list))
		self.assertTrue(isinstance(hooks.get("doc_events"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue(
			"frappe.desk.notifications.clear_doctype_notifications"
			in hooks.get("doc_events").get("*").get("on_update")
		)

	def test_override_doctype_class(self):
		from frappe import hooks

		# Set hook
		hooks.override_doctype_class = {"ToDo": ["frappe.tests.test_hooks.CustomToDo"]}

		# Clear cache
		frappe.cache().delete_value("app_hooks")
		clear_controller_cache("ToDo")

		todo = frappe.get_doc(doctype="ToDo", description="asdf")
		self.assertTrue(isinstance(todo, CustomToDo))

	def test_has_permission(self):
		from frappe import hooks

		# Set hook
		address_has_permission_hook = hooks.has_permission.get("Address", [])
		if isinstance(address_has_permission_hook, str):
			address_has_permission_hook = [address_has_permission_hook]

		address_has_permission_hook.append("frappe.tests.test_hooks.custom_has_permission")

		hooks.has_permission["Address"] = address_has_permission_hook

		# Clear cache
		frappe.cache().delete_value("app_hooks")

		# Init User and Address
		username = "test@example.com"
		user = frappe.get_doc("User", username)
		user.add_roles("System Manager")
		address = frappe.new_doc("Address")

		# Test!
		self.assertTrue(frappe.has_permission("Address", doc=address, user=username))

		address.flags.dont_touch_me = True
		self.assertFalse(frappe.has_permission("Address", doc=address, user=username))

	def test_ignore_links_on_delete(self):
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "Test Customer",
			}
		)
		customer.insert()

		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": customer.name,
				"delivery_date": "2022-12-21",
				"items": [
					{
						"item_code": frappe.get_last_doc("Item").name,
						"qty": 1,
						"rate": 100,
					}
				],
			}
		)
		so.insert()

		self.assertRaises(frappe.LinkExistsError, customer.delete)

		event = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "Test Event",
				"starts_on": "2022-12-21",
				"event_type": "Public",
			}
		)
		event.insert()

		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Test ToDo",
				"reference_type": "Event",
				"reference_name": event.name,
			}
		)
		todo.insert()

		event.delete()


def custom_has_permission(doc, ptype, user):
	if doc.flags.dont_touch_me:
		return False


class CustomToDo(ToDo):
	pass
