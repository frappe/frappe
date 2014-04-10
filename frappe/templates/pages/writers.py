# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def get_context(context):
	bloggers = frappe.db.sql("""select * from `tabBlogger` 
	 	where ifnull(posts,0) > 0 and ifnull(disabled,0)=0 
		order by posts desc""", as_dict=1)
		
	writers_context = {
		"bloggers": bloggers,
		"texts": {
			"all_posts_by": "All posts by"
		},
		"categories": frappe.db.sql_list("select name from `tabBlog Category` order by name")
	}
	
	writers_context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict())
	
	return writers_context
