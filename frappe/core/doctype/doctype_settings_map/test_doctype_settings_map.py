# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt
"""Tests for the DocTypeSettingsMap controller.

Covers only the controller's own non-trivial logic — single-active reconciliation between
a doctype's custom and standard maps, the developer-mode guard on standard maps, and the
on-trash fallback. Autoname/uniqueness are thin wrappers over framework behaviour and
aren't re-tested.

Test setup runs with `in_migrate` on (so standard maps, which are dev-mode-locked, can be
written) and `developer_mode` off (so inserting a standard map does NOT export a JSON
fixture into the app folder). All maps target "User".
"""

import frappe
from frappe.tests import IntegrationTestCase

CUSTOM_NAME = "User"
STANDARD_NAME = "User (Standard)"


class IntegrationTestDocTypeSettingsMap(IntegrationTestCase):
	def setUp(self):
		self._developer_mode = frappe.conf.developer_mode
		frappe.conf.developer_mode = 0  # keep standard-map inserts from writing to disk
		frappe.flags.in_migrate = True  # let the standard-map guard pass
		frappe.db.delete("DocType Settings Map", {"applies_to_doctype": "User"})

	def tearDown(self):
		frappe.db.delete("DocType Settings Map", {"applies_to_doctype": "User"})
		frappe.flags.in_migrate = False
		frappe.conf.developer_mode = self._developer_mode

	def make_map(self, is_standard=0, is_active=1):
		doc = frappe.get_doc(
			{
				"doctype": "DocType Settings Map",
				"applies_to_doctype": "User",
				"is_standard": is_standard,
				"is_active": is_active,
				"mappings": [],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_activating_a_map_deactivates_its_sibling(self):
		"""Only one map per doctype may be active — activating one turns the other off.

		A doctype can carry both a shipped (standard) and a user (custom) map; the General
		tab reads exactly one, so activation must reconcile the pair.
		"""
		custom = self.make_map(is_standard=0, is_active=0)
		self.make_map(is_standard=1, is_active=1)

		# Inserting the standard map reconciled the custom row (set its is_active), bumping
		# its timestamp — refresh before editing so the save isn't rejected as stale.
		custom.reload()
		custom.is_active = 1
		custom.save(ignore_permissions=True)

		self.assertEqual(
			frappe.db.get_value("DocType Settings Map", CUSTOM_NAME, "is_active"),
			1,
			"the map just activated should be active",
		)
		self.assertEqual(
			frappe.db.get_value("DocType Settings Map", STANDARD_NAME, "is_active"),
			0,
			"activating custom must deactivate the standard sibling",
		)

	def test_deactivating_the_only_active_map_falls_back_to_standard(self):
		"""Deactivating the active custom map re-activates the standard one.

		A doctype should never be left with no active map when a shipped fallback exists —
		otherwise the General tab would silently vanish.
		"""
		custom = self.make_map(is_standard=0, is_active=1)
		self.make_map(is_standard=1, is_active=0)

		custom.reload()
		custom.is_active = 0
		custom.save(ignore_permissions=True)

		self.assertEqual(
			frappe.db.get_value("DocType Settings Map", STANDARD_NAME, "is_active"),
			1,
			"standard sibling should be promoted when nothing else is active",
		)

	def test_standard_map_is_locked_outside_developer_mode(self):
		"""Standard maps ship with an app and must not be editable on a normal site.

		The guard keeps a shipped fixture from being mutated (and re-exported) except in
		developer mode or during migrate/install.
		"""
		standard = self.make_map(is_standard=1, is_active=1)

		# Leave the guarded context: not developer_mode (already off), not migrate/install.
		frappe.flags.in_migrate = False
		try:
			standard.reload()
			standard.is_active = 0
			with self.assertRaises(frappe.PermissionError):
				standard.save(ignore_permissions=True)
		finally:
			frappe.flags.in_migrate = True  # restore for tearDown cleanup

	def test_deleting_active_map_promotes_a_sibling(self):
		"""Trashing the active map activates a remaining sibling (standard preferred).

		Same invariant as deactivation — a surviving map should take over rather than leave
		the doctype with none active.
		"""
		custom = self.make_map(is_standard=0, is_active=1)
		self.make_map(is_standard=1, is_active=0)

		custom.delete(ignore_permissions=True)

		self.assertEqual(
			frappe.db.get_value("DocType Settings Map", STANDARD_NAME, "is_active"),
			1,
			"remaining sibling should be promoted on delete",
		)
