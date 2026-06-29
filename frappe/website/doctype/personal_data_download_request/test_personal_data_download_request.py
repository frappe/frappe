# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.contacts.doctype.contact.contact import get_contact_name
from frappe.core.doctype.user.user import create_contact
from frappe.tests import IntegrationTestCase
from frappe.website.doctype.personal_data_download_request.personal_data_download_request import (
	get_user_data,
)


class TestRequestPersonalData(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		create_user_if_not_exists(email="test_privacy@example.com")

	def tearDown(self):
		frappe.db.delete("Personal Data Download Request")
		frappe.set_user("Administrator")

	def test_user_data_creation(self):
		user_data = json.loads(get_user_data("test_privacy@example.com"))
		contact_name = get_contact_name("test_privacy@example.com")
		expected_data = {"Contact": frappe.get_all("Contact", {"name": contact_name}, ["*"])}
		expected_data = json.loads(json.dumps(expected_data, default=str))
		self.assertEqual({"Contact": user_data["Contact"]}, expected_data)

	def test_file_and_email_creation(self):
		frappe.set_user("test_privacy@example.com")
		download_request = frappe.get_doc(
			{"doctype": "Personal Data Download Request", "user": "test_privacy@example.com"}
		)
		download_request.save(ignore_permissions=True)

		frappe.set_user("Administrator")

		file_count = frappe.db.count(
			"File",
			{
				"attached_to_doctype": "Personal Data Download Request",
				"attached_to_name": download_request.name,
			},
		)

		self.assertEqual(file_count, 1)

		email_queue = frappe.get_all("Email Queue", fields=["message"], order_by="creation DESC", limit=1)
		self.assertIn(frappe._("Download Your Data"), email_queue[0].message)

		frappe.db.delete("Email Queue")

	def test_large_file_request(self):
		from unittest.mock import patch

		frappe.db.delete("File")
		frappe.db.delete("Email Queue")

		frappe.set_user("test_privacy@example.com")

		with patch("frappe.sendmail"):
			req = frappe.new_doc("Personal Data Download Request")
			req.user = "test_privacy@example.com"
			req.insert(ignore_permissions=True)

			req.generate_file_and_send_mail(
				{
					"data": "x" * (60 * 1024 * 1024)  # 60MB
				}
			)

		files = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Personal Data Download Request",
				"attached_to_name": req.name,
			},
			fields=["file_size"],
		)

		large_files = [f for f in files if f.file_size >= 60 * 1024 * 1024]
		self.assertEqual(len(large_files), 1)


def create_user_if_not_exists(email, first_name=None):
	frappe.delete_doc_if_exists("User", email)

	user = frappe.get_doc(
		{
			"doctype": "User",
			"user_type": "Website User",
			"email": email,
			"send_welcome_email": 0,
			"first_name": first_name or email.split("@", 1)[0],
			"birth_date": frappe.utils.now_datetime(),
		}
	).insert(ignore_permissions=True)
	create_contact(user=user)
