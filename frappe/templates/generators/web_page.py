# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow

doctype = "Web Page"
condition_field = "published"

def get_context(context):
	web_page = frappe._dict(context.doc.as_dict())

	if web_page.slideshow:
		web_page.update(get_slideshow(web_page))

	web_page.meta_description = web_page.description

	if web_page.enable_comments:
		web_page.comment_list = frappe.db.sql("""select
			comment, comment_by_fullname, creation
			from `tabComment` where comment_doctype="Web Page"
			and comment_docname=%s order by creation""", web_page.name, as_dict=1) or []

	web_page.update({
		"style": web_page.css or "",
		"script": web_page.javascript or ""
	})
	web_page.update(context)

	if not web_page.header:
		web_page.header = web_page.title

	return web_page
