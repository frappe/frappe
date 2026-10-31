# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import os
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.desk.doctype.doctype_view import api as view_api
from frappe.desk.doctype.doctype_view.key_space import SURVIVOR_CANDIDATES, reserved_keys
from frappe.desk.doctype.doctype_view.view_list import ViewList
from frappe.desk.doctype.view_type import view_type as view_type_module
from frappe.desk.doctype.view_type.view_type import applies_to, type_keys, view_types
from frappe.shell.manifest import ViewTypeFileError, enforce_view_types, view_type_problems
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

PROBE = "Probe-46028"
PROBE_RULES = "frappe.desk.view_type.probe_46028.probe_46028"


def make_view(doctype: str = "ToDo", type: str = PROBE, **kwargs):
	return frappe.get_doc(
		{"doctype": "Doctype View", "reference_doctype": doctype, "type": type, "settings": {}, **kwargs}
	)


class ViewTypeCase(IntegrationTestCase):
	"""A `Probe-46028` type made as migrate makes one, with server rules the test sets."""

	def setUp(self):
		frappe.db.delete("Doctype View", {"type": PROBE})
		self.rules = SimpleNamespace()
		self.enterContext(patch.object(view_type_module, "rules_module", side_effect=self.rules_module))
		frappe.flags.in_import = True
		self.addCleanup(setattr, frappe.flags, "in_import", False)
		frappe.get_doc({"doctype": "View Type", "name": PROBE, "label": "Probe", "module": "Desk"}).insert()
		self.addCleanup(frappe.cache.delete_value, view_type_module.CACHE_KEY)

	def tearDown(self):
		frappe.db.rollback()

	def rules_module(self, path):
		return self.rules if path == PROBE_RULES else None


class TestTheRecords(ViewTypeCase):
	def test_frappe_ships_list_as_a_record(self):
		record = view_types()["List"]
		self.assertEqual((record.label, record.icon, record.module), ("List", "list", "Desk"))

	def test_a_record_is_a_view_type_at_once_and_its_delete_ends_it(self):
		self.assertEqual(type_keys()["probe-46028"], PROBE)
		self.assertEqual(make_view().insert().type, PROBE)

		frappe.delete_doc("Doctype View", frappe.get_all("Doctype View", {"type": PROBE}, pluck="name")[0])
		frappe.delete_doc("View Type", PROBE)
		self.assertNotIn(PROBE, view_types())
		with self.assertRaisesRegex(frappe.ValidationError, "is not a view type"):
			make_view().insert()

	def test_a_type_with_no_record_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is not a view type"):
			make_view(type="Gantt").insert()

	def test_a_record_is_refused_outside_developer_mode_and_migrate(self):
		frappe.flags.in_import = False
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		with self.assertRaisesRegex(frappe.ValidationError, "can only be authored in developer mode"):
			frappe.get_doc("View Type", PROBE).save()

	def test_a_name_that_is_no_view_key_is_refused(self):
		for name in ("Two Words", "Record"):
			with self.assertRaisesRegex(frappe.ValidationError, "cannot name a view type"):
				frappe.get_doc(
					{"doctype": "View Type", "name": name, "label": name, "module": "Desk"}
				).insert()

	def test_boot_carries_every_record(self):
		from frappe.shell.boot import get_boot

		set_request(method="GET", path="/apps/desk")
		self.addCleanup(delattr, frappe.local, "request")
		boot = get_boot("/apps/desk")

		self.assertIn({"name": "List", "label": "List", "icon": "list"}, boot["view_types"])
		self.assertIn({"name": PROBE, "label": "Probe", "icon": None}, boot["view_types"])


class TestTheRules(ViewTypeCase):
	def test_a_type_with_no_rules_file_applies_everywhere_and_takes_any_object(self):
		self.assertTrue(applies_to("List", "ToDo"))
		self.assertEqual(make_view(type="List", label="Any", settings={"anything": 1}).insert().key, "any")

	def test_validate_settings_refuses_a_save(self):
		seen = []

		def validate_settings(doctype, settings):
			seen.append((doctype, settings))
			if "group_by" not in settings:
				frappe.throw("Group cards by a field.")

		self.rules.validate_settings = validate_settings
		with self.assertRaisesRegex(frappe.ValidationError, "Group cards by a field"):
			make_view(settings={"columns": []}).insert()
		make_view(settings={"group_by": "status"}).insert()

		self.assertEqual(seen, [("ToDo", {"columns": []}), ("ToDo", {"group_by": "status"})])

	def test_a_type_that_does_not_apply_is_refused_for_that_doctype(self):
		self.rules.applies_to = lambda meta: meta.name == "ToDo"

		make_view(doctype="ToDo").insert()
		with self.assertRaisesRegex(frappe.ValidationError, "Probe views don't apply to Note"):
			make_view(doctype="Note").insert()
		with self.assertRaisesRegex(frappe.ValidationError, "Probe views don't apply to Note"):
			view_api.get("Note", PROBE)

	def test_applies_to_filters_the_views_read(self):
		make_view(label="Probe board").insert()
		probes = {"probe-46028", "probe-board"}

		self.rules.applies_to = lambda meta: meta.name != "ToDo"
		listed = {view["key"] for view in ViewList().of(["ToDo"])["ToDo"]}
		self.assertIn("list", listed)
		self.assertFalse(probes & listed)

		self.rules.applies_to = lambda meta: meta.name == "ToDo"
		self.assertLessEqual(probes, {view["key"] for view in ViewList().of(["ToDo"])["ToDo"]})


class TestReservedKeys(ViewTypeCase):
	def test_each_record_and_each_survivor_candidate_is_reserved(self):
		self.assertLessEqual(
			{"list", "probe-46028", "kanban", "record", *SURVIVOR_CANDIDATES}, reserved_keys()
		)

	def test_a_view_labelled_as_a_type_or_a_candidate_takes_a_suffix(self):
		keys = [make_view(type="List", label=label).insert().key for label in ("Probe-46028", "Calendar")]
		self.assertEqual(keys, ["probe-46028-2", "calendar-2"])

	def test_no_stored_view_holds_a_reserved_key(self):
		clashing = frappe.get_all("Doctype View", {"key": ("in", list(reserved_keys()))}, pluck="name")
		self.assertEqual(clashing, [])


class TestTheRendererFile(IntegrationTestCase):
	def setUp(self):
		self.root = tempfile.mkdtemp(prefix="test_view_type_46028_")
		self.addCleanup(shutil.rmtree, self.root)

	def ship(self, scrubbed: str, record: bool, renderer: bool):
		folder = os.path.join(self.root, "myapp", "view_type", scrubbed)
		os.makedirs(os.path.join(folder, "frontend"))
		if record:
			with open(os.path.join(folder, f"{scrubbed}.json"), "w") as f:
				f.write(frappe.as_json({"doctype": "View Type", "name": scrubbed.title()}))
		if renderer:
			with open(os.path.join(folder, "frontend", "view.js"), "w") as f:
				f.write('export default { renderer: () => import("./View.vue") }\n')

	def test_a_type_needs_both_its_record_and_its_view_js(self):
		self.ship("cards", record=True, renderer=True)
		self.ship("board", record=True, renderer=False)
		self.ship("wall", record=False, renderer=True)

		problems = view_type_problems("myapp", self.root)

		self.assertEqual(len(problems), 2)
		self.assertIn("board with no frontend/view.js", problems[0])
		self.assertIn("wall/frontend/view.js with no wall.json", problems[1])

	def test_the_build_fails_on_one(self):
		self.ship("board", record=True, renderer=False)
		with patch.object(frappe, "get_app_path", return_value=self.root):
			with self.assertRaisesRegex(ViewTypeFileError, "board with no frontend/view.js"):
				enforce_view_types(["myapp"])

	def test_every_installed_app_ships_both(self):
		enforce_view_types(frappe.get_installed_apps())
