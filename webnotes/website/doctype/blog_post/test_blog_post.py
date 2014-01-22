# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""Use blog post test to test permission restriction logic"""

test_records = [
	[{
		"doctype": "Blog Post",
		"title":"_Test Blog Post",
		"blog_category": "_Test Blog Category",
		"blogger": "_Test Blogger",
		"blog_intro": "Test Blog Intro",
		"content": "Test Blog Content"
	}],
	[{
		"doctype": "Blog Post",
		"title":"_Test Blog Post 1",
		"blog_category": "_Test Blog Category 1",
		"blogger": "_Test Blogger",
		"blog_intro": "Test Blog Intro",
		"content": "Test Blog Content"
	}]
	
]

import webnotes
import webnotes.defaults
import unittest
from webnotes.core.page.user_properties.user_properties import add, remove, get_properties, clear_restrictions


test_dependencies = ["Profile"]
class TestBlogPost(unittest.TestCase):
	def setUp(self):
		webnotes.conn.sql("""update tabDocPerm set `restricted`=0 where parent='Blog Post' 
			and ifnull(permlevel,0)=0""")
		webnotes.conn.sql("""update `tabBlog Post` set owner='test2@example.com'
			where name='_test-blog-post'""")

		webnotes.clear_cache(doctype="Blog Post")
		
		profile = webnotes.bean("Profile", "test1@example.com")
		profile.get_controller().add_roles("Website Manager")
		
		profile = webnotes.bean("Profile", "test2@example.com")
		profile.get_controller().add_roles("Blogger")
		
		webnotes.set_user("test1@example.com")
		
	def tearDown(self):
		webnotes.set_user("Administrator")
		clear_restrictions("Blog Category")
		clear_restrictions("Blog Post")
		
	def test_basic_permission(self):
		post = webnotes.bean("Blog Post", "_test-blog-post")
		self.assertTrue(post.has_read_perm())
		
	def test_restriction_in_bean(self):
		webnotes.defaults.add_default("Blog Category", "_Test Blog Category 1", "test1@example.com", 
			"Restriction")
				
		post = webnotes.bean("Blog Post", "_test-blog-post")
		self.assertFalse(post.has_read_perm())

		post1 = webnotes.bean("Blog Post", "_test-blog-post-1")
		self.assertTrue(post1.has_read_perm())
		
	def test_restriction_in_report(self):
		webnotes.defaults.add_default("Blog Category", "_Test Blog Category 1", "test1@example.com", 
			"Restriction")
		webnotes.local.reportview_doctypes = {}
		
		names = [d.name for d in webnotes.get_list("Blog Post", fields=["name", "blog_category"])]

		self.assertTrue("_test-blog-post-1" in names)
		self.assertFalse("_test-blog-post" in names)
		
	def test_default_values(self):
		webnotes.defaults.add_default("Blog Category", "_Test Blog Category 1", "test1@example.com", 
			"Restriction")
			
		doc = webnotes.new_doc("Blog Post")
		self.assertEquals(doc.get("blog_category"), "_Test Blog Category 1")
	
	def add_restricted_on_blogger(self):
		webnotes.conn.sql("""update tabDocPerm set `restricted`=1 where parent='Blog Post' and role='Blogger' 
			and ifnull(permlevel,0)=0""")
		webnotes.clear_cache(doctype="Blog Post")
	
	def test_owner_match_bean(self):
		self.add_restricted_on_blogger()

		webnotes.set_user("test2@example.com")

		post = webnotes.bean("Blog Post", "_test-blog-post")
		self.assertTrue(post.has_read_perm())

		post1 = webnotes.bean("Blog Post", "_test-blog-post-1")
		self.assertFalse(post1.has_read_perm())
		
	def test_owner_match_report(self):
		webnotes.conn.sql("""update tabDocPerm set `restricted`=1 where parent='Blog Post' 
			and ifnull(permlevel,0)=0""")
		webnotes.clear_cache(doctype="Blog Post")

		webnotes.set_user("test2@example.com")

		names = [d.name for d in webnotes.get_list("Blog Post", fields=["name", "owner"])]
		self.assertTrue("_test-blog-post" in names)
		self.assertFalse("_test-blog-post-1" in names)
	
	def add_restriction_to_user2(self):
		webnotes.set_user("test1@example.com")
		add("test2@example.com", "Blog Post", "_test-blog-post")
	
	def test_add_restriction(self):
		# restrictor can add restriction
		self.add_restriction_to_user2()
		
	def test_not_allowed_to_restrict(self):
		webnotes.set_user("test2@example.com")
		
		# this user can't add restriction
		self.assertRaises(webnotes.PermissionError, add, 
			"test2@example.com", "Blog Post", "_test-blog-post")

	def test_not_allowed_to_restrict(self):
		self.add_restriction_to_user2()

		webnotes.set_user("test2@example.com")

		# user can only access restricted blog post
		bean = webnotes.bean("Blog Post", "_test-blog-post")
		self.assertTrue(bean.has_read_perm())

		# and not this one
		bean = webnotes.bean("Blog Post", "_test-blog-post-1")
		self.assertFalse(bean.has_read_perm())
	
	def test_not_allowed_to_remove_self(self):
		self.add_restriction_to_user2()
		defname = get_properties("test2@example.com", "Blog Post", "_test-blog-post")[0].name

		webnotes.set_user("test2@example.com")

		# user cannot remove their own restriction
		self.assertRaises(webnotes.PermissionError, remove, 
			"test2@example.com", defname, "Blog Post", "_test-blog-post")
				
	def test_allow_in_restriction(self):
		self.add_restricted_on_blogger()

		webnotes.set_user("test2@example.com")
		bean = webnotes.bean("Blog Post", "_test-blog-post-1")
		self.assertFalse(bean.has_read_perm())

		webnotes.set_user("test1@example.com")
		add("test2@example.com", "Blog Post", "_test-blog-post-1")

		webnotes.set_user("test2@example.com")
		bean = webnotes.bean("Blog Post", "_test-blog-post-1")

		self.assertTrue(bean.has_read_perm())
