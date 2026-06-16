# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.defaults import clear_default, get_global_default, set_global_default
from frappe.tests import IntegrationTestCase
from frappe.utils import cint
from frappe.utils.legacy_gravatar_cleanup import (
	GRAVATAR_DELETION_JOB_ID,
	SKIP_GRAVATAR_DELETION_PROMPT,
	Action,
	delete_gravatar_image_urls,
	has_gravatar_image_urls,
	should_show_gravatar_deletion_prompt,
	skip_gravatar_deletion_prompt_if_no_urls,
	submit_gravatar_deletion_prompt,
)


@contextmanager
def skip_gravatar_deletion_prompt(value):
	previous = get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)
	if cint(value):
		set_global_default(SKIP_GRAVATAR_DELETION_PROMPT, 1)
	else:
		clear_default(SKIP_GRAVATAR_DELETION_PROMPT, parent="__default")
	try:
		yield
	finally:
		if previous is None:
			clear_default(SKIP_GRAVATAR_DELETION_PROMPT, parent="__default")
		else:
			set_global_default(SKIP_GRAVATAR_DELETION_PROMPT, previous)


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
		with skip_gravatar_deletion_prompt(0):
			self.create_gravatar_records()

			self.assertTrue(should_show_gravatar_deletion_prompt())

		with skip_gravatar_deletion_prompt(1):
			self.assertFalse(should_show_gravatar_deletion_prompt())

	def test_gravatar_deletion_prompt_hidden_while_deletion_is_queued(self):
		with skip_gravatar_deletion_prompt(0):
			self.create_gravatar_records()

			with patch("frappe.utils.legacy_gravatar_cleanup.is_job_enqueued", return_value=True) as mock:
				self.assertFalse(should_show_gravatar_deletion_prompt())

			mock.assert_called_once_with(GRAVATAR_DELETION_JOB_ID)
			self.assertEqual(cint(get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)), 0)

	def test_skip_gravatar_deletion_prompt_if_no_urls(self):
		with skip_gravatar_deletion_prompt(0):
			with patch("frappe.utils.legacy_gravatar_cleanup.has_gravatar_image_urls", return_value=False):
				skip_gravatar_deletion_prompt_if_no_urls()

			self.assertEqual(cint(get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)), 1)

	def test_skip_gravatar_deletion_prompt_if_urls_exist(self):
		with skip_gravatar_deletion_prompt(0):
			with patch("frappe.utils.legacy_gravatar_cleanup.has_gravatar_image_urls", return_value=True):
				skip_gravatar_deletion_prompt_if_no_urls()

			self.assertEqual(cint(get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)), 0)

	def test_submit_gravatar_deletion_prompt_delete(self):
		user, contact, lead = self.create_gravatar_records()

		with skip_gravatar_deletion_prompt(0):
			response = submit_gravatar_deletion_prompt(action=Action.DELETE_GRAVATAR_URLS.value)

			self.assertEqual(response, "queued")
			self.assertFalse(frappe.db.get_value("User", user.name, "user_image"))
			self.assertFalse(frappe.db.get_value("Contact", contact.name, "image"))
			if lead:
				self.assertFalse(frappe.db.get_value("Lead", lead.name, "image"))
			self.assertEqual(cint(get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)), 1)

	def test_submit_gravatar_deletion_prompt_keep(self):
		user, contact, lead = self.create_gravatar_records()
		gravatar_url = frappe.db.get_value("User", user.name, "user_image")

		with skip_gravatar_deletion_prompt(0):
			response = submit_gravatar_deletion_prompt(action=Action.KEEP_GRAVATAR_URLS.value)

			self.assertEqual(response, "skipped")
			self.assertEqual(frappe.db.get_value("User", user.name, "user_image"), gravatar_url)
			self.assertEqual(frappe.db.get_value("Contact", contact.name, "image"), gravatar_url)
			if lead:
				self.assertEqual(frappe.db.get_value("Lead", lead.name, "image"), gravatar_url)
			self.assertEqual(cint(get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)), 1)

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
