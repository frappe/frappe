# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def on_update(self):
		"if profile is set, then update all older blogs"
		
		from frappe.website.doctype.blog_post.blog_post import clear_blog_cache
		clear_blog_cache()
		
		if self.doc.profile:
			for blog in frappe.conn.sql_list("""select name from `tabBlog Post` where owner=%s 
				and ifnull(blogger,'')=''""", self.doc.profile):
				b = frappe.bean("Blog Post", blog)
				b.doc.blogger = self.doc.name
				b.save()