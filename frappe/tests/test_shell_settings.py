# The settings dialog's merge: every app's panes, each holding its host's blocks and then the
# extending apps' blocks, in run order. Unfiltered, so no test here needs a second user.

import contextlib
import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype.settings_dialog.test_settings_dialog import (
	EXTENDER,
	HOST,
	SettingsDialogTestCase,
	authoring,
	component,
	pane,
	ship,
	single,
)
from frappe.shell.settings import resolve_panes

OTHER_EXTENDER = "payments"


@contextlib.contextmanager
def active(*apps: str):
	"""Present these apps to the merge as installed and enabled, in this order."""
	with patch("frappe.get_active_apps", return_value=["frappe", *apps]):
		yield


def panes_of(app: str, *apps: str) -> list[dict]:
	with active(*apps):
		return [entry for entry in resolve_panes() if entry["app"] == app]


def block_keys(app: str, *apps: str) -> dict[str, list[str]]:
	return {entry["key"]: [block["key"] for block in entry["blocks"]] for entry in panes_of(app, *apps)}


def anchored(key: str, *anchors: dict) -> dict:
	return component(key, anchors=json.dumps(list(anchors)))


def unchecked(doc):
	"""Insert as install order can leave it: the other record arrived after this one was checked."""
	doc.flags.ignore_validate = True
	doc.user = ""
	return doc.insert()


class TestSettingsMerge(SettingsDialogTestCase):
	def test_host_blocks_come_first_then_extending_apps_in_run_order(self):
		with authoring():
			ship(blocks=[component("billing")], app=OTHER_EXTENDER, extends=HOST)
			ship(blocks=[component("calls")], app=EXTENDER, extends=HOST)
			ship(["general"], [single("system"), component("theme")])

		self.assertEqual(
			block_keys(HOST, HOST, EXTENDER, OTHER_EXTENDER),
			{"general": ["system", "theme", "calls", "billing"]},
		)
		self.assertEqual(
			block_keys(HOST, HOST, OTHER_EXTENDER, EXTENDER),
			{"general": ["system", "theme", "billing", "calls"]},
		)

	def test_panes_keep_row_order_and_hosts_keep_run_order(self):
		with authoring():
			ship(["general", "email"], [single("system"), single("smtp", pane="email")])
			ship(["telephony"], [component("agents", pane="telephony")], app=EXTENDER)

		with active(EXTENDER, HOST):
			keys = [(entry["app"], entry["key"]) for entry in resolve_panes() if entry["app"] != "frappe"]

		self.assertEqual(keys, [(EXTENDER, "telephony"), (HOST, "general"), (HOST, "email")])

	def test_an_anchor_places_an_extending_block_beside_a_host_block(self):
		with authoring():
			ship(["general"], [single("system"), component("theme"), component("defaults")])
			ship(
				blocks=[anchored("calls", {"before": "theme"}), anchored("dial", {"after": "defaults"})],
				app=EXTENDER,
				extends=HOST,
			)

		self.assertEqual(
			block_keys(HOST, HOST, EXTENDER), {"general": ["system", "calls", "theme", "defaults", "dial"]}
		)

	def test_an_anchor_that_does_not_resolve_leaves_the_block_in_run_order(self):
		with authoring():
			ship(["general"], [single("system"), component("theme")])
			ship(
				blocks=[anchored("calls", {"after": "gone"}, {"parent_key": "system"})],
				app=EXTENDER,
				extends=HOST,
			)

		self.assertEqual(block_keys(HOST, HOST, EXTENDER), {"general": ["system", "theme", "calls"]})

	def test_a_host_blocks_anchor_does_not_move_it(self):
		with authoring():
			ship(["general"], [single("system"), anchored("theme", {"before": "system"})])

		self.assertEqual(block_keys(HOST, HOST), {"general": ["system", "theme"]})

	def test_a_duplicate_key_keeps_the_first_block_in_run_order_and_warns(self):
		with authoring():
			ship(blocks=[component("theme")], app=EXTENDER, extends=HOST)
			unchecked(ship(["general"], [component("theme", label="Host theme")], insert=False))

		with self.assertLogs(frappe.logger("shell"), "WARNING") as logged:
			merged = panes_of(HOST, HOST, EXTENDER)

		self.assertEqual([(block["key"], block["app"]) for block in merged[0]["blocks"]], [("theme", HOST)])
		self.assertIn("'theme'", logged.output[0])

	def test_an_orphan_block_is_dropped(self):
		with authoring():
			ship(["general"], [single("system")])
			ship(blocks=[component("calls", pane="gone")], app=EXTENDER, extends=HOST)

		self.assertEqual(block_keys(HOST, HOST, EXTENDER), {"general": ["system"]})

	def test_a_block_bound_to_a_doctype_the_site_lacks_is_dropped(self):
		missing = json.dumps(
			{"agent": {"type": "Record", "doctype": "Telephony Agent", "resolver": "session_user"}}
		)

		with authoring():
			doc = ship(
				["general"],
				[
					single("system"),
					single("agent", doctype="Telephony Agent"),
					component("dialer", bindings=missing),
				],
				insert=False,
			)
			doc.flags.ignore_links = True
			doc.insert()

		self.assertEqual(block_keys(HOST, HOST), {"general": ["system"]})

	def test_a_pane_left_with_no_block_is_hidden(self):
		with authoring():
			doc = ship(
				["general", "agents"],
				[single("system"), single("agent", pane="agents", doctype="Telephony Agent")],
				insert=False,
			)
			doc.flags.ignore_links = True
			doc.insert()
			ship(["empty"], app=EXTENDER)

		self.assertEqual(block_keys(HOST, HOST, EXTENDER), {"general": ["system"]})
		self.assertEqual(panes_of(EXTENDER, HOST, EXTENDER), [])

	def test_an_inactive_app_contributes_nothing(self):
		with authoring():
			ship(["general"], [single("system")])
			ship(blocks=[component("calls")], app=EXTENDER, extends=HOST)

		self.assertEqual(block_keys(HOST, HOST), {"general": ["system"]})
		self.assertEqual(panes_of(HOST, EXTENDER), [])

	def test_only_the_app_layer_is_merged(self):
		with authoring():
			ship(["general"], [single("system")])
			frappe.get_doc(
				{
					"doctype": "Settings Dialog",
					"app": HOST,
					"panes": [pane("site")],
					"blocks": [single("site-system", pane="site")],
				}
			).insert()

		self.assertEqual(block_keys(HOST, HOST), {"general": ["system"]})

	def test_the_wire_shape_of_a_pane_and_its_blocks(self):
		bindings = {"user": {"type": "Record", "doctype": "User", "resolver": "session_user"}}
		settings = [{"label": "Theme", "keywords": "dark light"}]

		with authoring():
			ship(
				[pane("general", icon="settings", description="Site-wide settings")],
				[
					single("system", label="System", fields='["language"]', save_mode="button"),
					single("me", binding_type="Record", document_type="User", name_resolver="session_user"),
					component("theme", bindings=json.dumps(bindings), settings=json.dumps(settings)),
				],
			)

		self.assertEqual(
			panes_of(HOST, HOST),
			[
				{
					"app": HOST,
					"key": "general",
					"label": "General",
					"icon": "settings",
					"description": "Site-wide settings",
					"blocks": [
						{
							"key": "system",
							"app": HOST,
							"save_mode": "button",
							"label": "System",
							"binding": {"type": "Single", "doctype": "System Settings"},
							"fields": ["language"],
						},
						{
							"key": "me",
							"app": HOST,
							"save_mode": "auto",
							"binding": {"type": "Record", "doctype": "User", "resolver": "session_user"},
						},
						{
							"key": "theme",
							"app": HOST,
							"save_mode": "auto",
							"component": "theme",
							"bindings": bindings,
							"settings": settings,
						},
					],
				}
			],
		)


class TestSettingsFiles(SettingsDialogTestCase):
	def test_an_app_shipping_only_a_settings_component_reaches_the_bundle(self):
		import os
		import tempfile

		from frappe.shell.manifest import contributes

		with tempfile.TemporaryDirectory() as source_dir:
			folder = os.path.join(source_dir, "telephony", "frontend", "settings")
			os.makedirs(folder)
			self.assertFalse(contributes(source_dir))

			with open(os.path.join(folder, "agents.vue"), "w") as handle:
				handle.write("<template><div /></template>\n")

			self.assertTrue(contributes(source_dir))

	def test_migrate_finds_a_record_shipped_at_the_app_root(self):
		import os
		import tempfile

		from frappe.model.sync import APP_ROOTED_DOCTYPES, get_doc_files

		with tempfile.TemporaryDirectory() as app_path:
			path = os.path.join(app_path, "settings_dialog", "crm_desk", "crm_desk.json")
			os.makedirs(os.path.dirname(path))
			with open(path, "w") as handle:
				handle.write("{}\n")

			self.assertEqual(get_doc_files([], app_path, doctypes=APP_ROOTED_DOCTYPES), [path])
