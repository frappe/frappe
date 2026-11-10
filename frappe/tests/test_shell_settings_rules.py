# The settings dialog's rules, run by save, by import, after migrate and by the merge.

import json
import os
from unittest.mock import patch

import frappe
from frappe.desk.doctype.settings_dialog.settings_dialog import SettingsDialog
from frappe.desk.doctype.settings_dialog.test_settings_dialog import (
	EXTENDER,
	HOST,
	SettingsDialogTestCase,
	authoring,
	bound,
	component,
	ship,
	single,
)
from frappe.desk.settings_block import native_row
from frappe.desk.settings_rules import SettingsRules, is_strict
from frappe.shell.settings import check_shipped_records, merge_shipped
from frappe.shell.settings_snapshot import check_settings_snapshot
from frappe.tests.test_shell_settings import active, unchecked

SNAPSHOT = frappe.get_app_path("frappe", "tests", "data", "settings_panes_frappe.json")


def problems_of(doc, panes=None) -> list:
	rules = SettingsRules()
	return [*rules.record_problems(doc), *rules.vet(panes, [doc]).problems]


class TestSettingsRules(SettingsDialogTestCase):
	def test_every_shipped_block_of_every_active_app_survives_the_merge(self):
		panes, problems = merge_shipped()

		self.assertEqual([problem.message for problem in problems], [])
		shipped = frappe.db.count("Settings Block", {"parenttype": "Settings Dialog"})
		self.assertGreater(len(panes), 0)
		self.assertLessEqual(sum(len(pane["blocks"]) for pane in panes), shipped)

	def test_frappes_resolved_panes_match_the_snapshot(self):
		check_settings_snapshot(self, "frappe", SNAPSHOT)

	def test_a_problem_names_the_app_record_pane_block_and_row(self):
		with authoring():
			doc = ship(["general"], [single("Bad Key")], insert=False)
			doc.name = HOST

		(problem,) = problems_of(doc, {"general"})
		self.assertEqual(
			(problem.app, problem.record, problem.pane, problem.key, problem.idx),
			(HOST, HOST, "general", "Bad Key", 1),
		)
		for part in (HOST, "pane general", "block Bad Key", "row 1"):
			self.assertIn(part, problem.message)

	def test_import_checks_a_record_that_skips_validate(self):
		with authoring():
			doc = ship(["general"], [single("Bad Key")], insert=False)

		with self.assertRaises(frappe.ValidationError):
			doc.run_method("before_import")

	def test_a_production_migrate_logs_the_error_and_goes_on(self):
		with authoring():
			doc = ship(["general"], [single("Bad Key")], insert=False)

		with (
			patch("frappe.desk.settings_rules.is_strict", return_value=False),
			patch("builtins.print") as printed,
			patch("frappe.log_error") as logged,
		):
			doc.run_method("before_import")

		self.assertIn("Bad Key", printed.call_args.args[0])
		self.assertIn("Bad Key", logged.call_args.kwargs["message"])

	def test_strict_in_developer_mode_in_tests_and_in_ci(self):
		with patch.object(frappe, "in_test", False), patch.dict(os.environ, {"CI": ""}):
			with patch.dict(frappe.conf, {"developer_mode": 0}):
				self.assertFalse(is_strict())
			with patch.dict(frappe.conf, {"developer_mode": 1}):
				self.assertTrue(is_strict())
			with patch.dict(os.environ, {"CI": "true"}), patch.dict(frappe.conf, {"developer_mode": 0}):
				self.assertTrue(is_strict())

		self.assertTrue(is_strict())

	def test_after_migrate_finds_an_extender_pane_the_host_lacks(self):
		with authoring():
			ship(["general"], [single("system")])
			unchecked(
				ship(blocks=[component("calls", pane="gone")], app=EXTENDER, extends=HOST, insert=False)
			)

		with active(HOST, EXTENDER), self.assertRaisesRegex(frappe.ValidationError, "pane gone"):
			check_shipped_records()

	def test_after_migrate_finds_two_apps_owning_a_field(self):
		with authoring():
			ship(["general"], [bound("phone", saves_fields='["mobile_no"]')])
			unchecked(
				ship(
					blocks=[bound("calls", saves_fields='["mobile_no"]')],
					app=EXTENDER,
					extends=HOST,
					insert=False,
				)
			)

		with active(HOST, EXTENDER), self.assertRaisesRegex(frappe.ValidationError, "mobile_no"):
			check_shipped_records()

	def test_after_migrate_is_quiet_when_the_records_agree(self):
		with authoring():
			ship(["general"], [single("system")])

		with active(HOST):
			check_shipped_records()

	def test_a_component_needs_its_file_in_a_module_of_its_app(self):
		with authoring():
			doc = ship(["general"], [component("no-such-file")], insert=False)

		with patch("frappe.get_installed_apps", return_value=["frappe"]):
			doc.app = "frappe"
			(problem,) = problems_of(doc, {"general"})
			self.assertIn("no-such-file.vue", problem.message)

			doc.blocks[0].component = "theme"
			self.assertEqual(problems_of(doc, {"general"}), [])

	def test_a_wrong_pane_on_an_extending_record_is_reported_not_silent(self):
		with authoring():
			ship(["general"], [single("system")])
			unchecked(
				ship(blocks=[component("calls", pane="gone")], app=EXTENDER, extends=HOST, insert=False)
			)

		with active(HOST, EXTENDER):
			_panes, problems = merge_shipped()

		self.assertEqual([(problem.key, problem.across) for problem in problems], [("calls", True)])

	def test_a_role_a_later_fixture_makes_does_not_stop_the_import(self):
		with authoring():
			doc = ship(["general"], [component("theme", roles='["Role From A Fixture"]')], insert=False)

		doc.run_method("before_import")

	def test_after_migrate_finds_a_role_that_still_does_not_exist(self):
		with authoring():
			unchecked(ship(["general"], [component("theme", roles='["No Such Role"]')], insert=False))

		with active(HOST), self.assertRaisesRegex(frappe.ValidationError, "No Such Role"):
			check_shipped_records()

	def test_a_production_migrate_logs_a_missing_role_and_goes_on(self):
		with authoring():
			unchecked(ship(["general"], [component("theme", roles='["No Such Role"]')], insert=False))

		with (
			active(HOST),
			patch("frappe.desk.settings_rules.is_strict", return_value=False),
			patch("builtins.print") as printed,
			patch("frappe.log_error") as logged,
		):
			check_shipped_records()
			panes, _problems = merge_shipped()

		self.assertIn("No Such Role", printed.call_args.args[0])
		self.assertIn("No Such Role", logged.call_args.kwargs["message"])
		self.assertNotIn("theme", [block["key"] for pane in panes for block in pane["blocks"]])

	def test_a_block_of_an_uninstalled_doctype_is_left_out_with_no_problem(self):
		with authoring():
			doc = ship(
				["general"],
				[single("gone", doctype="Not Installed Anywhere", roles='["No Such Role"]')],
				insert=False,
			)

		self.assertEqual(problems_of(doc, {"general"}), [])
		self.assertEqual(
			[block.key for block in SettingsRules().vet({"general"}, [doc]).unavailable], ["gone"]
		)

	def test_a_json_column_that_is_not_a_string_is_a_problem_not_a_crash(self):
		with authoring():
			doc = ship(["general"], [component("theme")], insert=False)

		doc.blocks[0].roles = ["System Manager"]
		(problem,) = problems_of(doc, {"general"})
		self.assertEqual(problem.title, "Invalid JSON")

	def test_save_refuses_a_block_that_clashes_with_a_shipped_record(self):
		with authoring():
			ship(["general"], [single("system")])
			doc = ship(blocks=[single("system")], app=EXTENDER, extends=HOST, insert=False)
			with self.assertRaisesRegex(frappe.ValidationError, "already ships a block"):
				doc.insert()

	def test_import_reads_the_old_shape_and_native_json(self):
		old = {"key": "theme", "pane": "general", "component": "theme", "settings": '[{"label": "Theme"}]'}
		new = {
			"key": "theme",
			"pane": "general",
			"kind": "Component",
			"component": "theme",
			"search_entries": [{"label": "Theme"}],
			"saves_fields": ["language"],
			"bindings": {"user": {"type": "Record", "doctype": "User", "resolver": "session_user"}},
			"roles": ["System Manager"],
		}
		for block in (old, new):
			with self.subTest(block=block):
				docdict = {"doctype": "Settings Dialog", "blocks": [block]}
				SettingsDialog.prepare_for_import(docdict)
				row = docdict["blocks"][0]
				self.assertEqual(row["kind"], "Component")
				self.assertEqual(json.loads(row["search_entries"]), [{"label": "Theme"}])
				self.assertNotIn("settings", row)

	def test_export_writes_native_json_and_no_blank_column(self):
		row = native_row(
			{"key": "theme", "binding_type": "", "roles": '["System Manager"]', "saves_fields": "not json"}
		)
		self.assertEqual(row, {"key": "theme", "roles": ["System Manager"], "saves_fields": "not json"})

	def test_a_block_must_match_its_kind(self):
		with authoring():
			for block in (
				single("both", component="theme"),
				single("with-entries", search_entries='[{"label": "Theme"}]'),
				{**component("shows", fields='["a"]')},
				{**component("bound-doctype"), "document_type": "User"},
				{**component("odd"), "kind": "Other"},
			):
				with self.subTest(block=block["key"]):
					self.assertRaises(frappe.ValidationError, ship, ["general"], [block])
