# The sidebar each desk shows: resolved from the arrangement of the app that owns it, validated
# with the path of every mistake, and printed as the text an app's `sidebar.txt` holds.

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.desk.app_prefix import default_prefix
from frappe.desk.doctype.settings_dialog.settings_dialog import SettingsDialog
from frappe.desk.doctype.settings_dialog.test_settings_dialog import (
	EXTENDER,
	HOST,
	SettingsDialogTestCase,
	authoring,
	component,
	ship,
	single,
)
from frappe.desk.settings_arrangement import ArrangementCheck
from frappe.shell.registry import get_prefix_registry
from frappe.shell.settings import check_shipped_records, get_cached_sidebars, merge_settings
from frappe.shell.settings_sidebar import filter_sidebar
from frappe.shell.settings_sidebar_text import (
	SIDEBAR_FILE,
	assert_settings_sidebar,
	describe_sidebars,
	required_scope,
	sidebar_text,
	write_settings_sidebar,
)
from frappe.tests.test_shell_settings import active

PROFILE = "desk/profile"
SYSTEM = "desk/system"
GENERAL = f"{HOST}/general"
MAIL = f"{HOST}/email"
EVERY_PANE = [PROFILE, SYSTEM, GENERAL, MAIL]
FRAMEWORK_PANES = [PROFILE, SYSTEM]


def arranged(groups=None, **rest) -> dict:
	"""An arrangement placing every pane in one unheaded group unless told otherwise."""
	return {"groups": groups if groups is not None else [{"panes": EVERY_PANE}], **rest}


def resolve(arrangement=None, *, bench: tuple[str, ...] = (), checked: bool = False):
	"""The merge over `HOST` and the framework, as `HOST` ships it with this arrangement.

	Unchecked unless `checked`: a file reaches the merge as migrate imports it, with no `validate`.
	"""
	with authoring():
		record = ship(
			["general", "email"],
			[
				single("system"),
				component("theme"),
				single("smtp", pane="email"),
				component("login", pane="email"),
			],
			arrangement=arrangement,
			insert=False,
		)
		record.flags.ignore_validate = not checked
		record.insert()

	get_prefix_registry()
	with (
		active(HOST),
		patch("frappe.get_all_apps", return_value=[*frappe.get_installed_apps(), *bench]),
		patch("frappe.desk.settings_arrangement.declared_prefix", side_effect=default_prefix_of),
	):
		return merge_settings()


def default_prefix_of(app: str) -> str:
	return "desk" if app == "frappe" else default_prefix(app)


def details(resolved) -> list[str]:
	return [problem.detail for problem in resolved.problems]


def group_panes(sidebar: dict) -> list[list[str]]:
	return [[entry["pane"] for entry in group["panes"]] for group in sidebar["groups"]]


def blocks_of(sidebar: dict, pane: str) -> list[str]:
	return next(
		entry["blocks"] for group in sidebar["groups"] for entry in group["panes"] if entry["pane"] == pane
	)


class TestSidebarDefault(SettingsDialogTestCase):
	def test_without_an_arrangement_the_framework_panes_come_first_then_the_app_group(self):
		resolved = resolve()
		sidebar = resolved.sidebars[HOST]

		self.assertEqual(group_panes(sidebar), [FRAMEWORK_PANES, [GENERAL, MAIL]])
		self.assertEqual(sidebar["groups"][1]["app"], HOST)
		self.assertNotIn("app", sidebar["groups"][0])
		self.assertEqual(blocks_of(sidebar, GENERAL), [f"{GENERAL}/system", f"{GENERAL}/theme"])
		self.assertEqual((sidebar["hidden"], sidebar["hidden_blocks"], resolved.notices[HOST]), ([], [], []))

	def test_the_framework_desk_shows_its_own_panes_only(self):
		sidebar = resolve().sidebars["desk"]

		self.assertEqual(group_panes(sidebar), [FRAMEWORK_PANES])

	def test_an_app_with_no_panes_and_no_record_has_no_sidebar(self):
		with active(EXTENDER):
			self.assertNotIn(EXTENDER, merge_settings().sidebars)


class TestSidebarArranged(SettingsDialogTestCase):
	def test_groups_order_panes_and_a_placement_shows_a_block_of_another_pane(self):
		resolved = resolve(
			{
				"groups": [
					{"panes": [PROFILE, GENERAL]},
					{"label": "Mail", "panes": [MAIL, SYSTEM]},
				],
				"panes": {GENERAL: {"blocks": [f"{GENERAL}/theme", f"{PROFILE}/photo", f"{GENERAL}/system"]}},
			}
		)
		sidebar = resolved.sidebars[HOST]

		self.assertEqual(group_panes(sidebar), [[PROFILE, GENERAL], [MAIL, SYSTEM]])
		self.assertEqual(sidebar["groups"][1]["label"], "Mail")
		self.assertEqual(
			blocks_of(sidebar, GENERAL), [f"{GENERAL}/theme", f"{PROFILE}/photo", f"{GENERAL}/system"]
		)
		self.assertIn(f"{PROFILE}/photo", blocks_of(sidebar, PROFILE))
		self.assertEqual((resolved.problems, resolved.notices[HOST]), ([], []))

	def test_only_the_app_that_owns_the_desk_arranges_it(self):
		resolved = resolve(arranged([{"panes": [GENERAL, MAIL, SYSTEM, PROFILE]}]))

		self.assertEqual(group_panes(resolved.sidebars["desk"]), [FRAMEWORK_PANES])

	def test_a_hidden_pane_leaves_the_groups_and_an_unmentioned_pane_goes_to_the_more_group(self):
		resolved = resolve({"groups": [{"panes": [GENERAL]}], "hidden": [SYSTEM]})
		sidebar = resolved.sidebars[HOST]

		self.assertEqual(sidebar["hidden"], [SYSTEM])
		self.assertEqual(group_panes(sidebar), [[GENERAL], [PROFILE, MAIL]])
		self.assertEqual(sidebar["groups"][1]["label"], "More")
		self.assertEqual(len(resolved.notices[HOST]), 2)
		self.assertIn(PROFILE, resolved.notices[HOST][0])
		self.assertIn(MAIL, resolved.notices[HOST][1])
		self.assertEqual(resolved.problems, [])

	def test_a_hidden_block_leaves_its_pane_and_raises_no_notice(self):
		resolved = resolve(arranged(panes={GENERAL: {"hidden": [f"{GENERAL}/theme"]}}))
		sidebar = resolved.sidebars[HOST]

		self.assertEqual(blocks_of(sidebar, GENERAL), [f"{GENERAL}/system"])
		self.assertEqual(sidebar["hidden_blocks"], [f"{GENERAL}/theme"])
		self.assertEqual((resolved.problems, resolved.notices[HOST]), ([], []))

	def test_a_pane_entry_with_no_blocks_keeps_the_default_order_and_raises_no_notice(self):
		resolved = resolve(arranged(panes={GENERAL: {}, MAIL: {"hidden": [f"{MAIL}/login"]}}))
		sidebar = resolved.sidebars[HOST]

		self.assertEqual(blocks_of(sidebar, GENERAL), [f"{GENERAL}/system", f"{GENERAL}/theme"])
		self.assertEqual(blocks_of(sidebar, MAIL), [f"{MAIL}/smtp"])
		self.assertEqual(resolved.notices[HOST], [])

	def test_blocks_a_list_leaves_out_go_to_the_end_with_a_notice(self):
		resolved = resolve(arranged(panes={GENERAL: {"blocks": [f"{GENERAL}/theme"]}}))

		self.assertEqual(
			blocks_of(resolved.sidebars[HOST], GENERAL), [f"{GENERAL}/theme", f"{GENERAL}/system"]
		)
		self.assertEqual(len(resolved.notices[HOST]), 1)
		self.assertIn(f"{GENERAL}/system", resolved.notices[HOST][0])
		self.assertEqual(resolved.problems, [])

	def test_a_placed_block_whose_key_a_pane_already_holds_is_dropped_with_a_problem(self):
		resolved = resolve(
			arranged(panes={MAIL: {"blocks": [f"{MAIL}/smtp", f"{MAIL}/login", f"{SYSTEM}/login"]}})
		)

		self.assertNotIn(f"{SYSTEM}/login", blocks_of(resolved.sidebars[HOST], MAIL))
		self.assertTrue(
			any(f'arrangement.panes["{MAIL}"].blocks[2]' in detail for detail in details(resolved))
		)

	def test_a_reference_to_an_app_on_the_bench_but_not_active_is_skipped_silently(self):
		resolved = resolve(
			arranged(
				[{"panes": [*EVERY_PANE, "dormant/pane"]}],
				hidden=["dormant/other"],
				panes={GENERAL: {"blocks": ["dormant/pane/block", f"{GENERAL}/system", f"{GENERAL}/theme"]}},
			),
			bench=("dormant",),
		)

		self.assertEqual(resolved.problems, [])
		self.assertEqual(
			blocks_of(resolved.sidebars[HOST], GENERAL), [f"{GENERAL}/system", f"{GENERAL}/theme"]
		)


class TestSidebarValidation(SettingsDialogTestCase):
	def assert_problem(self, arrangement: dict, path: str, *words: str):
		details_ = details(resolve(arrangement))
		matching = [detail for detail in details_ if path in detail]
		self.assertTrue(matching, f"No problem at {path} in {details_}")
		for word in words:
			self.assertIn(word, matching[0])

	def test_every_rule_names_the_path_of_the_mistake(self):
		cases = {
			"no pane at the address": (
				arranged([{"panes": [*EVERY_PANE, "desk/nowhere"]}]),
				"arrangement.groups[0].panes[4]",
				"desk/nowhere",
			),
			"no block at the address": (
				arranged(panes={GENERAL: {"blocks": [f"{PROFILE}/nowhere"]}}),
				f'arrangement.panes["{GENERAL}"].blocks[0]',
				f"{PROFILE}/nowhere",
			),
			"the app name for the prefix": (
				arranged(hidden=["frappe/profile"]),
				"arrangement.hidden[0]",
				"Did you mean desk/profile?",
			),
			"a prefix of no app": (
				arranged(hidden=["nowhere/profile"]),
				"arrangement.hidden[0]",
				"No app has the prefix nowhere",
			),
			"a pane in two groups": (
				arranged([{"panes": EVERY_PANE}, {"label": "Again", "panes": [PROFILE]}]),
				"arrangement.groups[1].panes[0]",
				"arrangement.groups[0].panes[0]",
			),
			"a pane placed and hidden": (
				arranged(hidden=[PROFILE]),
				"arrangement.hidden[0]",
				"also in a group",
			),
			"a block listed twice": (
				arranged(panes={GENERAL: {"blocks": [f"{GENERAL}/system", f"{GENERAL}/system"]}}),
				f'arrangement.panes["{GENERAL}"].blocks[1]',
				f"{GENERAL}/system",
			),
			"a block listed and hidden": (
				arranged(panes={GENERAL: {"blocks": [f"{GENERAL}/system"], "hidden": [f"{GENERAL}/system"]}}),
				f'arrangement.panes["{GENERAL}"].hidden[0]',
				f"{GENERAL}/system",
			),
			"an entry for a hidden pane": (
				{"groups": [{"panes": [GENERAL, MAIL, PROFILE]}], "hidden": [SYSTEM], "panes": {SYSTEM: {}}},
				f'arrangement.panes["{SYSTEM}"]',
				"hidden",
			),
			"an entry for an ungrouped pane": (
				arranged([{"panes": [GENERAL, MAIL, PROFILE, SYSTEM]}], panes={"desk/ungrouped": {}}),
				'arrangement.panes["desk/ungrouped"]',
				"desk/ungrouped",
			),
			"an app hiding its own pane": (
				{"groups": [{"panes": [PROFILE, SYSTEM, MAIL]}], "hidden": [GENERAL]},
				"arrangement.hidden[0]",
				"does not hide its own pane",
			),
			"a later group with no label": (
				arranged([{"panes": [PROFILE]}, {"panes": [SYSTEM, GENERAL, MAIL]}]),
				"arrangement.groups[1]",
				"first group",
			),
			"a short address": (
				arranged(hidden=["profile"]),
				"arrangement.hidden[0]",
				"is not a pane address",
			),
			"an unknown key": (arranged(extra=1), "arrangement.extra", "keys here are"),
		}

		for name, (arrangement, path, *words) in cases.items():
			with self.subTest(name):
				self.assert_problem(arrangement, path, *words)
				frappe.db.rollback(save_point="settings_dialog_test")
				frappe.db.savepoint("settings_dialog_test")

	def test_a_part_that_breaks_a_rule_is_dropped_and_the_rest_stays(self):
		resolved = resolve(
			arranged(hidden=[PROFILE, "desk/nowhere"], panes={GENERAL: {"hidden": [f"{GENERAL}/theme"]}})
		)
		sidebar = resolved.sidebars[HOST]

		self.assertEqual(sidebar["hidden"], [])
		self.assertEqual(sidebar["hidden_blocks"], [f"{GENERAL}/theme"])
		self.assertEqual(len(resolved.problems), 2)

	def test_a_pane_both_grouped_and_hidden_keeps_its_blocks_entry(self):
		entry = {"blocks": [f"{PROFILE}/photo"]}
		resolved = resolve(
			{"groups": [{"panes": [GENERAL, MAIL, PROFILE]}], "hidden": [PROFILE], "panes": {PROFILE: entry}}
		)

		self.assertEqual([problem.title for problem in resolved.problems], ["Pane Placed and Hidden"])
		self.assertEqual(blocks_of(resolved.sidebars[HOST], PROFILE)[0], f"{PROFILE}/photo")

	def test_an_array_where_an_object_belongs_is_a_problem_even_when_empty(self):
		record = frappe._dict(app="acme", name="acme", extends="", arrangement="[]")

		self.assertEqual(
			[problem.title for problem in ArrangementCheck(record).check()], ["Invalid Arrangement"]
		)

	def test_a_prefix_slip_is_an_error_and_not_a_silent_skip(self):
		resolved = resolve(arranged(hidden=["dormant/pane", "frappe/profile"]), bench=("dormant",))

		self.assertEqual(len(resolved.problems), 1)
		self.assertIn("arrangement.hidden[1]", resolved.problems[0].detail)

	def test_the_record_checks_run_on_save_with_no_site_to_look_in(self):
		slips = {
			"a second group without a label": arranged([{"panes": [PROFILE]}, {"panes": [SYSTEM]}]),
			"a pane in two groups": arranged([{"panes": [PROFILE, PROFILE]}]),
			"a short address": arranged(hidden=["profile"]),
			"a list that is not a list": {"groups": {"panes": []}},
			"a block listed and hidden": arranged(
				panes={GENERAL: {"blocks": [f"{GENERAL}/system"], "hidden": [f"{GENERAL}/system"]}}
			),
		}

		for name, arrangement in slips.items():
			with self.subTest(name), authoring():
				self.assertRaises(
					frappe.ValidationError, ship, ["general"], [single("system")], arrangement=arrangement
				)

		with authoring():
			ship(["general"], [single("system")], arrangement=arranged([{"panes": [GENERAL]}]))

	def test_an_arrangement_on_a_record_that_extends_is_refused(self):
		with authoring():
			self.assertRaises(
				frappe.ValidationError,
				ship,
				blocks=[component("calls")],
				app=EXTENDER,
				extends=HOST,
				arrangement=arranged([{"panes": [GENERAL]}]),
			)

	def test_a_bad_reference_raises_in_the_strict_check_of_shipped_records(self):
		resolve(arranged(hidden=["desk/nowhere"]))

		with active(HOST), self.assertRaises(frappe.ValidationError):
			check_shipped_records()


class TestSidebarFiles(SettingsDialogTestCase):
	def test_a_file_written_with_anchors_still_loads_and_the_anchor_is_ignored(self):
		docdict = {
			"doctype": "Settings Dialog",
			"blocks": [{**component("theme"), "anchors": '{"after": "email"}'}],
			"arrangement": {"groups": [{"panes": [GENERAL]}]},
		}
		SettingsDialog.prepare_for_import(docdict)

		self.assertNotIn("anchors", docdict["blocks"][0])
		self.assertEqual(json.loads(docdict["arrangement"]), {"groups": [{"panes": [GENERAL]}]})

	def test_an_arrangement_is_exported_as_native_json_and_imported_back(self):
		arrangement = {
			"groups": [{"panes": [GENERAL]}, {"label": "Mail", "panes": [PROFILE]}],
			"hidden": [SYSTEM],
			"panes": {GENERAL: {"blocks": [f"{GENERAL}/system"]}},
		}
		with authoring():
			record = ship(["general"], [single("system")], arrangement=arrangement)

		exported = {"blocks": [], "arrangement": record.arrangement}
		record.before_export(exported)
		self.assertEqual(exported["arrangement"], arrangement)

		SettingsDialog.prepare_for_import(exported)
		self.assertEqual(json.loads(exported["arrangement"]), arrangement)

	def test_an_arrangement_save_changes_the_cached_sidebar(self):
		resolve(arranged([{"panes": EVERY_PANE}]))
		with authoring():
			record = frappe.get_doc("Settings Dialog", HOST)

		def cached():
			with active(HOST):
				return group_panes(get_cached_sidebars()[HOST])

		self.assertEqual(cached(), [EVERY_PANE])

		with authoring():
			record.arrangement = json.dumps(arranged([{"panes": [GENERAL, MAIL]}], hidden=[SYSTEM, PROFILE]))
			record.save()

		self.assertEqual(cached(), [[GENERAL, MAIL]])


class TestSidebarText(SettingsDialogTestCase):
	def test_the_text_lists_groups_panes_blocks_and_what_is_hidden_or_noticed(self):
		resolved = resolve(
			{
				"groups": [{"panes": [GENERAL]}],
				"hidden": [SYSTEM],
				"panes": {GENERAL: {"blocks": [f"{PROFILE}/photo", f"{GENERAL}/theme"]}},
			}
		)
		lines = sidebar_text(HOST, resolved).splitlines()

		self.assertEqual(lines[0], f"Sidebar {HOST}")
		self.assertIn(f"    {PROFILE}/photo  [placed, home {PROFILE}]", lines)
		self.assertIn(f"    {GENERAL}/system", lines)
		self.assertIn('Group "More"', lines)
		self.assertIn(f"Hidden: {SYSTEM}", lines)
		self.assertTrue(any(line.startswith(f"Notice: {GENERAL}/system") for line in lines))
		self.assertTrue(any(line.startswith(f"Notice: {PROFILE} is in no group") for line in lines))

	def test_a_block_an_extending_app_added_is_noted(self):
		with authoring():
			ship(blocks=[component("calls")], app=EXTENDER, extends=HOST)
			ship(["general"], [single("system")])

		get_prefix_registry()
		with active(HOST, EXTENDER):
			resolved = merge_settings()

		self.assertIn(f"{GENERAL}/calls  [added by {EXTENDER}-{HOST}]", sidebar_text(HOST, resolved))

	def test_the_command_prints_one_desk_or_all_and_as_json(self):
		resolve()
		get_prefix_registry()

		with (
			active(HOST),
			patch("frappe.get_all_apps", return_value=[*frappe.get_installed_apps()]),
			patch("frappe.desk.settings_arrangement.declared_prefix", side_effect=default_prefix_of),
		):
			everything = describe_sidebars()
			desk = describe_sidebars("desk")
			as_json = json.loads(describe_sidebars(HOST, as_json=True))
			self.assertRaises(ValueError, describe_sidebars, "nowhere")

		self.assertIn(f"Sidebar {HOST}", everything)
		self.assertIn("Sidebar desk", everything)
		self.assertNotIn(f"Sidebar {HOST}", desk)
		self.assertEqual(as_json[HOST]["groups"][1]["app"], HOST)

	def test_the_user_option_drops_the_blocks_that_user_may_not_see(self):
		sidebar = {
			"groups": [
				{"panes": [{"pane": PROFILE, "blocks": [f"{PROFILE}/photo", f"{PROFILE}/details"]}]},
				{"label": "Gone", "panes": [{"pane": SYSTEM, "blocks": [f"{SYSTEM}/login"]}]},
			],
			"hidden": [],
			"hidden_blocks": [],
		}
		panes = [{"app": "frappe", "key": "profile", "blocks": [{"key": "photo"}]}]

		with patch("frappe.desk.settings_arrangement.declared_prefix", side_effect=default_prefix_of):
			filtered = filter_sidebar(sidebar, panes)

		self.assertEqual(group_panes(filtered), [[PROFILE]])
		self.assertEqual(blocks_of(filtered, PROFILE), [f"{PROFILE}/photo"])


class TestSidebarSnapshot(SettingsDialogTestCase):
	def test_the_framework_desk_matches_its_shipped_sidebar_txt(self):
		assert_settings_sidebar("desk")

	def test_a_different_sidebar_fails_with_a_diff_and_the_command_to_regenerate(self):
		with patch("frappe.shell.settings_sidebar_text._snapshot", return_value=("frappe", "Sidebar desk\n")):
			with self.assertRaises(AssertionError) as raised:
				assert_settings_sidebar("desk")

		self.assertIn("settings-sidebar desk --write", str(raised.exception))
		self.assertIn("-    desk/profile/photo", str(raised.exception))

	def test_write_puts_the_text_where_the_check_reads_it(self):
		with tempfile.TemporaryDirectory() as app_path:
			real = frappe.get_app_path

			def app_path_of(app, *parts):
				return str(Path(app_path, *parts)) if parts == SIDEBAR_FILE else real(app, *parts)

			with patch("frappe.get_app_path", side_effect=app_path_of):
				path = write_settings_sidebar("desk")
				assert_settings_sidebar("desk")

			self.assertEqual(path, Path(app_path, "settings_dialog", "sidebar.txt"))
			self.assertTrue(path.read_text().startswith("Sidebar desk\n"))

	def test_the_scope_is_the_framework_then_the_required_apps_then_the_app(self):
		hooks = {"crm": ["frappe", "telephony"], "telephony": ["frappe"]}

		with patch("frappe.get_hooks", side_effect=lambda key, app_name=None: hooks.get(app_name, [])):
			self.assertEqual(required_scope("crm"), ["frappe", "telephony", "crm"])
			self.assertEqual(required_scope("frappe"), ["frappe"])
