# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt

import frappe
import unittest

class TestFeedback(unittest.TestCase):
	def test_feedback_creation_updation(self):
		from frappe.website.doctype.blog_post.test_blog_post import make_test_blog
		test_blog = make_test_blog()

		frappe.db.sql("delete from `tabFeedback` where reference_doctype = 'Blog Post'")

		from frappe.templates.includes.feedback.feedback import add_feedback, update_feedback
		feedback = add_feedback('Blog Post', test_blog.name, 5, 'New feedback','test@test.com')

		self.assertEqual(feedback.feedback, 'New feedback')
		self.assertEqual(feedback.rating, 5)

		updated_feedback = update_feedback('Blog Post', test_blog.name, 6, 'Updated feedback', 'test@test.com')

		self.assertEqual(updated_feedback.feedback, 'Updated feedback')
		self.assertEqual(updated_feedback.rating, 6)

		frappe.db.sql("delete from `tabFeedback` where reference_doctype = 'Blog Post'")

		test_blog.delete()