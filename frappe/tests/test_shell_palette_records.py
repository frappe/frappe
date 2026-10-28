# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.record_title import RecordTitles
from frappe.shell import SHELL_ROOT
from frappe.shell.doctypes import get_shell_doctypes, slug
from frappe.shell.links import canonical_path
from frappe.shell.palette import places, search_doctype_records, search_records
from frappe.tests import IntegrationTestCase
from frappe.utils.logging import get_log_db, log_table

READER = "palette-reader@example.com"
ROLE = "Palette Reader"


class PaletteRecordsCase(IntegrationTestCase):
	"""The reader, the doctypes it can and cannot read, and a rollback after each test."""

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
		cls.titled_plain_links = readable_doctype(title_field="some_fieldname")
		cls.rich_titled = readable_doctype(
			title_field="some_fieldname",
			fields=[{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Text Editor"}],
		)
		cls.translated = readable_doctype(title_field="some_fieldname", translated_doctype=1)
		cls.virtual_titled = readable_doctype(
			title_field="loud_title",
			fields=[
				{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Data"},
				{
					"label": "Loud Title",
					"fieldname": "loud_title",
					"fieldtype": "Data",
					"is_virtual": 1,
					"options": "(doc.some_fieldname or '').upper()",
				},
			],
		)
		cls.restricted_title = readable_doctype(
			title_field="some_fieldname",
			fields=[
				{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Data", "permlevel": 1}
			],
		)
		cls.single = readable_doctype(issingle=1)
		cls.closed = new_doctype(autoname="Prompt").insert().name
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		for doctype in [
			*cls.readable,
			cls.titled,
			cls.titled_plain_links,
			cls.rich_titled,
			cls.translated,
			cls.virtual_titled,
			cls.restricted_title,
			cls.single,
			cls.closed,
		]:
			frappe.delete_doc("DocType", doctype, force=True)
		frappe.delete_doc("User", READER, force=True)
		frappe.delete_doc("Role", ROLE, force=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def tearDown(self):
		frappe.db.rollback()


class TestSearchRecords(PaletteRecordsCase):
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

	def test_label_is_the_title_where_links_show_names(self):
		titled = self.titled_plain_links
		frappe.get_doc(doctype=titled, name="KES-0002", some_fieldname="Kestrel Hollow").insert()
		frappe.get_doc(doctype=titled, name="Kestrel Untitled").insert()

		with listed([titled]), self.set_user(READER):
			found = search_records("Kestrel")

		self.assertEqual(
			sorted(without_route(found), key=lambda row: row["name"]),
			[
				{"doctype": titled, "name": "KES-0002", "label": "Kestrel Hollow"},
				{"doctype": titled, "name": "Kestrel Untitled", "label": "Kestrel Untitled"},
			],
		)

	def test_a_rich_text_title_is_plain_text(self):
		frappe.get_doc(
			doctype=self.rich_titled, name="KES-0003", some_fieldname="<p>Kestrel &amp; Hawk</p>"
		).insert()

		with listed([self.rich_titled]), self.set_user(READER):
			found = search_records("Kestrel")

		self.assertEqual([row["label"] for row in found], ["Kestrel & Hawk"])

	def test_a_hooked_query_is_titled_too(self):
		with listed(["User"]):
			found = search_records(READER)

		self.assertEqual(without_route(found), [{"doctype": "User", "name": READER, "label": "Palette"}])

	def test_label_is_the_name_without_a_title_field(self):
		first = self.readable[0]
		add_records(first, "Kestrel Ridge")

		with listed([first]), self.set_user(READER):
			found = search_records("Kestrel")

		self.assertEqual([(row["name"], row["label"]) for row in found], [("Kestrel Ridge", "Kestrel Ridge")])

	def test_each_record_carries_its_address_on_its_owners_app_without_the_host(self):
		first, second = self.readable[:2]
		add_records(first, "Kestrel Ridge")
		add_records(second, "Kestrel Moor")
		shell = get_shell_doctypes()
		owned = {**shell, "owners": {**shell["owners"], second: "acme"}}

		# with desk v2 off, get_url_to_form would give a /desk/ address
		with (
			listed([first, second]),
			self.set_user(READER),
			patch("frappe.utils.data.is_desk_v2_enabled", return_value=False),
			patch("frappe.shell.links.get_shell_doctypes", return_value=owned),
			patch("frappe.shell.links.declared_prefix", side_effect=lambda app: f"{app}-prefix"),
			patch("frappe.shell.links.is_modular", return_value=False),
		):
			found = search_records("Kestrel")

		self.assertEqual(
			{row["name"]: row["route"] for row in found},
			{
				"Kestrel Ridge": f"/{SHELL_ROOT}/frappe-prefix/{slug(first)}/Kestrel%20Ridge",
				"Kestrel Moor": f"/{SHELL_ROOT}/acme-prefix/{slug(second)}/Kestrel%20Moor",
			},
		)

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


class TestSearchDoctypeRecords(PaletteRecordsCase):
	def test_ten_of_one_doctype_titled_and_exact_name_first(self):
		titled = self.titled_plain_links
		for n in range(11):
			frappe.get_doc(doctype=titled, name=f"KES-{n:02}", some_fieldname=f"Kestrel {n}").insert()
		frappe.get_doc(doctype=titled, name="kestrel").insert()

		with self.set_user(READER):
			found = search_doctype_records(titled, "Kestrel")

		self.assertEqual(len(found), 10)
		self.assertEqual(found[0]["name"], "kestrel")
		self.assertEqual({row["doctype"] for row in found}, {titled})
		self.assertEqual(
			[row["label"] for row in found[1:]], [f"Kestrel {int(row['name'][4:])}" for row in found[1:]]
		)

	def test_unreadable_or_single_doctype_finds_nothing(self):
		add_records(self.closed, "Kestrel")

		with self.set_user(READER):
			self.assertEqual(search_doctype_records(self.closed, "Kestrel"), [])
			self.assertEqual(search_doctype_records(self.single, "Kestrel"), [])

	def test_short_query_finds_nothing(self):
		add_records(self.readable[0], "K9")

		with self.set_user(READER):
			self.assertEqual(search_doctype_records(self.readable[0], " K "), [])


class TestRecordsFollowGoTo(PaletteRecordsCase):
	"""A doctype whose owner app the person may not enter is neither listed by Go to nor searched."""

	def test_search_records_leaves_out_a_doctype_of_an_app_the_person_may_not_enter(self):
		first, second = self.readable[:2]
		add_records(first, "Kestrel Ridge")
		add_records(second, "Kestrel Moor")

		with listed([first, second]), self.set_user(READER), owned_by_acme(second, may_enter=False):
			found = search_records("Kestrel", doctype=second)
			goes_to = {row["name"] for row in places()["doctypes"]}

		self.assertEqual([row["name"] for row in found], ["Kestrel Ridge"])
		self.assertIn(first, goes_to)
		self.assertNotIn(second, goes_to)

	def test_search_doctype_records_refuses_a_doctype_of_an_app_the_person_may_not_enter(self):
		first = self.readable[0]
		add_records(first, "Kestrel Ridge")

		with self.set_user(READER), owned_by_acme(first, may_enter=False):
			self.assertEqual(search_doctype_records(first, "Kestrel"), [])

	def test_a_person_who_may_enter_the_owner_app_still_finds_its_records(self):
		first = self.readable[0]
		add_records(first, "Kestrel Ridge")

		with listed([first]), self.set_user(READER), owned_by_acme(first, may_enter=True):
			found = search_records("Kestrel")
			narrowed = search_doctype_records(first, "Kestrel")

		self.assertEqual([row["name"] for row in found], ["Kestrel Ridge"])
		self.assertEqual([row["name"] for row in narrowed], ["Kestrel Ridge"])

	def test_a_doctype_without_an_address_is_not_searched(self):
		first, second = self.readable[:2]
		add_records(first, "Kestrel Ridge")
		add_records(second, "Kestrel Moor")
		shell = get_shell_doctypes()
		addressed = {
			doctype: path for doctype, path in shell["table"]["doctypes"].items() if doctype != second
		}
		unaddressed = {**shell, "table": {**shell["table"], "doctypes": addressed}}

		with (
			listed([first, second]),
			self.set_user(READER),
			patch("frappe.shell.palette.get_shell_doctypes", return_value=unaddressed),
		):
			found = search_records("Kestrel")
			narrowed = search_doctype_records(second, "Kestrel")

		self.assertEqual([row["name"] for row in found], ["Kestrel Ridge"])
		self.assertEqual(narrowed, [])


class TestRecentAndRecordsAgree(PaletteRecordsCase):
	"""One record has one title, whether the palette's Recent or its Records lists it."""

	def setUp(self):
		super().setUp()
		clear_visits()
		self.addCleanup(clear_visits)

	def test_a_rich_text_title(self):
		frappe.get_doc(
			doctype=self.rich_titled, name="Kestrel Ridge", some_fieldname="<p>Kestrel &amp; Hawk</p>"
		).insert()

		self.assertEqual(self.titles_of(self.rich_titled, "Kestrel Ridge"), ["Kestrel & Hawk"] * 2)

	def test_a_data_title_holding_markup(self):
		# saving sanitises a Data value that holds tags, so it is stored as "Kestrel <b>&amp;</b> Hawk"
		frappe.get_doc(
			doctype=self.titled, name="Kestrel Ridge", some_fieldname="Kestrel <b>&</b> Hawk"
		).insert()

		self.assertEqual(self.titles_of(self.titled, "Kestrel Ridge"), ["Kestrel & Hawk"] * 2)

	def test_a_translated_doctypes_title(self):
		frappe.get_doc(doctype=self.translated, name="Kestrel Ridge", some_fieldname="Kestrel Hawk").insert()

		with patch("frappe.desk.record_title._", side_effect=lambda text: f"Turmfalke ({text})"):
			titles = self.titles_of(self.translated, "Kestrel Ridge")

		self.assertEqual(titles, ["Turmfalke (Kestrel Hawk)"] * 2)

	def test_a_virtual_title_field(self):
		frappe.get_doc(
			doctype=self.virtual_titled, name="Kestrel Ridge", some_fieldname="Kestrel Hawk"
		).insert()

		self.assertEqual(self.titles_of(self.virtual_titled, "Kestrel Ridge"), ["KESTREL HAWK"] * 2)

	def test_a_title_field_the_person_may_not_read_gives_the_name(self):
		frappe.get_doc(doctype=self.restricted_title, name="Kestrel Ridge", some_fieldname="Secret").insert()
		self.visit(self.restricted_title, "Kestrel Ridge")

		with self.set_user(READER):
			[recent] = places()["recent"]
			# search_widget refuses this doctype, so a row that carries the column stands in for Records
			record = RecordTitles(self.restricted_title).of(
				[{"name": "Kestrel Ridge", "some_fieldname": "Secret"}]
			)

		self.assertEqual([recent["title"], record["Kestrel Ridge"]], ["Kestrel Ridge"] * 2)

	def titles_of(self, doctype: str, name: str) -> list[str]:
		"""The record's title in the palette's Recent, after one visit, and in its Records."""
		self.visit(doctype, name)
		with listed([doctype]), self.set_user(READER):
			[recent] = places()["recent"]
			[record] = search_records(name)
		return [recent["title"], record["label"]]

	def visit(self, doctype: str, name: str):
		frappe.get_doc(doctype="Route History", route=canonical_path(doctype, name), user=READER).db_insert()


def clear_visits():
	qb, table = log_table("Route History")
	db = get_log_db()
	db.sql(qb.from_(table).where(table.user == READER).delete())
	db.commit()


def readable_doctype(**properties) -> str:
	doctype = new_doctype(autoname="Prompt", **properties)
	doctype.append("permissions", {"role": ROLE, "read": 1, "write": 0, "create": 0, "delete": 0})
	return doctype.insert().name


def add_records(doctype: str, *names: str):
	for name in names:
		frappe.get_doc(doctype=doctype, name=name).insert()


def listed(doctypes: list[str]):
	return patch("frappe.shell.palette.get_doctypes_for_global_search", return_value=doctypes)


@contextmanager
def owned_by_acme(doctype: str, may_enter: bool):
	"""`doctype` owned by the app `acme`, whose `app_permission` hook lets the person in or not."""
	shell = get_shell_doctypes()
	owned = {**shell, "owners": {**shell["owners"], doctype: "acme"}}
	gate = f"{__name__}.{'acme_lets_in' if may_enter else 'acme_keeps_out'}"
	get_hooks = frappe.get_hooks

	def hooks(hook=None, *args, **kwargs):
		if hook == "app_permission" and kwargs.get("app_name") == "acme":
			return [gate]
		return get_hooks(hook, *args, **kwargs)

	with (
		patch("frappe.shell.palette.get_shell_doctypes", return_value=owned),
		patch("frappe.get_hooks", side_effect=hooks),
	):
		yield


def acme_lets_in() -> bool:
	return True


def acme_keeps_out() -> bool:
	return False


def without_route(found: list[dict]) -> list[dict]:
	"""The rows without their address, which its own test checks."""
	return [{key: value for key, value in row.items() if key != "route"} for row in found]
