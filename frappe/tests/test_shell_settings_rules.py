# The settings dialog's rules, run by save, by import, after migrate and by the merge.

import os
from unittest.mock import patch

import frappe
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
from frappe.desk.settings_rules import SettingsRules, is_strict
from frappe.shell.settings import check_shipped_records, merge_shipped, resolve_panes
from frappe.shell.settings_snapshot import check_settings_snapshot
from frappe.tests.test_shell_settings import active, unchecked

SNAPSHOT = frappe.get_app_path("frappe", "tests", "data", "settings_panes_frappe.json")


def problems_of(doc, panes=None) -> list:
	rules = SettingsRules()
	return [*rules.record_problems(doc), *rules.vet(panes, [doc]).problems]


class TestSettingsRules(SettingsDialogTestCase):
	def test_every_shipped_block_of_every_active_app_survives_the_merge(self):
		apps = frappe.get_active_apps()
		with patch("frappe.get_active_apps", return_value=apps):
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
			doc = ship(["general"], [component("theme", roles='["No Such Role"]')], insert=False)

		with self.assertRaises(frappe.ValidationError):
			doc.run_method("before_import")

	def test_a_production_migrate_logs_the_error_and_goes_on(self):
		with authoring():
			doc = ship(["general"], [component("theme", roles='["No Such Role"]')], insert=False)

		with (
			patch("frappe.desk.settings_rules.is_strict", return_value=False),
			patch("builtins.print") as printed,
			patch("frappe.log_error") as logged,
		):
			doc.run_method("before_import")

		self.assertIn("No Such Role", printed.call_args.args[0])
		self.assertIn("No Such Role", logged.call_args.kwargs["message"])

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
			ship(["general"], [bound("phone", fields='["mobile_no"]')])
			unchecked(
				ship(
					blocks=[bound("calls", fields='["mobile_no"]')], app=EXTENDER, extends=HOST, insert=False
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
		self.assertEqual(resolve_panes.__name__, "resolve_panes")
