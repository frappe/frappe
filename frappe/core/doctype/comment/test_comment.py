# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import json
import unittest

import frappe
<<<<<<< HEAD
=======
from frappe.templates.includes.comments.comments import add_comment
from frappe.tests.test_model_utils import set_user
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.website.doctype.blog_post.test_blog_post import make_test_blog
>>>>>>> e5b1b8d681 (fix: improved validation in `add_comment` (#20520))


class TestComment(unittest.TestCase):
	def test_comment_creation(self):
		test_doc = frappe.get_doc(dict(doctype="ToDo", description="test"))
		test_doc.insert()
		comment = test_doc.add_comment("Comment", "test comment")

		test_doc.reload()

		# check if updated in _comments cache
		comments = json.loads(test_doc.get("_comments"))
		self.assertEqual(comments[0].get("name"), comment.name)
		self.assertEqual(comments[0].get("comment"), comment.content)

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

		frappe.db.sql("delete from `tabComment` where reference_doctype = 'Blog Post'")

<<<<<<< HEAD
		from frappe.templates.includes.comments.comments import add_comment

		add_comment(
			"Good comment with 10 chars",
			"test@test.com",
			"Good Tester",
			"Blog Post",
			test_blog.name,
			test_blog.route,
		)
=======
		frappe.form_dict.comment = "Good comment with 10 chars"
		frappe.form_dict.comment_email = "test@test.com"
		frappe.form_dict.comment_by = "Good Tester"
		frappe.form_dict.reference_doctype = "Blog Post"
		frappe.form_dict.reference_name = test_blog.name
		frappe.form_dict.route = test_blog.route
		frappe.local.request_ip = "127.0.0.1"

		add_comment()
>>>>>>> e5b1b8d681 (fix: improved validation in `add_comment` (#20520))

		self.assertEqual(
			frappe.get_all(
				"Comment",
				fields=["*"],
				filters=dict(reference_doctype=test_blog.doctype, reference_name=test_blog.name),
			)[0].published,
			1,
		)

		frappe.db.sql("delete from `tabComment` where reference_doctype = 'Blog Post'")

		add_comment(
			"pleez vizits my site http://mysite.com",
			"test@test.com",
			"bad commentor",
			"Blog Post",
			test_blog.name,
			test_blog.route,
		)

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

		test_blog.delete()

	@change_settings("Blog Settings", {"allow_guest_to_comment": 0})
	def test_guest_cannot_comment(self):
		test_blog = make_test_blog()
		with set_user("Guest"):
			frappe.form_dict.comment = "Good comment with 10 chars"
			frappe.form_dict.comment_email = "mail@example.org"
			frappe.form_dict.comment_by = "Good Tester"
			frappe.form_dict.reference_doctype = "Blog Post"
			frappe.form_dict.reference_name = test_blog.name
			frappe.form_dict.route = test_blog.route
			frappe.local.request_ip = "127.0.0.1"

			self.assertEqual(add_comment(), None)

	def test_user_not_logged_in(self):
		some_system_user = frappe.db.get_value("User", {})

		test_blog = make_test_blog()
		with set_user("Guest"):
			frappe.form_dict.comment = "Good comment with 10 chars"
			frappe.form_dict.comment_email = some_system_user
			frappe.form_dict.comment_by = "Good Tester"
			frappe.form_dict.reference_doctype = "Blog Post"
			frappe.form_dict.reference_name = test_blog.name
			frappe.form_dict.route = test_blog.route
			frappe.local.request_ip = "127.0.0.1"

			self.assertRaises(frappe.ValidationError, add_comment)
