# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

test_dependencies = ["Blog Post"]


class TestWebsiteRouteMeta(FrappeTestCase):
	def test_meta_tag_generation(self):
		blogs = frappe.get_all(
			"Blog Post", fields=["name", "route"], filters={"published": 1, "route": ("!=", "")}, limit=1
		)

		blog = blogs[0]

		# create meta tags for this route
		doc = frappe.new_doc("Website Route Meta")
		doc.append("meta_tags", {"key": "type", "value": "blog_post"})
		doc.append("meta_tags", {"key": "og:title", "value": "My Blog"})
		doc.name = blog.route
		doc.insert()

		# set request on this route
		set_request(path=blog.route)
		response = get_response()

		self.assertTrue(response.status_code, 200)

		html = response.get_data().decode()

		self.assertTrue("""<meta name="type" content="blog_post">""" in html)
		self.assertTrue("""<meta property="og:title" content="My Blog">""" in html)

	def tearDown(self):
		frappe.db.rollback()
