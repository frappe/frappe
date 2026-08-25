# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.core.doctype.comment.comment import get_document_comments, get_permission_query_conditions
from frappe.desk.form.activity import get_activity_timeline
from frappe.desk.form.load import add_comments, get_comments
from frappe.permissions import add_permission, reset_perms
from frappe.templates.includes.comments.comments import add_comment
from frappe.tests import IntegrationTestCase
from frappe.tests.test_helpers import setup_for_tests
from frappe.tests.test_model_utils import set_user

EXTRA_TEST_RECORD_DEPENDENCIES = ["Web Page"]


class TestComment(IntegrationTestCase):
	def setUp(self):
		setup_for_tests()

	def test_comment_creation(self):
		test_doc = frappe.get_doc(doctype="ToDo", description="test")
		test_doc.insert()
		comment = test_doc.add_comment("Comment", "test comment")

		test_doc.reload()

		# check if updated in _comments cache
		comments = json.loads(test_doc.get("_comments"))
		self.assertEqual(comments[0].get("name"), comment.name)
		self.assertEqual(comments[0].get("comment"), comment.content)

		# Check comment count
		counts = frappe.get_all("ToDo", {"name": test_doc.name}, ["*"], with_comment_count=True)
		self.assertEqual(counts[0]._comment_count, 1)

		comment = test_doc.add_comment("Comment", "test comment")

		counts = frappe.get_all("ToDo", {"name": test_doc.name}, ["*"], with_comment_count=True)
		self.assertEqual(counts[0]._comment_count, 2)

		# check document creation
		comment_1 = frappe.get_all(
			"Comment",
			fields=["*"],
			filters=dict(reference_doctype=test_doc.doctype, reference_name=test_doc.name),
		)[0]

		self.assertEqual(comment_1.content, "test comment")

	# test via blog
	def test_public_comment(self):
		test_blog = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")

		frappe.db.delete("Comment", {"reference_doctype": "Test Blog Post"})
		add_comment_args = {
			"comment": "Good comment with 10 chars",
			"comment_email": "test@test.com",
			"comment_by": "Good Tester",
			"reference_doctype": test_blog.doctype,
			"reference_name": test_blog.name,
			"route": f"blog/{test_blog.doctype}/{test_blog.name}",
		}
		add_comment(**add_comment_args)

		self.assertEqual(
			frappe.get_all(
				"Comment",
				fields=["*"],
				filters=dict(reference_doctype=test_blog.doctype, reference_name=test_blog.name),
			)[0].published,
			1,
		)

		frappe.db.delete("Comment", {"reference_doctype": "Test Blog Post"})

		add_comment_args.update(comment="pleez vizits my site http://mysite.com", comment_by="bad commentor")
		add_comment(**add_comment_args)

		self.assertEqual(
			len(
				frappe.get_all(
					"Comment",
					fields=["*"],
					filters=dict(reference_doctype=test_blog.doctype, reference_name=test_blog.name),
				)
			),
			0,
		)

		# test for filtering html and css injection elements
		frappe.db.delete("Comment", {"reference_doctype": "Test Blog Post"})

		add_comment_args.update(comment="<script>alert(1)</script>Comment", comment_by="hacker")
		add_comment(**add_comment_args)
		self.assertEqual(
			frappe.get_all(
				"Comment",
				fields=["content"],
				filters=dict(reference_doctype=test_blog.doctype, reference_name=test_blog.name),
			)[0]["content"],
			"Comment",
		)

		test_blog.delete()

	def test_guest_sees_published_website_comments(self):
		"""Website comment visibility is the `published` flag, not desk read on the page."""
		from frappe.website.utils import get_comment_list

		web_page = frappe.get_doc("Web Page", "test-web-page-1")
		comment = frappe.get_doc(
			doctype="Comment",
			comment_type="Comment",
			content="public comment",
			comment_email="test@test.com",
			comment_by="Good Tester",
			published=1,
			reference_doctype="Web Page",
			reference_name=web_page.name,
		).insert(ignore_permissions=True)

		with set_user("Guest"):
			visible = [c["name"] for c in get_comment_list("Web Page", web_page.name)]

		self.assertIn(comment.name, visible)

	def test_user_not_logged_in(self):
		some_system_user = frappe.db.get_value("User", {"name": ("not in", frappe.STANDARD_USERS)})

		test_blog = frappe.get_doc("Web Page", "test-web-page-1")
		with set_user("Guest"):
			self.assertRaises(
				frappe.AuthenticationError,
				add_comment,
				comment="Good comment with 10 chars",
				comment_email=some_system_user,
				comment_by="Good Tester",
				reference_doctype="Web Page",
				reference_name=test_blog.name,
				route=test_blog.route,
			)


class TestCommentPermissions(IntegrationTestCase):
	"""Read on the Comment doctype must not be read on every comment in the site."""

	def setUp(self):
		self.todo = frappe.get_doc(doctype="ToDo", description="comment permission test").insert()
		self.comment = self.todo.add_comment("Comment", "internal discussion").name

		self.user = "comment-perm@example.com"
		if not frappe.db.exists("User", self.user):
			frappe.get_doc(
				doctype="User",
				email=self.user,
				first_name="Comment Perm",
				send_welcome_email=0,
				roles=[{"role": "Blogger"}],
			).insert(ignore_permissions=True)

		# a role read on Comment is needed to get past the doctype gate
		add_permission("Comment", "Blogger", 0)
		frappe.clear_cache(doctype="Comment")

	def tearDown(self):
		reset_perms("Comment")
		frappe.clear_cache(doctype="Comment")

	def visible_comments(self):
		"""Assertions stay outside `set_user`: one failing inside leaks the user into the next setUp."""
		with set_user(self.user):
			return frappe.get_list(
				"Comment",
				filters={
					"reference_doctype": "ToDo",
					"reference_name": self.todo.name,
					"comment_type": "Comment",
				},
				pluck="name",
			)

	def can_read_comment(self):
		with set_user(self.user):
			return frappe.has_permission("Comment", "read", doc=self.comment)

	def test_comments_on_an_unreadable_doctype_are_dropped_from_lists(self):
		on_a_role = frappe.get_doc(
			doctype="Comment",
			comment_type="Comment",
			content="on a role",
			reference_doctype="Role",
			reference_name="Blogger",
		).insert(ignore_permissions=True)

		with set_user(self.user):
			visible = frappe.get_list("Comment", filters={"name": on_a_role.name}, pluck="name")

		self.assertEqual(visible, [])

	def test_comments_on_a_readable_doctype_stay_in_lists(self):
		frappe.share.add("ToDo", self.todo.name, self.user, read=1)
		self.assertEqual(self.visible_comments(), [self.comment])

	def test_direct_read_follows_the_document(self):
		self.assertFalse(self.can_read_comment())

		frappe.share.add("ToDo", self.todo.name, self.user, read=1)
		self.assertTrue(self.can_read_comment())

	def test_query_conditions_drop_doctypes_the_user_cannot_read(self):
		with set_user(self.user):
			conditions = get_permission_query_conditions()

		self.assertIn("'ToDo'", conditions)
		self.assertNotIn("'Role'", conditions)

	def test_administrator_is_not_filtered(self):
		self.assertEqual(get_permission_query_conditions("Administrator"), "")

	def test_a_cycle_of_comments_does_not_recurse(self):
		"""Two comments referencing each other must not blow the stack on a permission check."""
		a = frappe.get_doc(doctype="Comment", comment_type="Comment", content="a").insert(
			ignore_permissions=True
		)
		b = frappe.get_doc(
			doctype="Comment",
			comment_type="Comment",
			content="b",
			reference_doctype="Comment",
			reference_name=a.name,
		).insert(ignore_permissions=True)
		a.reference_doctype = "Comment"
		a.reference_name = b.name
		a.save(ignore_permissions=True)

		with set_user(self.user):
			readable = frappe.has_permission("Comment", "read", doc=a.name)

		self.assertTrue(readable)

	def test_a_comment_on_nothing_stays_visible(self):
		orphan = frappe.get_doc(doctype="Comment", comment_type="Comment", content="no reference").insert(
			ignore_permissions=True
		)
		with set_user(self.user):
			visible = frappe.get_list("Comment", filters={"name": orphan.name}, pluck="name")

		self.assertEqual(visible, [orphan.name])


def hide_the_discussion(doc, ptype=None, user=None, debug=False):
	"""Test hook: a ToDo's discussion is agent-internal; its activity log is not."""
	return not (doc.reference_doctype == "ToDo" and doc.comment_type == "Comment")


HIDE = {"has_permission": {"Comment": ["frappe.core.doctype.comment.test_comment.hide_the_discussion"]}}


class TestCommentReadersHonourHooks(IntegrationTestCase):
	"""The readers that fetch with permissions ignored must still run the Comment hooks."""

	def setUp(self):
		self.todo = frappe.get_doc(doctype="ToDo", description="hook test").insert()
		self.comment = self.todo.add_comment("Comment", "internal discussion").name
		self.info = self.todo.add_comment("Info", "info log").name

	def docinfo(self):
		out = frappe._dict()
		add_comments(self.todo, out)
		return [c.name for c in out.comments], [c.name for c in out.info_logs]

	def timeline_types(self):
		timeline = get_activity_timeline("ToDo", self.todo.name)
		return {a["type"] for a in timeline["activities"]}

	def test_everything_is_returned_without_a_hook(self):
		self.assertEqual(self.docinfo(), ([self.comment], [self.info]))
		self.assertIn("comment", self.timeline_types())
		self.assertEqual(len(get_comments("ToDo", self.todo.name)), 1)

	def test_hook_reaches_docinfo(self):
		with self.patch_hooks(HIDE):
			comments, info_logs = self.docinfo()

		self.assertEqual(comments, [])
		self.assertEqual(info_logs, [self.info])

	def test_hook_reaches_the_activity_timeline(self):
		with self.patch_hooks(HIDE):
			types = self.timeline_types()

		self.assertNotIn("comment", types)
		self.assertIn("log", types)

	def test_hook_reaches_get_comments(self):
		with self.patch_hooks(HIDE):
			self.assertEqual(get_comments("ToDo", self.todo.name), [])
			self.assertEqual(len(get_comments("ToDo", self.todo.name, "Info")), 1)

	def test_hook_reaches_a_read_composed_for_another_user(self):
		with self.patch_hooks(HIDE):
			permitted = get_document_comments("ToDo", self.todo.name, fields=["name"], user="Administrator")

		self.assertEqual([c.name for c in permitted], [self.info])
