# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

page_title = "Blog"
def get_context(context):
	context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict())
	context.children = get_children()

def get_children():
	return frappe.db.sql("""select concat("blog/", page_name) as name,
		title from `tabBlog Category`
		where ifnull(published, 0) = 1 order by title asc""", as_dict=1)
