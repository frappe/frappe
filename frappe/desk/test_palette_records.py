# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.palette import search_records
from frappe.shell.links import canonical_path
from frappe.tests import IntegrationTestCase

READER = "palette-reader@example.com"
ROLE = "Palette Reader"


class TestSearchRecords(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.get_doc(doctype="Role", role_name=ROLE, desk_access=1).insert(ignore_if_duplicate=True)
		if not frappe.db.exists("User", READER):
			frappe.get_doc(
				doctype="User", email=READER, first_name="Palette", roles=[{"role": ROLE}]
			).insert()
		cls.readable = [readable_doctype() for _ in range(4)]
		cls.titled = readable_doctype(title_field="some_fieldname", show_title_field_in_link=1)
		cls.single = readable_doctype(issingle=1)
		cls.closed = new_doctype(autoname="Prompt").insert().name
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		for doctype in [*cls.readable, cls.titled, cls.single, cls.closed]:
			frappe.delete_doc("DocType", doctype, force=True)
		frappe.delete_doc("User", READER, force=True)
		frappe.delete_doc("Role", ROLE, force=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_unreadable_doctype_is_never_searched(self):
		first = self.readable[0]
		add_records(self.closed, "Kestrel")
		add_records(first, "Kestrel Ridge")

		with listed([self.closed, first]), self.set_user(READER):
			found = search_records("Kestrel", doctype=self.closed)

		self.assertEqual(
			without_route(found), [{"doctype": first, "name": "Kestrel Ridge", "label": "Kestrel Ridge"}]
		)

	def test_exact_name_comes_first(self):
		first, second = self.readable[:2]
		add_records(first, "Kestrel Alpha", "Kestrel Beta", "Kestrel Gamma")
		add_records(second, "kestrel")

		with listed([first, second]), self.set_user(READER):
			found = search_records("Kestrel")

		self.assertEqual([row["name"] for row in found][:1], ["kestrel"])
		self.assertEqual([row["doctype"] for row in found], [second, first, first, first])

	def test_exact_name_is_kept_behind_three_newer_matches(self):
		first = self.readable[0]
		add_records(first, "Kestrel_1", "Kestrel_1 Alpha", "Kestrel_1 Beta", "Kestrel_1 Gamma", "Kestrel11")

		with listed([first]), self.set_user(READER):
			found = search_records("kestrel_1")

		self.assertEqual([row["name"] for row in found][:1], ["Kestrel_1"])
		self.assertEqual(len(found), 3)

	def test_current_doctype_comes_before_the_listed_ones(self):
		first, current = self.readable[:2]
		add_records(first, "Kestrel Alpha")
		add_records(current, "Kestrel Beta")

		with listed([first]), self.set_user(READER):
			found = search_records("Kestrel", doctype=current)

		self.assertEqual([row["doctype"] for row in found], [current, first])

	def test_three_per_doctype_and_ten_in_all(self):
		for doctype in self.readable:
			add_records(doctype, *(f"Kestrel {n}" for n in range(4)))

		with listed(self.readable), self.set_user(READER):
			found = search_records("Kestrel")

		counts = [sum(row["doctype"] == doctype for row in found) for doctype in self.readable]
		self.assertEqual(counts, [3, 3, 3, 1])

	def test_label_is_the_title_where_links_show_titles(self):
		frappe.get_doc(doctype=self.titled, name="KES-0001", some_fieldname="Kestrel Ridge").insert()

		with listed([self.titled]), self.set_user(READER):
			found = search_records("Kestrel")

		self.assertEqual(
			without_route(found), [{"doctype": self.titled, "name": "KES-0001", "label": "Kestrel Ridge"}]
		)

	def test_a_record_carries_its_v2_address_without_the_host(self):
		first = self.readable[0]
		add_records(first, "Kestrel Ridge")

		with (
			listed([first]),
			self.set_user(READER),
			patch("frappe.utils.data.is_desk_v2_enabled", return_value=True),
		):
			found = search_records("Kestrel")

		self.assertEqual([row["route"] for row in found], [canonical_path(first, "Kestrel Ridge")])
		self.assertTrue(found[0]["route"].startswith("/apps/"))

	def test_single_is_skipped(self):
		first = self.readable[0]
		add_records(first, "Kestrel")

		with listed([self.single, first]), self.set_user(READER):
			found = search_records("Kestrel", doctype=self.single)

		self.assertEqual([row["doctype"] for row in found], [first])

	def test_short_query_searches_nothing(self):
		add_records(self.readable[0], "K9")

		with listed(self.readable), self.set_user(READER):
			self.assertEqual(search_records(" K "), [])


def readable_doctype(**properties) -> str:
	doctype = new_doctype(autoname="Prompt", **properties)
	doctype.append("permissions", {"role": ROLE, "read": 1, "write": 0, "create": 0, "delete": 0})
	return doctype.insert().name


def add_records(doctype: str, *names: str):
	for name in names:
		frappe.get_doc(doctype=doctype, name=name).insert()


def listed(doctypes: list[str]):
	return patch("frappe.desk.palette.get_doctypes_for_global_search", return_value=doctypes)


def without_route(found: list[dict]) -> list[dict]:
	"""The rows without their address, which its own test checks."""
	return [{key: value for key, value in row.items() if key != "route"} for row in found]
