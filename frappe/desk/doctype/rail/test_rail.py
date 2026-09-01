# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import contextlib
from unittest.mock import patch

import frappe
from frappe.desk.doctype.rail.rail import Rail
from frappe.tests import IntegrationTestCase

# An app that is certainly installed on any site running these tests. Which app it is does not
# matter: these tests are about the layers and the rows, not about anyone's actual navigation.
APP = "frappe"


@contextlib.contextmanager
def authoring():
	"""Author app content the way a developer does, without writing a file into the working tree.

	`export_rail` is what makes authoring and shipping one step, and in a test that is a fixture
	leaking into the repo: the database is rolled back afterwards and the file is not.
	"""
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
	def test_the_seven_shipped_types_are_present(self):
		"""The framework's own kinds arrive by migrate, as records rather than through a seeder.

		`Sidebar` and `View` are deliberately absent: each points at a doctype that does not exist
		on this branch yet, and a type row with a wrong target is worse than a missing one.
		"""
		shipped = set(frappe.get_all("Navigation Item Type", pluck="name"))
		self.assertTrue(
			{"DocType", "Record", "Module", "Module Contents", "Page", "Link", "Section"} <= shipped
		)
		self.assertNotIn("Sidebar", shipped)
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
		"""`mount_on` is an app-layer claim, and hiding the field does not stop an API write."""
		rail = make_rail(mount_on="crm")
		rail.insert()
		self.addCleanup(rail.delete)
		self.assertFalse(rail.mount_on)

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
		"""Otherwise a Workspace Manager could take an app's rail and turn it into a site row."""
		with developer_mode(False):
			self.assertRaises(frappe.ValidationError, make_rail(standard=1).insert)

	def test_two_layers_cannot_share_one_address(self):
		"""The database holds this, not a hook, because a bulk write skips the document entirely.

		Two rows at one `(app, user, standard)` would give the merge two answers for one layer.
		"""
		first = make_rail()
		first.insert()
		self.addCleanup(first.delete)

		with self.assertRaises(frappe.UniqueValidationError):
			make_rail().insert()
