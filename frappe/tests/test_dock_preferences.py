# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.desktop import (
	get_dock_curation,
	get_dock_order,
	get_site_dock_layer,
	get_user_dock_layer,
	get_user_dock_modules,
	save_dock_order,
	save_dock_preferences,
)
from frappe.desk.doctype.module_sidebar.test_module_sidebar import make_sidebar, sidebarless_module
from frappe.tests import IntegrationTestCase

USER = "test-dock-prefs@example.com"


class TestDockPreferences(IntegrationTestCase):
	"""The user's own layer, on a site whose `Dock Order` names nothing."""

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


class TestDockSiteLayer(IntegrationTestCase):
	"""The site's arrangement, the user's own on top of it, and what the merge is for.

	Same rule as the sidebar's layers: a layer moves what it names to the front, in its order,
	and leaves everything else following in the order it inherited. What that buys here is the
	thing per-user curation cannot express -- "Accounts first, for everyone" -- without making
	an app's newly installed modules disappear from every site that has used it.
	"""

	MANAGER = "test-dock-manager@example.com"
	DESK_USER = "test-dock-desk-user@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.make_user(self.MANAGER, ["Desk User", "Workspace Manager"])
		self.make_user(self.DESK_USER, ["Desk User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		self.set_site_order([])
		for email in (self.MANAGER, self.DESK_USER):
			frappe.delete_doc("User", email, force=True, ignore_missing=True)

	def make_user(self, email, roles):
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)

	def set_site_order(self, modules):
		"""The site layer as a Workspace Manager would leave it. Administrator holds every role."""
		user = frappe.session.user
		frappe.set_user("Administrator")
		save_dock_order(json.dumps(modules))
		frappe.set_user(user)

	def block_module(self, email, module):
		user = frappe.get_doc("User", email)
		user.append("block_modules", {"module": module})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=email)

	def dock_for(self, email):
		frappe.set_user(email)
		try:
			return get_user_dock_modules()
		finally:
			frappe.set_user("Administrator")

	# -- the merge ----------------------------------------------------------------------

	def test_site_order_applies_to_a_user_who_has_arranged_nothing(self):
		self.set_site_order(["Email", "Core"])
		self.assertEqual([r["module"] for r in self.dock_for(self.DESK_USER)], ["Email", "Core"])

	def test_a_users_own_arrangement_applies_on_top_of_the_sites(self):
		self.set_site_order(["Email", "Core", "Website"])

		frappe.set_user(self.DESK_USER)
		save_dock_preferences(json.dumps(["Website"]))

		# what they named comes first; the site's arrangement of the rest survives underneath
		self.assertEqual([r["module"] for r in self.dock_for(self.DESK_USER)], ["Website", "Email", "Core"])

	def test_a_user_can_unhide_what_the_site_hid(self):
		"""Later layers win on hiding too, which is the whole reason to have a second one."""
		self.set_site_order([{"module": "Email", "hidden": 1}, {"module": "Core", "hidden": 0}])
		self.assertEqual({r["module"]: r["hidden"] for r in self.dock_for(self.DESK_USER)}["Email"], 1)

		frappe.set_user(self.DESK_USER)
		save_dock_preferences(json.dumps([{"module": "Email", "hidden": 0}]))
		self.assertEqual({r["module"]: r["hidden"] for r in self.dock_for(self.DESK_USER)}["Email"], 0)

	def test_a_module_the_site_never_named_is_absent_rather_than_appended(self):
		"""Absence *is* the answer: the arrangement is what to move, not what to show.

		The client keeps a module no layer names in its app's own order, trailing the ones a
		layer did name -- so nothing has to be re-listed for it to keep its default place.
		"""
		self.set_site_order(["Email", "Core"])
		self.assertEqual([r["module"] for r in self.dock_for(self.DESK_USER)], ["Email", "Core"])

	def test_installing_an_app_surfaces_its_module_on_an_already_ordered_dock(self):
		self.set_site_order(["Email", "Core"])

		with sidebarless_module("Test Dock Newcomer"):
			dock = self.dock_for(self.DESK_USER)

		# the new module is named by neither layer, so nothing hides it and nothing pins it
		# behind the arrangement -- it lands after what the site ordered
		self.assertNotIn("Test Dock Newcomer", [r["module"] for r in dock])
		self.assertEqual([r["module"] for r in dock], ["Email", "Core"])

	def test_a_module_the_user_may_not_reach_is_absent_from_the_dock(self):
		"""The dock is navigation reach, never a way around the module gate -- at either layer."""
		self.block_module(self.DESK_USER, "Website")
		self.set_site_order(["Website", "Core"])

		self.assertEqual([r["module"] for r in self.dock_for(self.DESK_USER)], ["Core"])

	# -- the gate -----------------------------------------------------------------------

	def test_only_a_workspace_manager_may_write_the_site_layer(self):
		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, save_dock_order, json.dumps(["Core"]))

		frappe.set_user(self.MANAGER)
		save_dock_order(json.dumps(["Core", "Email"]))
		frappe.set_user("Administrator")
		self.assertEqual([r["module"] for r in get_dock_order()], ["Core", "Email"])

	def test_only_a_workspace_manager_may_read_the_site_layer(self):
		self.set_site_order(["Core"])

		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, get_site_dock_layer)

		frappe.set_user(self.MANAGER)
		self.assertEqual([r["module"] for r in get_site_dock_layer()], ["Core"])

	def test_a_site_save_keeps_rows_for_modules_the_saver_cannot_see(self):
		"""Site intent outlives one manager's blocked module.

		Filtering a site write by the saver's own visibility would let a Workspace Manager who
		happens to be blocked from a module silently delete the site's arrangement of it for
		everyone. Visibility is applied when the dock is resolved instead -- so the row stays,
		and it still does not show up on that manager's own dock.
		"""
		self.block_module(self.MANAGER, "Website")

		frappe.set_user(self.MANAGER)
		save_dock_order(json.dumps(["Website", "Core"]))
		frappe.set_user("Administrator")

		self.assertEqual([r["module"] for r in get_dock_order()], ["Website", "Core"])
		self.assertEqual([r["module"] for r in self.dock_for(self.MANAGER)], ["Core"])
		self.assertEqual([r["module"] for r in self.dock_for(self.DESK_USER)], ["Website", "Core"])

	# -- the seams the client edits through ---------------------------------------------

	def test_the_editor_reads_the_layer_it_will_overwrite(self):
		"""Each layer's read answers with that layer's own rows, never the resolved dock.

		A save replaces a layer whole. Handed the resolved dock, the dock manager would write
		the site's rows into the user's own layer, freezing them out of every later site change.
		"""
		self.set_site_order(["Email", "Core"])

		frappe.set_user(self.DESK_USER)
		save_dock_preferences(json.dumps(["Core"]))

		self.assertEqual([r["module"] for r in get_user_dock_layer()], ["Core"])
		self.assertEqual([r["module"] for r in get_dock_curation()], ["Core"])
		self.assertEqual([r["module"] for r in get_user_dock_modules()], ["Core", "Email"])

	def test_boot_carries_the_resolved_dock(self):
		from frappe.boot import get_bootinfo

		self.set_site_order(["Email", "Core"])

		frappe.set_user(self.DESK_USER)
		self.assertEqual([r["module"] for r in get_bootinfo().get("user_dock_modules")], ["Email", "Core"])

	def test_both_layers_store_the_same_child_doctype(self):
		"""One doctype, because the rows are identical -- the parent is what names the layer."""
		self.assertEqual(frappe.get_meta("User").get_field("dock_modules").options, "Dock Module")
		self.assertEqual(frappe.get_meta("Dock Order").get_field("modules").options, "Dock Module")


class TestTheShippedDockOrder(IntegrationTestCase):
	"""The layer *below* both of the ones above: what the dock reads before anybody arranges it.

	`Dock Order` and `User.dock_modules` are site and user intent, and they can only rearrange
	the list they are given. This is that list -- `boot.get_app_modules` -- and until
	`Module Sidebar.sequence_id` existed the only way an app could state it was the position a
	module happened to occupy in `modules.txt`.
	"""

	def app_order(self, app: str = "frappe") -> list[str]:
		from frappe.boot import get_app_modules

		return get_app_modules(app)

	def position(self, module: str) -> int:
		return self.app_order().index(module)

	def test_a_sequence_pulls_a_module_in_front_of_one_that_declares_none(self):
		with (
			sidebarless_module("Test Sequence Ahead A") as ahead,
			sidebarless_module("Test Sequence Ahead B") as behind,
		):
			# alphabetical to begin with: neither is in modules.txt, so both tie on every key
			# above the name
			self.assertLess(self.position(ahead), self.position(behind))

			make_sidebar(behind, sequence_id=1)
			self.assertLess(self.position(behind), self.position(ahead))

	def test_a_high_sequence_pushes_a_module_behind_one_that_declares_none(self):
		"""What the *middle* default buys: declaring a sequence can say "after the quiet ones"
		as well as "before them". A trailing default could only ever say the first."""
		with (
			sidebarless_module("Test Sequence Behind A") as pushed,
			sidebarless_module("Test Sequence Behind B") as quiet,
		):
			make_sidebar(pushed, sequence_id=500)

			self.assertLess(self.position(quiet), self.position(pushed))

	def test_modules_txt_still_breaks_a_tie(self):
		"""The modules an app says nothing about keep exactly the dock they had, because the
		order it already declared is what the tie falls back to.

		Scoped to the modules with no sidebar document rather than to all of `frappe`'s: the
		ones that *do* have a document are entitled to state a sequence, and asserting over
		them would be asserting that no framework sidebar ever does.
		"""
		declared = frappe.get_module_list("frappe")
		sequenced = set(frappe.get_all("Module Sidebar", pluck="module"))
		quiet = [m for m in self.app_order() if m in declared and m not in sequenced]

		self.assertTrue(quiet, "sanity: some framework module declares no sequence")
		self.assertEqual(quiet, sorted(quiet, key=declared.index))

	def test_a_module_with_no_sidebar_document_takes_the_default(self):
		"""Most modules have a computed base and no document at all, so the default is the
		common case rather than the edge one."""
		from frappe.boot import DEFAULT_MODULE_SEQUENCE_ID

		with sidebarless_module("Test Sequence Defaulted") as module:
			self.assertFalse(frappe.db.exists("Module Sidebar", {"module": module}))
			self.assertIn(module, self.app_order())

			# the same position a document stating the default would put it in
			without = self.position(module)
			make_sidebar(module, sequence_id=DEFAULT_MODULE_SEQUENCE_ID)
			self.assertEqual(self.position(module), without)
