# The settings dialog's pane-list endpoint: who sees which pane, block and field, the search label
# index, and the cache. Never as Administrator: `may_read` and the permlevels pass every check for it.

import json
from unittest.mock import patch

import frappe
from frappe.deferred_insert import queue_prefix
from frappe.desk.doctype.settings_dialog.test_settings_dialog import (
	AUTHOR,
	EXTENDER,
	HOST,
	SettingsDialogTestCase,
	authoring,
	component,
	ship,
	single,
)
from frappe.shell.boot import BUDGET_LOG_TITLE, KEY_BUDGET
from frappe.shell.permissions import default_app_permission, has_app_permission
from frappe.shell.settings import PANES_CACHE_KEY, PANES_VERSION_KEY, get_panes
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_shell_settings import active

SINGLE = "Settings Filter Single"
RECORD = "Settings Filter Record"
READER_ROLE = "Settings Filter Reader"
CREATOR_ROLE = "Settings Filter Creator"

READER = "settings-reader@example.com"
CREATOR = "settings-creator@example.com"
WEBSITE_USER = "settings-website@example.com"

SESSION_USER = {"binding_type": "Record", "document_type": "User", "name_resolver": "session_user"}
APP_GATE = "frappe.shell.settings_filter.has_app_permission"
OWN_RECORD = {"binding_type": "Record", "document_type": RECORD, "name_resolver": "session_user"}


def a_doctype(name: str, fields: list[dict], permissions: list[dict], **kwargs):
	if not frappe.db.exists("DocType", name):
		frappe.get_doc(
			doctype="DocType",
			name=name,
			module="Desk",
			custom=1,
			fields=fields,
			permissions=permissions,
			**kwargs,
		).insert()


def perm(role: str, permlevel: int = 0, **rights: int) -> dict:
	"""A DocPerm row granting only `rights`: the DocType defaults write, create and delete to 1."""
	return {"role": role, "permlevel": permlevel, **dict.fromkeys(("write", "create", "delete"), 0), **rights}


def a_user(email: str, roles: list[str], user_type: str = "System User"):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			doctype="User",
			email=email,
			first_name=email.split("@")[0],
			user_type=user_type,
			roles=[{"role": role} for role in roles],
		).insert()


def binding(type_: str, doctype: str) -> dict:
	spec = {"type": type_, "doctype": doctype}
	return {**spec, "resolver": "session_user"} if type_ == "Record" else spec


def bound(key: str, **bindings: dict) -> dict:
	return component(key, bindings=json.dumps(bindings))


def visible(user: str = READER, gate=None) -> dict:
	"""The endpoint's reply for this user, with the merge seeing `HOST` and `EXTENDER` as installed."""
	with active(HOST, EXTENDER), set_user(user), patch(APP_GATE, side_effect=gate or entered):
		return get_panes()


def entered(app: str) -> bool:
	"""`has_app_permission` for the test apps, which are never installed and so have no hooks."""
	return default_app_permission() if app in (HOST, EXTENDER) else has_app_permission(app)


def blocks_of(reply: dict) -> dict[str, list[str]]:
	return {
		pane["key"]: [block["key"] for block in pane["blocks"]]
		for pane in reply["panes"]
		if pane["app"] == HOST
	}


def block_named(reply: dict, key: str) -> dict:
	return next(block for pane in reply["panes"] for block in pane["blocks"] if block["key"] == key)


def indexed(reply: dict) -> list[tuple]:
	return [
		(entry["pane"], entry["block"], entry.get("fieldname") or entry["label"])
		for entry in reply["index"]
		if entry["app"] == HOST
	]


class TestSettingsFilter(SettingsDialogTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for role in (READER_ROLE, CREATOR_ROLE):
			if not frappe.db.exists("Role", role):
				frappe.get_doc(doctype="Role", role_name=role, desk_access=1).insert()

		a_doctype(
			SINGLE,
			[
				{"fieldname": "alpha", "label": "Alpha", "fieldtype": "Data", "description": "The first"},
				{"fieldname": "details", "label": "Details", "fieldtype": "Section Break"},
				{"fieldname": "beta", "label": "Beta", "fieldtype": "Data", "permlevel": 1},
				{"fieldname": "gamma", "label": "Gamma", "fieldtype": "Data", "permlevel": 2},
				{"fieldname": "kept_out", "label": "Kept Out", "fieldtype": "Data", "hidden": 1},
			],
			[
				perm("System Manager", read=1, write=1),
				perm(READER_ROLE, read=1, write=1),
				perm(READER_ROLE, permlevel=1, read=1),
			],
			issingle=1,
		)
		a_doctype(
			RECORD,
			[{"fieldname": "note", "label": "Note", "fieldtype": "Data"}],
			[perm(READER_ROLE, read=1), perm(CREATOR_ROLE, read=1, write=1, create=1)],
			autoname="Prompt",
		)
		a_user(READER, ["Desk User", READER_ROLE])
		a_user(CREATOR, ["Desk User", READER_ROLE, CREATOR_ROLE])
		a_user(WEBSITE_USER, [], user_type="Website User")
		# DocType DDL commits anyway, so the users are committed with it.
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		for doctype in (SINGLE, RECORD):
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)
		for user in (READER, CREATOR, WEBSITE_USER):
			frappe.delete_doc("User", user, force=True, ignore_permissions=True)
		for role in (READER_ROLE, CREATOR_ROLE):
			frappe.delete_doc("Role", role, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.client_cache.delete_value(PANES_CACHE_KEY)

	# Each binding kind

	def test_a_single_block_shows_on_read_of_its_doctype(self):
		with authoring():
			ship(["general"], [single("mine", doctype=SINGLE), single("system")])

		self.assertEqual(blocks_of(visible()), {"general": ["mine"]})
		self.assertEqual(blocks_of(visible(AUTHOR)), {"general": ["mine", "system"]})

	def test_the_users_own_record_shows_to_anyone_allowed_in(self):
		with authoring():
			ship(["profile"], [single("me", pane="profile", **SESSION_USER)])

		self.assertEqual(blocks_of(visible()), {"profile": ["me"]})

	def test_another_record_block_shows_on_read_and_a_missing_record_needs_create(self):
		with authoring():
			ship(["calls"], [single("agent", pane="calls", **OWN_RECORD)])

		self.assertEqual(blocks_of(visible(READER)), {}, "missing, and the reader cannot create it")
		self.assertEqual(blocks_of(visible(CREATOR)), {"calls": ["agent"]})

		frappe.get_doc(doctype=RECORD, note="mine").insert(set_name=READER, ignore_permissions=True)
		self.assertEqual(blocks_of(visible(READER)), {"calls": ["agent"]})
		self.assertTrue(block_named(visible(READER), "agent")["read_only"])

	def test_a_component_block_shows_when_every_binding_it_declares_may_be_used(self):
		with authoring():
			ship(
				["general"],
				[
					bound("readable", me=binding("Record", "User"), mine=binding("Single", SINGLE)),
					bound(
						"half", mine=binding("Single", SINGLE), system=binding("Single", "System Settings")
					),
					bound("uncreated", agent=binding("Record", RECORD)),
				],
			)

		self.assertEqual(blocks_of(visible(READER)), {"general": ["readable"]})
		self.assertEqual(blocks_of(visible(CREATOR)), {"general": ["readable", "uncreated"]})

	def test_a_component_block_with_no_binding_shows_to_whoever_may_enter_its_app(self):
		with authoring():
			ship(["general"], [component("theme")])
			ship(blocks=[component("dialer")], app=EXTENDER, extends=HOST)

		self.assertEqual(blocks_of(visible()), {"general": ["theme", "dialer"]})
		self.assertEqual(blocks_of(visible(gate=lambda app: app == HOST)), {"general": ["theme"]})

	def test_a_pane_left_with_no_visible_block_is_not_sent(self):
		with authoring():
			ship(["general", "system"], [single("mine", doctype=SINGLE), single("smtp", pane="system")])

		self.assertEqual(blocks_of(visible()), {"general": ["mine"]})

	# Fields

	def test_fields_above_the_readable_permlevel_are_cut_and_unwritable_ones_read_only(self):
		with authoring():
			ship(["general"], [single("mine", doctype=SINGLE, fields=json.dumps(["alpha", "beta", "gamma"]))])

		block = block_named(visible(), "mine")

		self.assertEqual(block["fields"], ["alpha", "beta"])
		self.assertEqual(block["read_only_fields"], ["beta"])
		self.assertNotIn("read_only", block)

	def test_a_whole_layout_block_names_the_fields_it_leaves_out(self):
		with authoring():
			ship(["general"], [single("mine", doctype=SINGLE)])

		block = block_named(visible(), "mine")

		self.assertNotIn("fields", block)
		self.assertEqual(block["left_out_fields"], ["gamma"])
		self.assertEqual(block["read_only_fields"], ["beta"])

	def test_a_block_with_no_readable_field_is_not_sent(self):
		with authoring():
			ship(
				["general"],
				[single("mine", doctype=SINGLE, fields=json.dumps(["gamma"])), component("theme")],
			)

		self.assertEqual(blocks_of(visible()), {"general": ["theme"]})

	def test_the_users_own_record_leaves_out_what_only_a_system_manager_reads(self):
		with authoring():
			ship(["profile"], [single("me", pane="profile", **SESSION_USER)])

		block = block_named(visible(), "me")

		self.assertIn("roles", block["left_out_fields"])
		self.assertNotIn("read_only", block, "the self-share writes permlevel 0")

	# The label index

	def test_the_index_holds_readable_fields_and_shown_component_settings_only(self):
		settings = json.dumps([{"label": "Dark mode", "keywords": ["theme"]}])
		with authoring():
			ship(
				["general", "system"],
				[
					single("mine", doctype=SINGLE),
					component("theme", settings=settings),
					single("smtp", pane="system"),
					component(
						"mail",
						pane="system",
						settings=settings,
						bindings=json.dumps({"smtp": binding("Single", "System Settings")}),
					),
				],
			)

		reply = visible()

		self.assertEqual(
			indexed(reply),
			[("general", "mine", "alpha"), ("general", "mine", "beta"), ("general", "theme", "Dark mode")],
		)
		self.assertEqual(reply["index"][0]["description"], "The first")
		self.assertEqual(reply["index"][2]["keywords"], ["theme"])
		self.assertNotIn("settings", block_named(reply, "theme"))

	# The cache and the gate

	def test_a_settings_dialog_save_clears_the_cached_merge(self):
		with authoring():
			record = ship(["general"], [single("mine", doctype=SINGLE)])

		self.assertEqual(blocks_of(visible()), {"general": ["mine"]})
		version = frappe.client_cache.get_value(PANES_VERSION_KEY)

		with authoring():
			record.append("blocks", component("theme"))
			record.save()

		self.assertNotEqual(frappe.client_cache.get_value(PANES_VERSION_KEY), version)
		self.assertEqual(blocks_of(visible()), {"general": ["mine", "theme"]})

		with authoring():
			record.delete()

		self.assertEqual(blocks_of(visible()), {})

	def test_the_merge_is_cached_on_metadata_version(self):
		with authoring():
			ship(["general"], [single("mine", doctype=SINGLE)])

		visible()
		with patch("frappe.shell.settings.resolve_panes") as merge:
			visible()
			merge.assert_not_called()

			frappe.reset_metadata_version()
			merge.return_value = []
			self.assertEqual(blocks_of(visible()), {})

	def test_a_website_user_is_refused(self):
		with set_user(WEBSITE_USER):
			self.assertRaises(frappe.PermissionError, get_panes)

	def test_a_reply_over_the_key_budget_is_logged_and_sent_whole(self):
		queue = f"{queue_prefix}Error Log"
		frappe.cache.delete_keys("boot_budget:")
		frappe.cache.delete_value(queue)
		self.addCleanup(frappe.cache.delete_value, queue)

		huge = {
			"key": "theme",
			"app": HOST,
			"save_mode": "auto",
			"component": "theme",
			"label": "x" * KEY_BUDGET,
		}
		merged = [{"app": HOST, "key": "general", "label": "General", "blocks": [huge]}]

		with patch("frappe.shell.settings.get_cached_panes", return_value=merged):
			self.assertEqual(blocks_of(visible()), {"general": ["theme"]})

		queued = [json.loads(raw.decode()) for raw in frappe.cache.lrange(queue, 0, -1) or []]
		logged = [record["error"] for record in queued if record.get("method") == BUDGET_LOG_TITLE]
		self.assertEqual(len(logged), 1)
		self.assertIn("panes is", logged[0])
		self.assertIn("at the settings reply", logged[0])
