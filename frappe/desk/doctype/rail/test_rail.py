# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import contextlib
from unittest.mock import patch

import frappe
from frappe.desk.doctype.rail.rail import Rail
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

# An app that is certainly installed on any site running these tests. Which app it is does not
# matter: these tests are about the layers and the rows, not about anyone's actual navigation.
APP = "frappe"

# Hosts an extension names. Neither has to be installed: `Rail.app` and `Rail.extends` are
# `Autocomplete` columns over installed apps rather than Links, so nothing on the document
# resolves them. Resolution is where an uninstalled app stops counting, and that is tested
# against the resolver in `frappe/tests/test_shell_navigation.py`.
HOST = "erpnext"
OTHER_HOST = "helpdesk"


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
	def test_the_eight_shipped_types_are_present(self):
		"""The framework's own kinds arrive by migrate, as records rather than through a seeder.

		`Sidebar` joined them once desk v2 had a sidebar container for it to point at. `View` is
		still deliberately absent: the doctype it points at is a separate effort, and a type row
		with a wrong target is worse than a missing one.
		"""
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
		"""They share a target doctype and are told apart by what they do with it. `Module` opens a
		module's page and is visible when anything in the module is readable; `Module Contents` is
		the overflow row that expands into what is left, so it drops when nothing survives under
		it, exactly as a `Section` does.
		"""
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
		"""`extends` is an app-layer claim, and hiding the field does not stop an API write.

		A site or user row naming a host would be one person's arrangement filed onto a rail
		they do not own — and it is unnecessary besides, since arranging a host rail is one row
		at the host's own address covering every contributed item in the list.
		"""
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
		"""An app ships its own rail and one record per host, so the app name is not enough.

		The record name is the export path, so two records sharing a name would overwrite one
		file — which is exactly what `mount_on`'s single column made unavoidable.
		"""
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
		"""The whole reason `mount_on` came off: a scalar could name one host, and Payments and
		Telephony each extend ERPNext *or* CRM *or* Helpdesk, choosing per site.

		This is also what the old three-column index made unstorable rather than merely
		unresolvable — every one of these rows is `(app, "", 1)` under it.
		"""
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
		"""The index widened; it did not stop enforcing one layer per address.

		A shipped row is refused by name rather than by the index, and says so: its name is its
		address, so the second one collides on the primary key — which `db_insert` reads as a
		hash collision, retries five times against an `autoname` that keeps returning the same
		string, and then re-raises the driver's own error naming a column and no cause.
		"""
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
		"""The database holds this, not a hook, because a bulk write skips the document entirely.

		Two rows at one `(app, user, standard)` would give the merge two answers for one layer.
		"""
		first = make_rail()
		first.insert()
		self.addCleanup(first.delete)

		with self.assertRaises(frappe.UniqueValidationError):
			make_rail().insert()

	def test_a_person_lists_only_their_own_layer(self):
		"""The list query is the half `has_permission` does not cover.

		Reports, the API and the desk's own export go through the query condition rather than
		through the document check, so without it a `Desk User`'s read would be a read of
		everyone else's arrangements.
		"""
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

		# `get_list`, not `get_all`: the latter bypasses permissions by design, so it would pass
		# whether or not the condition exists.
		with set_user(person.name):
			visible = frappe.get_list("Rail", pluck="name")

		self.assertEqual(visible, [mine.name])
