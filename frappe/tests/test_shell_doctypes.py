# The shell's one cache over DocType rows: owners and the address table, keyed on `metadata_version`.

from unittest.mock import patch

import frappe
from frappe.cache_manager import reset_metadata_version
from frappe.shell import doctypes
from frappe.shell.doctypes import (
	DOCTYPES_CACHE_KEY,
	contents_for_app,
	get_address_table,
	get_doctype_owners,
	get_shell_doctypes,
)
from frappe.shell.links import canonical_path
from frappe.tests import IntegrationTestCase
from frappe.tests.test_shell import SECOND_APP, a_second_app

PROBE = "Shell Cache Probe"
PROBE_RENAMED = "Shell Cache Probe Renamed"
PROBE_MODULE = "Shell Cache Probe Module"


def insert_probe(module: str = "Core", name: str = PROBE):
	return frappe.get_doc(
		doctype="DocType",
		name=name,
		module=module,
		custom=1,
		fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title"}],
		permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
	).insert()


def delete_probes():
	for name in (PROBE, PROBE_RENAMED):
		frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
	frappe.delete_doc("Module Def", PROBE_MODULE, force=True, ignore_missing=True)
	# Deleting a DocType keeps its table. The DDL also commits the deletes, which the
	# test's rollback would otherwise undo, since the inserts were committed by their own DDL.
	for name in (PROBE, PROBE_RENAMED):
		frappe.db.sql_ddl(f"drop table if exists `tab{name}`")


class TestShellDoctypesCache(IntegrationTestCase):
	def setUp(self):
		# An aborted run can leave a probe behind.
		delete_probes()
		self.addCleanup(delete_probes)

	def builds(self):
		"""Counts entry rebuilds; both halves rebuild together, so the owners builder stands in."""
		return patch.object(doctypes, "build_doctype_owners", wraps=doctypes.build_doctype_owners)

	def test_owners_and_the_address_table_share_one_key(self):
		for stale in ("shell_doctype_owners", "shell_address_table_v2"):
			frappe.client_cache.delete_value(stale)
		reset_metadata_version()

		entry = get_shell_doctypes()

		self.assertEqual(frappe.client_cache.get_value(DOCTYPES_CACHE_KEY), entry)
		self.assertIs(get_doctype_owners(), entry["owners"])
		self.assertIs(get_address_table(), entry["table"])
		self.assertEqual(entry["owners"]["User"], "frappe")
		self.assertEqual(entry["table"]["doctypes"]["User"], ["user", "core"])
		for stale in ("shell_doctype_owners", "shell_address_table_v2"):
			self.assertIsNone(frappe.client_cache.get_value(stale))

	def test_a_call_reads_the_version_once(self):
		get_shell_doctypes()
		for call in (lambda: canonical_path("User", "x"), lambda: contents_for_app("frappe")):
			with patch.object(doctypes, "metadata_version", wraps=doctypes.metadata_version) as read:
				call()
			self.assertEqual(read.call_count, 1)

	def test_a_warm_read_does_not_rebuild(self):
		get_shell_doctypes()
		with self.builds() as build:
			get_doctype_owners()
			get_address_table()
		self.assertEqual(build.call_count, 0)

	def test_a_new_doctype_enters_both_halves(self):
		get_shell_doctypes()
		insert_probe()

		self.assertEqual(get_doctype_owners().get(PROBE), "frappe")
		self.assertEqual(get_address_table()["doctypes"].get(PROBE), ["shell-cache-probe", "core"])

	def test_a_saved_doctype_moves_in_the_table(self):
		probe = insert_probe()
		self.assertEqual(get_address_table()["doctypes"][PROBE], ["shell-cache-probe", "core"])

		probe.module = "Desk"
		probe.save()

		self.assertEqual(get_address_table()["doctypes"][PROBE], ["shell-cache-probe", "desk"])

	def test_a_renamed_doctype_moves_in_both_halves(self):
		insert_probe()
		get_shell_doctypes()

		frappe.rename_doc("DocType", PROBE, PROBE_RENAMED, force=True)

		self.assertNotIn(PROBE, get_doctype_owners())
		self.assertNotIn(PROBE, get_address_table()["doctypes"])
		self.assertEqual(get_doctype_owners().get(PROBE_RENAMED), "frappe")
		self.assertIn(PROBE_RENAMED, get_address_table()["doctypes"])

	def test_a_deleted_doctype_leaves_both_halves(self):
		insert_probe()
		self.assertIn(PROBE, get_doctype_owners())

		frappe.delete_doc("DocType", PROBE, force=True)

		self.assertNotIn(PROBE, get_doctype_owners())
		self.assertNotIn(PROBE, get_address_table()["doctypes"])

	def test_a_module_moved_to_another_app_moves_its_doctypes(self):
		with (
			a_second_app(),
			# The invented app has no source dir, so it has no pages for the DocType to be checked against.
			patch("frappe.shell.address_clash.page_files", return_value={}),
		):
			# `custom=1` keeps this off the disk: `on_update` would otherwise rewrite the owning app's modules.txt.
			module = frappe.get_doc(
				doctype="Module Def", module_name=PROBE_MODULE, app_name="frappe", custom=1
			).insert()
			insert_probe(module=module.name)
			self.assertEqual(get_doctype_owners().get(PROBE), "frappe")

			module.app_name = SECOND_APP
			module.save()

			self.assertEqual(get_doctype_owners().get(PROBE), SECOND_APP)

	def test_a_full_cache_clear_rebuilds(self):
		# `install_app`, `remove_app` and `migrate` all end in `frappe.clear_cache()`.
		get_shell_doctypes()
		with self.builds() as build:
			frappe.clear_cache()
			get_shell_doctypes()
		self.assertEqual(build.call_count, 1)

	def test_a_metadata_version_reset_rebuilds(self):
		get_shell_doctypes()
		with self.builds() as build:
			reset_metadata_version()
			get_shell_doctypes()
		self.assertEqual(build.call_count, 1)
