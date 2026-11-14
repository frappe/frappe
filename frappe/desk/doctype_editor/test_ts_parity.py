# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The DocType editor replays each edit on the client, and the server replays it again on save.

The client's rules are hand-made copies of the server's. These tests read the copies out of the
TypeScript source and compare them with the Python originals, and replay one fixture of canvas
edits here and in `canvasParity.test.ts`.
"""

import json
import re
from pathlib import Path

import frappe
from frappe.desk.doctype.form_layout.form_layout import LAYOUT_BREAKS, assign_names, layout_from_fields
from frappe.desk.doctype_editor import design_edits, layout_tree, settings_edits
from frappe.desk.doctype_editor.errors import EditError
from frappe.model import no_value_fields
from frappe.permissions import std_rights
from frappe.tests import UnitTestCase

EDITOR = Path(frappe.get_app_path("frappe")).parent / "frontend/src/pages/doctypeEditor"
FIXTURE = Path(__file__).with_name("canvas_edits_fixture.json")
ITEM = re.compile(r'"([^"]*)"|\.\.\.([A-Z_]+)')


def ts_source(file: str) -> str:
	return (EDITOR / file).read_text()


def ts_body(file: str, name: str, opening: str, closing: str) -> str:
	"""What sits between the brackets of `const NAME ... = [` or `{`, up to the `;` that ends it."""
	match = re.search(
		rf"^(?:export )?const {name}\b[^=\n]*=\s*\{opening}(.*?)\{closing}(?: as const)?;",
		ts_source(file),
		re.M | re.S,
	)
	assert match, f"{name} is not a constant of {file}"
	return match.group(1)


def ts_list(file: str, name: str, others: dict[str, list[str]] | None = None) -> list[str]:
	"""A TypeScript array of strings, with `...OTHER` spreads taken from `others` and `...[...]` read inline."""
	body = re.sub(
		r"//[^\n]*|\.\.\.\[(.*?)\]",
		lambda spread: spread.group(1) or "",
		ts_body(file, name, "[", "]"),
		flags=re.S,
	)
	items = []
	for text, spread in ITEM.findall(body):
		items.extend(others[spread] if spread else [text])
	return items


def ts_dict(file: str, name: str) -> dict[str, str]:
	return dict(re.findall(r'"([\w.]+)":\s*"(\w+)"', ts_body(file, name, "{", "}")))


def ts_lists_by_key(file: str, name: str) -> dict[str, list[str]]:
	return {
		key: re.findall(r'"(\w+)"', items)
		for key, items in re.findall(r"(\w+):\s*\[([^\]]*)\]", ts_body(file, name, "{", "}"))
	}


def ts_row_properties() -> set[str]:
	"""Every property a Settings row sets: its `props`, and the third argument of `flag(...)`."""
	source = ts_source("settingsRows.ts")
	properties = {
		each
		for props in re.findall(r"props:\s*\[([^\]]*)\]", source)
		for each in re.findall(r'"(\w+)"', props)
	}
	return properties | set(re.findall(r'flag\(\s*"[^"]*",\s*"[^"]*",\s*"(\w+)"', source))


class TestRuleCopies(UnitTestCase):
	def test_reserved_properties_and_place_keys(self):
		self.assertEqual(
			ts_list("editorModel.ts", "RESERVED_PROPERTIES"), list(design_edits.RESERVED_PROPERTIES)
		)
		self.assertEqual(ts_list("editorModel.ts", "PLACE_KEYS"), list(design_edits.PLACE_KEYS))

	def test_canvas_acts_name_the_same_methods(self):
		server = {act: method for act, (method, _keys) in design_edits.CANVAS_ACTS.items()}
		self.assertEqual(ts_dict("editorModel.ts", "CANVAS_ACTS"), server)

	def test_container_properties(self):
		self.assertCountEqual(
			ts_list("layoutTree.ts", "CONTAINER_PROPERTIES"), layout_tree.CONTAINER_PROPERTIES
		)

	def test_layout_breaks(self):
		self.assertEqual(ts_list("fieldRules.ts", "LAYOUT_BREAKS"), list(LAYOUT_BREAKS))

	def test_unfetchable_types_are_the_valueless_ones_and_dynamic_link(self):
		breaks = {"LAYOUT_BREAKS": ts_list("fieldRules.ts", "LAYOUT_BREAKS")}
		self.assertCountEqual(
			ts_list("fetchFrom.ts", "UNFETCHABLE", breaks), [*no_value_fields, "Dynamic Link"]
		)
		self.assertCountEqual(design_edits.UNFETCHABLE_TYPES, [*no_value_fields, "Dynamic Link"])

	def test_rights_and_their_prerequisites(self):
		self.assertEqual(ts_list("settingsModel.ts", "RIGHTS"), list(std_rights))
		self.assertEqual(
			ts_lists_by_key("settingsModel.ts", "PREREQUISITES"),
			{k: list(v) for k, v in settings_edits.PREREQUISITES.items()},
		)

	def test_kind_properties(self):
		self.assertEqual(ts_list("settingsModel.ts", "KIND_PROPERTIES"), list(settings_edits.KIND_PROPERTIES))

	def test_every_settings_row_sets_a_property_the_server_accepts(self):
		# `naming_series` and `permissions` go in their own acts, and the kind is set when the DocType is made.
		own_acts = {"naming_series", "permissions", *settings_edits.KIND_PROPERTIES}
		self.assertEqual(
			ts_row_properties() - set(settings_edits.DESIGN_PROPERTIES),
			own_acts - set(settings_edits.DESIGN_PROPERTIES),
		)


class TestCanvasEditsFixture(UnitTestCase):
	"""`canvasParity.test.ts` replays the same file on `LayoutTreeEditor` and expects the same trees."""

	def setUp(self):
		self.fixture = json.loads(FIXTURE.read_text())

	def test_each_case_lands_on_its_expected_tree(self):
		for case in self.fixture["cases"]:
			with self.subTest(case["case"]):
				tree = layout_tree.LayoutTree(json.loads(json.dumps(self.fixture["base"])), "Details")
				if "refused" in case:
					with self.assertRaises(EditError) as raised:
						replay(tree, case["edits"])
					self.assertEqual(raised.exception.message, case["refused"])
				else:
					replay(tree, case["edits"])
					self.assertEqual(tree.tabs, case["expected"])

	def test_assign_names_slugs_a_label(self):
		for label, name in self.fixture["slugs"]:
			with self.subTest(label):
				nodes = [{"label": label}]
				assign_names(nodes, "tab")
				self.assertEqual(nodes[0]["name"], name)

	def test_a_name_taken_takes_the_position(self):
		nodes = [{"name": "main"}, {"label": "Main"}, {"label": "Main"}]
		assign_names(nodes, "section")
		self.assertEqual([node["name"] for node in nodes], ["main", "main_2", "main_3"])

	def test_the_fallback_layout_from_fields(self):
		for case in self.fixture["from_fields"]:
			with self.subTest(case["case"]):
				fields = [frappe._dict(field) for field in case["fields"]]
				self.assertEqual(json.loads(json.dumps(layout_from_fields(fields))), case["expected"])


def replay(tree: layout_tree.LayoutTree, edits: list[dict]):
	"""Each edit through `CANVAS_ACTS`, as `DesignEdits.canvas` hands it to the tree."""
	for edit in edits:
		method, keys = design_edits.CANVAS_ACTS[edit["act"]]
		getattr(tree, method)(**{key: edit[key] for key in keys if key in edit})
