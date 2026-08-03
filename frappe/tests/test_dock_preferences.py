# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.desktop import get_user_dock_modules, save_dock_preferences
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import clear_module_permission_cache

USER = "test-dock-prefs@example.com"


class TestDockPreferences(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": USER,
					"first_name": "Dock",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert()
		frappe.set_user(USER)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)
		clear_module_permission_cache()

	def test_order_round_trips(self):
		save_dock_preferences(json.dumps(["Website", "Core", "Email"]))
		self.assertEqual([r["module"] for r in get_user_dock_modules()], ["Website", "Core", "Email"])

	def test_hidden_is_stored_not_omitted(self):
		"""An explicitly hidden module has to persist as a row. Storing "hidden" as mere
		absence would let it reappear the moment its app adds another module."""
		save_dock_preferences(
			json.dumps([{"module": "Core", "hidden": 0}, {"module": "Website", "hidden": 1}])
		)
		rows = {r["module"]: r["hidden"] for r in get_user_dock_modules()}
		self.assertEqual(rows["Core"], 0)
		self.assertEqual(rows["Website"], 1)

	def test_plain_names_and_dicts_both_accepted(self):
		save_dock_preferences(json.dumps(["Core", {"module": "Email", "hidden": 1}]))
		rows = {r["module"]: r["hidden"] for r in get_user_dock_modules()}
		self.assertEqual(rows, {"Core": 0, "Email": 1})

	def test_duplicates_are_collapsed(self):
		save_dock_preferences(json.dumps(["Core", "Core", "Email"]))
		self.assertEqual([r["module"] for r in get_user_dock_modules()], ["Core", "Email"])

	def test_unknown_module_is_dropped(self):
		save_dock_preferences(json.dumps(["Core", "No Such Module"]))
		self.assertEqual([r["module"] for r in get_user_dock_modules()], ["Core"])

	def test_curation_cannot_resurface_a_blocked_module(self):
		"""A dock arrangement is a preference, never a way around module visibility."""
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", USER)
		user.append("block_modules", {"module": "Website"})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=USER)
		frappe.set_user(USER)

		save_dock_preferences(json.dumps(["Core", "Website"]))
		self.assertEqual([r["module"] for r in get_user_dock_modules()], ["Core"])

	def test_saving_replaces_rather_than_appends(self):
		"""The client sends the whole arrangement, not a delta -- the shape a Sortable makes."""
		save_dock_preferences(json.dumps(["Core", "Email", "Website"]))
		save_dock_preferences(json.dumps(["Email"]))
		self.assertEqual([r["module"] for r in get_user_dock_modules()], ["Email"])

	def test_boot_exposes_the_curation(self):
		from frappe.boot import get_bootinfo

		save_dock_preferences(json.dumps(["Email", "Core"]))
		boot = get_bootinfo()
		self.assertEqual([r["module"] for r in boot.get("user_dock_modules")], ["Email", "Core"])
