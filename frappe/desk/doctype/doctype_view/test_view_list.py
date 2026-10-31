# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.default_view import api as default_view_api
from frappe.desk.doctype.doctype_view.api import list_views
from frappe.desk.doctype.doctype_view.doctype_view import SITE_ROW
from frappe.desk.doctype.doctype_view.test_app_views import AppViewCase, site_row
from frappe.desk.doctype.doctype_view.test_doctype_view import OTHER, PERSON, PRIVATE_DOCTYPE, a_person
from frappe.tests.classes.context_managers import set_user


def todo_view(user: str, label: str, doctype: str = "ToDo") -> "frappe.Document":
	row = frappe.get_doc(
		{"doctype": "Doctype View", "reference_doctype": doctype, "type": "List", "label": label}
	)
	row.user = user
	return row.insert(ignore_permissions=True)


def listed(views: list[dict]) -> list[tuple]:
	return [(view["key"], view["label"], view["layer"]) for view in views]


def default_of(views: list[dict]) -> list[str]:
	return [view["key"] for view in views if view["default"]]


class TestViewList(AppViewCase):
	def setUp(self):
		super().setUp()
		for doctype in ("Doctype View", "Default View"):
			frappe.db.delete(doctype, {"reference_doctype": ("in", ("ToDo", "Note", PRIVATE_DOCTYPE))})
		self.person = a_person(PERSON)
		self.other = a_person(OTHER)

	def test_lists_the_plain_view_then_own_site_and_app_views_each_by_label(self):
		self.folders.own_view("probe-zulu", label="Zulu app")
		self.folders.custom_view("acme", "probe-alpha", label="Alpha app")
		bravo = todo_view(self.person, "Bravo mine")
		alpha = todo_view(self.person, "alpha mine")
		todo_view(self.other, "Not mine")
		site = todo_view(SITE_ROW, "Site one")

		with set_user(self.person):
			views = list_views("ToDo")["ToDo"]

		self.assertEqual(
			listed(views),
			[
				("list", "List", None),
				(alpha.key, "alpha mine", "own"),
				(bravo.key, "Bravo mine", "own"),
				(site.key, "Site one", "site"),
				("probe-alpha", "Alpha app", "app"),
				("probe-zulu", "Zulu app", "app"),
			],
		)
		self.assertEqual(
			views[0], {"key": "list", "label": "List", "type": "List", "layer": None, "default": True}
		)

	def test_views_sharing_a_label_are_listed_by_key(self):
		first, second = todo_view(SITE_ROW, "Twin"), todo_view(SITE_ROW, "Twin")

		self.assertEqual([view["key"] for view in list_views("ToDo")["ToDo"][1:]], [first.key, second.key])

	def test_a_site_row_at_an_app_key_replaces_the_app_view(self):
		self.folders.own_view("probe-open", label="Open probe")
		site_row("probe-open", label="Site's")

		self.assertEqual(listed(list_views("ToDo")["ToDo"])[1:], [("probe-open", "Site's", "site")])

	def test_an_own_view_made_before_an_app_shipped_its_key_is_listed_once_as_the_persons(self):
		todo_view(self.person, "Probe Open")
		self.folders.own_view("probe-open", label="Open probe")

		with set_user(self.person):
			self.assertEqual(listed(list_views("ToDo")["ToDo"])[1:], [("probe-open", "Probe Open", "own")])

	def test_the_plain_list_is_the_default_when_no_layer_names_one(self):
		todo_view(SITE_ROW, "Site one")

		self.assertEqual(default_of(list_views("ToDo")["ToDo"]), ["list"])

	def test_the_resolved_default_is_marked_own_over_site(self):
		site = todo_view(SITE_ROW, "Site one")
		own = todo_view(self.person, "Mine")
		default_view_api.save("ToDo", site.key, "site")

		with set_user(self.person):
			self.assertEqual(default_of(list_views("ToDo")["ToDo"]), [site.key])
			default_view_api.save("ToDo", own.key, "user")
			self.assertEqual(default_of(list_views("ToDo")["ToDo"]), [own.key])

	def test_an_apps_default_is_marked_in_its_prefix_only(self):
		self.folders.custom_view("acme", "probe-acme", label="Acme's", default=True)

		self.assertEqual(default_of(list_views("ToDo", app="acme")["ToDo"]), ["probe-acme"])
		self.assertEqual(default_of(list_views("ToDo", app="zeta")["ToDo"]), ["list"])

	def test_without_a_doctype_lists_each_doctype_the_person_reads_that_has_a_saved_view(self):
		self.folders.own_view("probe-open")
		todo_view(SITE_ROW, "Site note", doctype="Note")
		todo_view(SITE_ROW, "Settings view", doctype=PRIVATE_DOCTYPE)

		with set_user(self.person):
			found = list_views()

		self.assertEqual(listed(found["ToDo"])[1:], [("probe-open", "Probe", "app")])
		self.assertEqual([view["label"] for view in found["Note"]], ["List", "Site note"])
		self.assertNotIn(PRIVATE_DOCTYPE, found)

	def test_without_a_doctype_an_app_view_of_a_doctype_made_on_the_site_is_named_from_the_database(self):
		self.folders.custom_view("acme", "probe-note", doctype="note", label="Acme's notes")

		self.assertEqual(listed(list_views()["Note"])[1:], [("probe-note", "Acme's notes", "app")])

	def test_without_a_doctype_an_app_view_of_a_doctype_the_person_cannot_read_is_left_out(self):
		self.folders.custom_view("acme", "probe-settings", doctype="system_settings")

		self.assertIn(PRIVATE_DOCTYPE, list_views())
		with set_user(self.person):
			self.assertNotIn(PRIVATE_DOCTYPE, list_views())

	def test_a_doctype_the_person_cannot_read_is_refused(self):
		with set_user(self.person), self.assertRaises(frappe.PermissionError):
			list_views(PRIVATE_DOCTYPE)
