# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.templates.includes.comments.comments import add_comment
from frappe.tests import IntegrationTestCase
from frappe.tests.test_model_utils import set_user
from frappe.website.doctype.blog_post.test_blog_post import make_test_blog


class TestComment(IntegrationTestCase):
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
		test_blog = make_test_blog()

		frappe.db.delete("Comment", {"reference_doctype": "Blog Post"})
		add_comment_args = {
			"comment": "Good comment with 10 chars",
			"comment_email": "test@test.com",
			"comment_by": "Good Tester",
			"reference_doctype": test_blog.doctype,
			"reference_name": test_blog.name,
			"route": test_blog.route,
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

		frappe.db.delete("Comment", {"reference_doctype": "Blog Post"})

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
		frappe.db.delete("Comment", {"reference_doctype": "Blog Post"})

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

	@IntegrationTestCase.change_settings("Blog Settings", {"allow_guest_to_comment": 0})
	def test_guest_cannot_comment(self):
		test_blog = make_test_blog()
		with set_user("Guest"):
			self.assertEqual(
				add_comment(
					comment="Good comment with 10 chars",
					comment_email="mail@example.org",
					comment_by="Good Tester",
					reference_doctype="Blog Post",
					reference_name=test_blog.name,
					route=test_blog.route,
				),
				None,
			)

	def test_user_not_logged_in(self):
		some_system_user = frappe.db.get_value("User", {"name": ("not in", frappe.STANDARD_USERS)})

		test_blog = make_test_blog()
		with set_user("Guest"):
			self.assertRaises(
				frappe.ValidationError,
				add_comment,
				comment="Good comment with 10 chars",
				comment_email=some_system_user,
				comment_by="Good Tester",
				reference_doctype="Blog Post",
				reference_name=test_blog.name,
				route=test_blog.route,
			)
