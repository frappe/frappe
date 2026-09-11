# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.page.permission_manager.permission_manager import add, reset, update
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.form.load import get_docinfo, get_versions, getdoc, getdoctype
from frappe.share import add as add_share
from frappe.tests import IntegrationTestCase
from frappe.tests.test_helpers import setup_for_tests
from frappe.utils.file_manager import save_file


class TestFormLoad(IntegrationTestCase):
	def test_load(self):
		getdoctype("DocType")
		meta = next(filter(lambda d: d.name == "DocType", frappe.response.docs))
		self.assertEqual(meta.name, "DocType")
		self.assertTrue(meta.get("__js"))

		frappe.response.docs = []
		getdoctype("Event")
		meta = next(filter(lambda d: d.name == "Event", frappe.response.docs))
		self.assertTrue(meta.get("__calendar_js"))

	def test_fieldlevel_permissions_in_load(self):
		setup_for_tests()
		blog = frappe.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category 1",
				"blog_intro": "Test Blog Intro",
				"blogger": "_Test Blogger 1",
				"content": "Test Blog Content",
				"title": f"_Test Blog Post {frappe.utils.now()}",
				"published": 0,
			}
		)

		blog.insert()

		user = frappe.get_doc("User", "test@example.com")

		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles("Blogger")

		blog_post_property_setter = make_property_setter("Test Blog Post", "published", "permlevel", 1, "Int")
		reset("Test Blog Post")

		# test field level permission before role level permissions are defined
		frappe.set_user(user.name)
		blog_doc = get_blog(blog.name)

		with self.assertRaises(AttributeError):
			blog_doc.published

		# this will be ignored because user does not
		# have write access on `published` field (or on permlevel 1 fields)
		blog_doc.published = 1
		blog_doc.save()

		# since published field has higher permlevel
		self.assertEqual(blog_doc.published, 0)

		# test field level permission after role level permissions are defined
		frappe.set_user("Administrator")
		add("Test Blog Post", "Website Manager", 1)
		update("Test Blog Post", "Website Manager", 1, "write", 1)

		frappe.set_user(user.name)
		blog_doc = get_blog(blog.name)

		self.assertEqual(blog_doc.name, blog.name)
		# since published field has higher permlevel
		with self.assertRaises(AttributeError):
			blog_doc.published

		# this will be ignored because user does not
		# have write access on `published` field (or on permlevel 1 fields)
		blog_doc.published = 1
		blog_doc.save()

		# since published field has higher permlevel
		self.assertEqual(blog_doc.published, 0)

		frappe.set_user("Administrator")
		user.add_roles("Website Manager")
		frappe.set_user(user.name)

		doc = frappe.get_doc("Test Blog Post", blog.name)
		doc.published = 1
		doc.save()

		blog_doc = get_blog(blog.name)
		# now user should be allowed to read field with higher permlevel
		# (after adding Website Manager role)
		self.assertEqual(blog_doc.published, 1)

		frappe.set_user("Administrator")

		# reset user roles
		user.remove_roles("Blogger", "Website Manager")
		user.add_roles(*user_roles)

		blog_doc.delete()
		frappe.delete_doc(blog_post_property_setter.doctype, blog_post_property_setter.name)

	def test_fieldlevel_permissions_in_load_for_child_table(self):
		contact = frappe.new_doc("Contact")
		contact.first_name = "_Test Contact 1"
		contact.append("phone_nos", {"phone": "123456"})
		contact.insert()

		user = frappe.get_doc("User", "test@example.com")

		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles("Accounts User")

		make_property_setter("Contact Phone", "phone", "permlevel", 1, "Int")
		reset("Contact Phone")
		add("Contact", "Sales User", 1)
		update("Contact", "Sales User", 1, "write", 1)

		frappe.set_user(user.name)

		contact = frappe.get_doc("Contact", "_Test Contact 1")

		contact.phone_nos[0].phone = "654321"
		contact.save()

		self.assertEqual(contact.phone_nos[0].phone, "123456")

		frappe.set_user("Administrator")
		user.add_roles("Sales User")
		frappe.set_user(user.name)

		contact.phone_nos[0].phone = "654321"
		contact.save()

		contact = frappe.get_doc("Contact", "_Test Contact 1")
		self.assertEqual(contact.phone_nos[0].phone, "654321")

		frappe.set_user("Administrator")

		# reset user roles
		user.remove_roles("Accounts User", "Sales User")
		user.add_roles(*user_roles)

		contact.delete()

	def test_get_attachments_filters_permlevel_restricted_top_level_field(self):
		from frappe.desk.form.load import get_attachments

		blog = frappe.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category 1",
				"blog_intro": "Test Blog Intro",
				"blogger": "_Test Blogger 1",
				"content": "Test Blog Content",
				"title": f"_Test Blog Post {frappe.utils.now()}",
				"published": 0,
			}
		)
		blog.insert()

		unrestricted_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "unrestricted.png",
				"content": b"unrestricted-bytes",
				"attached_to_doctype": blog.doctype,
				"attached_to_name": blog.name,
				"attached_to_field": "content",
			}
		).insert()
		restricted_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "restricted.png",
				"content": b"restricted-bytes",
				"attached_to_doctype": blog.doctype,
				"attached_to_name": blog.name,
				"attached_to_field": "published",
			}
		).insert()

		user = frappe.get_doc("User", "test@example.com")
		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles("Blogger")

		blog_post_property_setter = make_property_setter("Test Blog Post", "published", "permlevel", 1, "Int")
		reset("Test Blog Post")

		try:
			# Blogger only has permlevel-0 access: the restricted attachment must be hidden
			frappe.set_user(user.name)
			names = {f.file_name for f in get_attachments(blog.doctype, blog.name)}
			self.assertIn("unrestricted.png", names)
			self.assertNotIn("restricted.png", names)

			# granting permlevel-1 read access makes the restricted attachment visible again
			frappe.set_user("Administrator")
			add("Test Blog Post", "Website Manager", 1)
			update("Test Blog Post", "Website Manager", 1, "read", 1)
			user.add_roles("Website Manager")

			frappe.set_user(user.name)
			names = {f.file_name for f in get_attachments(blog.doctype, blog.name)}
			self.assertEqual(names, {"unrestricted.png", "restricted.png"})

			# Administrator always bypasses permlevel restrictions
			frappe.set_user("Administrator")
			names = {f.file_name for f in get_attachments(blog.doctype, blog.name)}
			self.assertEqual(names, {"unrestricted.png", "restricted.png"})
		finally:
			frappe.set_user("Administrator")
			user.remove_roles("Blogger", "Website Manager")
			user.add_roles(*user_roles)
			unrestricted_file.delete()
			restricted_file.delete()
			blog.delete()
			frappe.delete_doc(blog_post_property_setter.doctype, blog_post_property_setter.name)

	def test_get_attachments_filters_permlevel_restricted_child_table_field(self):
		from frappe.desk.form.load import get_attachments

		contact = frappe.new_doc("Contact")
		contact.first_name = "_Test Contact 1"
		contact.append("phone_nos", {"phone": "123456"})
		contact.insert()

		unrestricted_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "unrestricted.png",
				"content": b"unrestricted-bytes",
				"attached_to_doctype": contact.doctype,
				"attached_to_name": contact.name,
				"attached_to_field": "first_name",
			}
		).insert()
		restricted_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "restricted.png",
				"content": b"restricted-bytes",
				"attached_to_doctype": contact.doctype,
				"attached_to_name": contact.name,
				"attached_to_field": "phone",
			}
		).insert()

		user = frappe.get_doc("User", "test@example.com")
		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles("Accounts User")

		contact_phone_property_setter = make_property_setter("Contact Phone", "phone", "permlevel", 1, "Int")
		reset("Contact Phone")

		try:
			# Accounts User only has permlevel-0 access: the restricted attachment must be hidden
			frappe.set_user(user.name)
			names = {f.file_name for f in get_attachments(contact.doctype, contact.name)}
			self.assertIn("unrestricted.png", names)
			self.assertNotIn("restricted.png", names)

			# granting permlevel-1 read access makes the restricted attachment visible again
			frappe.set_user("Administrator")
			add("Contact", "Sales User", 1)
			update("Contact", "Sales User", 1, "read", 1)
			user.add_roles("Sales User")

			frappe.set_user(user.name)
			names = {f.file_name for f in get_attachments(contact.doctype, contact.name)}
			self.assertEqual(names, {"unrestricted.png", "restricted.png"})

			# Administrator always bypasses permlevel restrictions
			frappe.set_user("Administrator")
			names = {f.file_name for f in get_attachments(contact.doctype, contact.name)}
			self.assertEqual(names, {"unrestricted.png", "restricted.png"})
		finally:
			frappe.set_user("Administrator")
			user.remove_roles("Accounts User", "Sales User")
			user.add_roles(*user_roles)
			unrestricted_file.delete()
			restricted_file.delete()
			contact.delete()
			frappe.delete_doc(contact_phone_property_setter.doctype, contact_phone_property_setter.name)

	def test_get_doc_info(self):
		note = frappe.new_doc("Note")
		note.content = "some content"
		note.title = frappe.generate_hash(length=20)
		note.insert()

		note.content = "new content"
		# trigger a version
		note.save(ignore_version=False)

		note.add_comment(text="test")

		note.add_tag("test_tag")
		note.add_tag("more_tag")

		# empty attachment
		save_file("test_file", b"", note.doctype, note.name, decode=True)

		frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"content": "test email",
				"reference_doctype": note.doctype,
				"reference_name": note.name,
			}
		).insert()

		get_docinfo(note)
		docinfo = frappe.response["docinfo"]

		self.assertEqual(len(docinfo.comments), 1)
		self.assertIn("test", docinfo.comments[0].content)

		self.assertGreaterEqual(len(docinfo.versions), 1)

		self.assertEqual(set(docinfo.tags.split(",")), {"more_tag", "test_tag"})

		self.assertEqual(len(docinfo.attachments), 1)
		self.assertIn("test_file", docinfo.attachments[0].file_name)

		self.assertEqual(len(docinfo.communications), 1)
		self.assertIn("email", docinfo.communications[0].content)
		note.delete()


class TestVersionPermlevelFiltering(IntegrationTestCase):
	"""get_versions() must honour permlevels the same way the live document does.

	Set up on Contact via property setters:
	- `phone_nos` is a Table field pushed to permlevel 1, so the whole table is restricted
	  (apply_fieldlevel_read_permissions deletes the attribute outright),
	- `email_ids` stays readable, but `is_primary` inside it is pushed to permlevel 1,
	- Contact's "All" role permission is dropped so access comes only from an explicit
	  role or an explicit DocShare, never ambiently.
	"""

	RESTRICTED_USER = "test@example.com"
	SHARED_USER = "test1@example.com"

	def setUp(self):
		# Contact does not track changes out of the box, and versions are what we filter
		make_property_setter("Contact", None, "track_changes", 1, "Check", for_doctype=True)
		# the whole phone_nos table sits above permlevel 0 ...
		make_property_setter("Contact", "phone_nos", "permlevel", 1, "Int")
		# ... while email_ids stays readable with one restricted field inside it
		make_property_setter("Contact Email", "is_primary", "permlevel", 1, "Int")

		reset("Contact")
		# "All" grants every user read at permlevel 0 on Contact, which would mask what
		# the role and the DocShare are actually contributing
		update("Contact", "All", 0, "read", 0)

		self._set_roles(self.RESTRICTED_USER, ["Sales User"])
		self._set_roles(self.SHARED_USER, [])

	def _set_roles(self, email, roles):
		user = frappe.get_doc("User", email)
		user.remove_roles(*frappe.get_roles(email))
		if roles:
			user.add_roles(*roles)

	def _make_contact(self):
		"""Create a Contact, then edit it so the version records changed/added/row_changed."""
		contact = frappe.new_doc("Contact")
		contact.first_name = f"_Test Version Contact {frappe.generate_hash(length=8)}"
		contact.append("phone_nos", {"phone": "1111111111"})
		contact.append("email_ids", {"email_id": "before@example.com", "is_primary": 0})
		contact.insert()

		contact.designation = "Head of Testing"
		contact.phone_nos[0].phone = "9999999999"
		contact.append("phone_nos", {"phone": "2222222222"})
		contact.email_ids[0].email_id = "after@example.com"
		contact.email_ids[0].is_primary = 1
		contact.append("email_ids", {"email_id": "extra@example.com"})
		contact.save(ignore_version=False)

		return contact

	def _collect(self, versions):
		"""Flatten versions into (tables touched, parent fields changed, table-section payload).

		Only the table sections are serialised: Contact keeps read-only permlevel 0 copies of
		the primary phone and email, so searching the whole payload would flag values that the
		parent doctype publishes by design rather than anything get_versions leaked.
		"""
		tables, changed, blob = set(), set(), ""
		for version in versions:
			data = frappe.parse_json(version.data)
			for key in ("added", "removed", "row_changed"):
				tables.update(log[0] for log in data.get(key) or [])
				blob += frappe.as_json(data.get(key) or [])
			changed.update(log[0] for log in data.get("changed") or [])
		return tables, changed, blob

	def _child_fields(self, versions, table_fieldname):
		"""Every child fieldname reported for one table, across added/removed/row_changed."""
		fields = set()
		for version in versions:
			data = frappe.parse_json(version.data)
			for log in data.get("row_changed") or []:
				if log[0] == table_fieldname:
					fields.update(entry[0] for entry in log[3] or [])
			for key in ("added", "removed"):
				for log in data.get(key) or []:
					if log[0] == table_fieldname:
						fields.update(log[1].keys())
		return fields

	def test_restricted_table_field_excluded_from_versions(self):
		contact = self._make_contact()

		with self.set_user(self.RESTRICTED_USER):
			versions = get_versions(frappe.get_doc("Contact", contact.name))

		self.assertTrue(versions, "expected at least one version to be recorded")
		tables, changed, blob = self._collect(versions)

		self.assertNotIn("phone_nos", tables)
		# no historical value from the restricted table may survive in the table sections
		self.assertNotIn("9999999999", blob)
		self.assertNotIn("2222222222", blob)

		# the fix must be targeted: a table the user *can* read still reports its changes
		self.assertIn("email_ids", tables)
		self.assertIn("designation", changed)

	def test_restricted_child_field_excluded_from_versions(self):
		"""A readable table still hides the child fields sitting above the user's permlevel."""
		contact = self._make_contact()

		with self.set_user(self.RESTRICTED_USER):
			versions = get_versions(frappe.get_doc("Contact", contact.name))

		tables, _, _ = self._collect(versions)
		self.assertIn("email_ids", tables)

		child_fields = self._child_fields(versions, "email_ids")
		self.assertIn("email_id", child_fields)
		self.assertNotIn("is_primary", child_fields)

	def test_permlevel_one_role_sees_restricted_table(self):
		"""Granting the role read at permlevel 1 brings the table back."""
		contact = self._make_contact()
		add("Contact", "Sales User", 1)
		update("Contact", "Sales User", 1, "read", 1)

		with self.set_user(self.RESTRICTED_USER):
			versions = get_versions(frappe.get_doc("Contact", contact.name))

		tables, _, _ = self._collect(versions)
		self.assertIn("phone_nos", tables)
		self.assertIn("email_ids", tables)
		self.assertIn("is_primary", self._child_fields(versions, "email_ids"))

	def test_roleless_user_sees_nothing_without_a_share(self):
		"""Precondition for the share test: no role means no permlevel access at all."""
		contact = self._make_contact()

		with self.set_user(self.SHARED_USER):
			doc = frappe.get_doc("Contact", contact.name)
			self.assertEqual(doc.get_permlevel_access(permission_type="read"), [])
			versions = get_versions(doc)

		tables, changed, _ = self._collect(versions)
		self.assertFalse(tables)
		self.assertFalse(changed)

	def test_shared_document_grants_permlevel_zero_only(self):
		"""A DocShare unlocks permlevel 0, and must not drag permlevel 1 along with it."""
		contact = self._make_contact()
		add_share("Contact", contact.name, self.SHARED_USER, read=1)

		with self.set_user(self.SHARED_USER):
			versions = get_versions(frappe.get_doc("Contact", contact.name))

		tables, changed, blob = self._collect(versions)

		# the share granted permlevel 0 ...
		self.assertIn("designation", changed)
		self.assertIn("email_ids", tables)

		# ... and nothing above it
		self.assertNotIn("phone_nos", tables)
		self.assertNotIn("is_primary", self._child_fields(versions, "email_ids"))
		self.assertNotIn("9999999999", blob)

	def test_administrator_sees_restricted_table_in_versions(self):
		contact = self._make_contact()

		versions = get_versions(frappe.get_doc("Contact", contact.name))

		tables, changed, _ = self._collect(versions)
		self.assertIn("phone_nos", tables)
		self.assertIn("email_ids", tables)
		self.assertIn("designation", changed)
		self.assertIn("is_primary", self._child_fields(versions, "email_ids"))


def get_blog(blog_name):
	frappe.response.docs = []
	getdoc("Test Blog Post", blog_name)
	return frappe.response.docs[0]
