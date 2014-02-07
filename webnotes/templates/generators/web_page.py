# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.website.doctype.website_slideshow.website_slideshow import get_slideshow

doctype = "Web Page"
condition_field = "published"

def get_context(context):
	web_page = context.bean
	
	if web_page.doc.slideshow:
		web_page.doc.fields.update(get_slideshow(web_page))
		
	web_page.doc.meta_description = web_page.doc.description
	
	# web_page.doc.breadcrumbs = get_breadcrumbs(web_page)
	web_page.doc.toc_list = get_toc_list(web_page)
	
	# parent, child, next sibling links
	web_page.doc.links = get_navigation_links(web_page)
	
	if web_page.doc.enable_comments:
		web_page.doc.comment_list = webnotes.conn.sql("""select 
			comment, comment_by_fullname, creation
			from `tabComment` where comment_doctype="Web Page"
			and comment_docname=%s order by creation""", web_page.doc.name, as_dict=1) or []
			
	web_page.doc.fields.update({
		"style": web_page.doc.css or "",
		"script": web_page.doc.javascript or ""
	})
	
	web_page.doc.fields.update(context)
	
	return web_page.doc.fields
			
def get_breadcrumbs(web_page):
	breadcrumbs = []
	
	def add_parent_of(web_page):
		parent = webnotes.conn.sql("""select name, page_name, title from `tabWeb Page`
			where exists (select parent from `tabTable of Contents`
				where `tabTable of Contents`.parent=`tabWeb Page`.name
					and web_page=%s)""", web_page, as_dict=True)
		if parent and parent[0]:
			parent = parent[0]
			add_parent_of(parent.name)
			breadcrumbs.append(parent)
		
	add_parent_of(web_page.doc.name)
	
	return breadcrumbs
	
def get_toc_list(web_page):
	toc_list = web_page.doclist.get({"parentfield": "toc"})
	if not toc_list: return []

	out = webnotes.conn.sql("""select name, page_name, title
		from `tabWeb Page` where name in (%s)""" % \
		(", ".join(["%s"]*len(toc_list))),
		tuple([d.web_page for d in toc_list]),
		as_dict=True)
	
	toc_idx = dict(((toc.web_page, toc.idx) for toc in toc_list))
	return sorted(out, key=lambda x: toc_idx.get(x.name))
	
def get_navigation_links(web_page):
	links = {}
	
	if web_page.doc.toc_list:
		links["child"] = web_page.doc.toc_list[0]
	
	if web_page.doc.breadcrumbs:
		if web_page.doc.breadcrumbs[-1]:
			links["parent"] = web_page.doc.breadcrumbs[-1]
		
		def set_next(current, parent, breadcrumbs):
			web_page = webnotes.get_obj("Web Page", parent)
			toc_list = web_page.get_toc_list()
			for i, toc in enumerate(toc_list):
				if toc.name == current and ((i+1)<len(toc_list)):
					links["next"] = toc_list[i+1]
					break
					
			if not links.get("next") and breadcrumbs:
				set_next(parent, breadcrumbs[-1].name, breadcrumbs[:-1])
			
		set_next(web_page.doc.name, web_page.doc.breadcrumbs[-1].name, web_page.doc.breadcrumbs[:-1])

	return links