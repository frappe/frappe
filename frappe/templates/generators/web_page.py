# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow

doctype = "Web Page"
condition_field = "published"

def get_context(context):
	web_page = context.bean
	
	if web_page.doc.slideshow:
		web_page.doc.fields.update(get_slideshow(web_page))
		
	web_page.doc.meta_description = web_page.doc.description
	
	if web_page.doc.enable_comments:
		web_page.doc.comment_list = frappe.db.sql("""select 
			comment, comment_by_fullname, creation
			from `tabComment` where comment_doctype="Web Page"
			and comment_docname=%s order by creation""", web_page.doc.name, as_dict=1) or []
			
	web_page.doc.fields.update({
		"style": web_page.doc.css or "",
		"script": web_page.doc.javascript or ""
	})
	
	web_page.doc.fields.update(context)
	
	return web_page.doc.fields
