# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.integrations.doctype.google_drive.google_drive import authorize_access
from frappe.tests.utils import FrappeTestCase


class TestGoogleDrive(FrappeTestCase):
	def test_authorize_access_requires_write_permission(self):
		frappe.db.set_single_value("Google Drive", "backup_folder_id", "folder")

		with self.set_user("test2@example.com"), self.assertRaises(frappe.PermissionError):
			authorize_access(reauthorize=True)
		self.assertEqual(frappe.db.get_single_value("Google Drive", "backup_folder_id"), "folder")

		with patch("frappe.integrations.doctype.google_drive.google_drive.GoogleOAuth"):
			authorize_access(reauthorize=True)
		self.assertFalse(frappe.db.get_single_value("Google Drive", "backup_folder_id"))
