# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import contextlib
from unittest.mock import patch

import frappe
from frappe.desk.doctype.rail.rail import Rail
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

# Any app certainly installed on a site running these tests.
APP = "frappe"

# Hosts need not be installed: `Rail.app` and `Rail.extends` are `Autocomplete`, not Links.
HOST = "erpnext"
OTHER_HOST = "helpdesk"


@contextlib.contextmanager
def authoring():
	"""Author app content as a developer, with `export_rail` patched so no file lands in the working tree."""
	with developer_mode(True), patch.object(Rail, "export_rail"):
		yield


@contextlib.contextmanager
def developer_mode(on: bool):
	original = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 1 if on else 0
	try:
		yield
	finally:
		frappe.conf.developer_mode = original


def make_rail(**kwargs):
	"""Build an unsaved rail, defaulting to a site layer so a test opts in to app content."""
	doc = frappe.get_doc({"doctype": "Rail", "app": APP, **kwargs})
	return doc


def item(**kwargs):
	return {"doctype": "Navigation Item", "item_type": "DocType", **kwargs}


class TestRail(IntegrationTestCase):
	def test_the_eight_shipped_types_are_present(self):
		"""The framework's own kinds arrive by migrate; `View` is deliberately absent until its doctype exists."""
		shipped = set(frappe.get_all("Navigation Item Type", pluck="name"))
		self.assertTrue(
			{"DocType", "Record", "Module", "Module Contents", "Page", "Link", "Section", "Sidebar"}
			<= shipped
		)
		self.assertNotIn("View", shipped)

	def test_a_type_declares_its_permission_bucket(self):
		"""Every kind names the rule that filters it, so a new kind writes no permission code."""
		buckets = dict(
			frappe.get_all("Navigation Item Type", fields=["name", "permission_rule"], as_list=True)
		)
		self.assertEqual(buckets["DocType"], "Readable DocType")
		self.assertEqual(buckets["Module"], "Module Contents")
		self.assertEqual(buckets["Section"], "Derived From Children")
		self.assertEqual(buckets["Link"], "Always Visible")

	def test_module_and_module_contents_are_two_kinds(self):
		"""They share a target doctype and are told apart by their permission rule."""
		buckets = dict(
			frappe.get_all("Navigation Item Type", fields=["name", "permission_rule"], as_list=True)
		)
		self.assertEqual(buckets["Module"], "Module Contents")
		self.assertEqual(buckets["Module Contents"], "Derived From Children")

	def test_nobody_may_author_a_type_outside_developer_mode(self):
		"""A kind is code, so minting one is a developer act and not a permission a role carries."""
		with developer_mode(False):
			self.assertRaises(
				frappe.ValidationError,
				frappe.get_doc(
					{
						"doctype": "Navigation Item Type",
						"type_name": "Invented",
						"module": "Desk",
						"permission_rule": "Always Visible",
					}
				).insert,
			)

	def test_an_app_layer_needs_a_key_on_every_row(self):
		"""A shipped row with no key cannot be customized, and would fail silently at read time."""
		rail = make_rail(standard=1, items=[item(link_to="User", label="Users")])
		with authoring():
			self.assertRaises(frappe.ValidationError, rail.insert)

	def test_an_app_layer_refuses_two_rows_with_one_key(self):
		"""Two rows at one address means one delta reaching both, so it is refused at write time."""
		rail = make_rail(
			standard=1,
			items=[
				item(key="users", link_to="User", label="Users"),
				item(key="users", link_to="Role", label="Roles"),
			],
		)
		with authoring():
			self.assertRaises(frappe.ValidationError, rail.insert)

	def test_a_layer_is_not_asked_for_keys(self):
		"""A site or user layer addresses base rows by their key; its own rows are minted on export."""
		rail = make_rail(items=[item(link_to="User", label="Users")])
		rail.insert()
		self.addCleanup(rail.delete)
		self.assertTrue(rail.name)

	def test_the_type_fixes_the_destination_doctype(self):
		"""`link_doctype` comes off the type, so a row cannot point into the wrong table."""
		rail = make_rail(
			items=[
				item(item_type="DocType", link_to="User", label="Users"),
				item(item_type="Module", link_to="Desk", label="Desk"),
			]
		)
		rail.insert()
		self.addCleanup(rail.delete)
		self.assertEqual(rail.items[0].link_doctype, "DocType")
		self.assertEqual(rail.items[1].link_doctype, "Module Def")

	def test_a_record_row_keeps_the_doctype_it_was_given(self):
		"""`Record` is the one kind that leaves the target to the item, so nothing overwrites it."""
		rail = make_rail(items=[item(item_type="Record", link_doctype="User", link_to="Administrator")])
		rail.insert()
		self.addCleanup(rail.delete)
		self.assertEqual(rail.items[0].link_doctype, "User")

	def test_a_site_layer_cannot_claim_another_apps_rail(self):
		"""`extends` is an app-layer claim, and hiding the field does not stop an API write."""
		rail = make_rail(extends=HOST)
		rail.insert()
		self.addCleanup(rail.delete)
		self.assertFalse(rail.extends)

	def test_an_app_cannot_extend_itself(self):
		"""It is its own rail written twice, and both copies would merge into one list."""
		rail = make_rail(standard=1, extends=APP, items=[item(key="users", link_to="User")])
		with authoring():
			self.assertRaises(frappe.ValidationError, rail.insert)

	def test_an_extension_is_named_after_the_address_and_not_the_app(self):
		"""An app ships its own rail and one record per host, so the app name alone is not enough."""
		own = make_rail(standard=1, items=[item(key="users", link_to="User")])
		extension = make_rail(standard=1, extends=HOST, items=[item(key="users", link_to="User")])
		with authoring():
			own.insert()
			self.addCleanup(own.delete)
			extension.insert()
			self.addCleanup(extension.delete)

		self.assertEqual(own.name, APP)
		self.assertEqual(extension.name, f"{APP}-{HOST}")

	def test_one_app_may_extend_two_hosts_and_keep_its_own_rail(self):
		"""One app extends several hosts, each as its own record beside its own rail."""
		with authoring():
			for extends in ("", HOST, OTHER_HOST):
				rail = make_rail(standard=1, extends=extends, items=[item(key="users", link_to="User")])
				rail.insert()
				self.addCleanup(rail.delete)

		self.assertEqual(
			frappe.db.count("Rail", {"app": APP, "standard": 1}),
			3,
		)

	def test_two_extensions_of_one_host_by_one_app_are_still_refused(self):
		"""A second shipped row at one address is refused by name, with a message and not a driver error."""
		with authoring():
			first = make_rail(standard=1, extends=HOST, items=[item(key="users", link_to="User")])
			first.insert()
			self.addCleanup(first.delete)

			with self.assertRaises(frappe.ValidationError):
				make_rail(standard=1, extends=HOST, items=[item(key="roles", link_to="Role")]).insert()

	def test_a_layer_with_no_user_is_the_site_layer(self):
		"""One spelling of "not a user's own", so two site layers cannot look like one address."""
		rail = make_rail()
		rail.insert()
		self.addCleanup(rail.delete)
		self.assertEqual(rail.user, "")

	def test_an_app_layer_is_named_after_its_app(self):
		"""The record name is the export path, so a hash-named standard rail would orphan its file."""
		rail = make_rail(standard=1, items=[item(key="users", link_to="User", label="Users")])
		with authoring():
			rail.insert()
		self.addCleanup(rail.delete)
		self.assertEqual(rail.name, APP)

	def test_app_content_is_not_writable_outside_developer_mode(self):
		"""Otherwise anyone who may curate the site could take an app's rail and turn it into a site row."""
		with developer_mode(False):
			self.assertRaises(frappe.ValidationError, make_rail(standard=1).insert)

	def test_two_layers_cannot_share_one_address(self):
		"""The database holds this, not a hook, because a bulk write skips the document entirely."""
		first = make_rail()
		first.insert()
		self.addCleanup(first.delete)

		with self.assertRaises(frappe.UniqueValidationError):
			make_rail().insert()

	def test_a_person_lists_only_their_own_layer(self):
		"""The list query is the half `has_permission` does not cover."""
		site = make_rail()
		site.insert()
		self.addCleanup(site.delete)

		person = frappe.get_doc(
			{
				"doctype": "User",
				"email": "rail-layer-tester@example.com",
				"first_name": "Rail",
				"roles": [{"role": "Desk User"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(person.delete)

		mine = make_rail(user=person.name)
		mine.insert()
		self.addCleanup(mine.delete)

		# `get_list`, not `get_all`, which bypasses permissions and would pass either way.
		with set_user(person.name):
			visible = frappe.get_list("Rail", pluck="name")

		self.assertEqual(visible, [mine.name])
