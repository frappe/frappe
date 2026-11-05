# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from frappe.integrations.doctype.google_contacts.google_contacts import sync_contacts_from_google_contacts


class TestGoogleContactsSync(TestCase):
	"""
	Unit tests for Google Contacts sync (no database needed).
	"""

	MODULE = "frappe.integrations.doctype.google_contacts.google_contacts"

	def _sync(self, insert_side_effect=None):
		account = MagicMock()
		account.name = "Test Account"
		account.pull_from_google_contacts = 1
		account.get_password.return_value = "old-token"

		page = {
			"connections": [
				{"names": [{"givenName": "Ada", "metadata": {"primary": True}}]},
			],
			"nextSyncToken": "new-token",
		}
		client = MagicMock()
		client.people().connections().list().execute.return_value = page

		db = MagicMock()
		self.db = db
		contact = MagicMock()
		contact.insert.side_effect = insert_side_effect

		with (
			patch(f"{self.MODULE}.get_google_contacts_object", return_value=(client, account)),
			patch(f"{self.MODULE}.frappe.get_doc", return_value=contact),
			patch(f"{self.MODULE}.frappe.db", new=db),
			patch(f"{self.MODULE}.frappe.publish_realtime"),
			patch(f"{self.MODULE}._", side_effect=lambda msg: msg),
			patch(f"{self.MODULE}.frappe.utils.now_datetime", return_value="2026-01-01 00:00:00"),
			patch(f"{self.MODULE}.frappe.session", MagicMock(user="Administrator")),
		):
			sync_contacts_from_google_contacts("Test Account")

	def _saved_tokens(self):
		return [call for call in self.db.set_value.call_args_list if call.args[2:3] == ("next_sync_token",)]

	def test_sync_token_saved_after_successful_import(self):
		self._sync()
		self.assertEqual(len(self._saved_tokens()), 1)
		self.assertEqual(self._saved_tokens()[0].args[3], "new-token")
		self.db.commit.assert_called()

	def test_sync_token_not_saved_when_import_aborts(self):
		with self.assertRaises(frappe.ValidationError):
			self._sync(insert_side_effect=frappe.ValidationError("boom"))
		self.assertEqual(self._saved_tokens(), [])
		self.db.commit.assert_not_called()
