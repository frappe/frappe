# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import change_settings
from frappe.utils import cint
from frappe.utils.legacy_gravatar_cleanup import (
	delete_gravatar_image_urls,
	has_gravatar_image_urls,
	should_show_gravatar_deletion_prompt,
	submit_gravatar_deletion_prompt,
)


class TestGravatarDeletion(IntegrationTestCase):
	def test_delete_gravatar_image_urls(self):
		user, contact, lead = self.create_gravatar_records()

		self.assertTrue(has_gravatar_image_urls())
		delete_gravatar_image_urls()

		self.assertFalse(frappe.db.get_value("User", user.name, "user_image"))
		self.assertFalse(frappe.db.get_value("Contact", contact.name, "image"))
		if lead:
			self.assertFalse(frappe.db.get_value("Lead", lead.name, "image"))

	def test_gravatar_deletion_prompt_depends_on_setting_and_urls(self):
		with change_settings("System Settings", {"skip_gravatar_deletion_prompt": 0}):
			self.create_gravatar_records()

			self.assertTrue(should_show_gravatar_deletion_prompt())

		with change_settings("System Settings", {"skip_gravatar_deletion_prompt": 1}):
			self.assertFalse(should_show_gravatar_deletion_prompt())

	def test_submit_gravatar_deletion_prompt(self):
		user, contact, lead = self.create_gravatar_records()

		with change_settings("System Settings", {"skip_gravatar_deletion_prompt": 0}):
			response = submit_gravatar_deletion_prompt(delete_gravatar_urls=True, skip_prompt=True)

			self.assertTrue(response["queued"])
			self.assertFalse(frappe.db.get_value("User", user.name, "user_image"))
			self.assertFalse(frappe.db.get_value("Contact", contact.name, "image"))
			if lead:
				self.assertFalse(frappe.db.get_value("Lead", lead.name, "image"))
			self.assertEqual(
				cint(frappe.db.get_single_value("System Settings", "skip_gravatar_deletion_prompt")), 1
			)

	def create_gravatar_records(self):
		email = f"gravatar-test-{frappe.generate_hash()}@example.com"
		gravatar_url = f"https://secure.gravatar.com/avatar/{frappe.generate_hash()}"
		user = frappe.get_doc(doctype="User", email=email, first_name="Gravatar").insert(
			ignore_permissions=True
		)
		contact = frappe.get_doc(
			doctype="Contact",
			first_name="Gravatar",
			email_id=email,
			image=gravatar_url,
		).insert(ignore_permissions=True)

		frappe.db.set_value("User", user.name, "user_image", gravatar_url, update_modified=False)

		lead = None
		if "erpnext" in frappe.get_installed_apps():
			lead = frappe.get_doc(
				doctype="Lead",
				first_name="Gravatar",
				last_name="Lead",
				email_id=email,
				company_name="Gravatar Test Co",
				image=gravatar_url,
			).insert(ignore_permissions=True)

		return user, contact, lead
