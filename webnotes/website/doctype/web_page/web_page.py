# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import WebsiteGenerator
from webnotes import _
from webnotes.model.controller import DocListController

class DocType(DocListController, WebsiteGenerator):
	def autoname(self):
		from webnotes.webutils import cleanup_page_name
		self.doc.name = cleanup_page_name(self.doc.title)
		
	def validate(self):
		for d in self.doclist.get({"parentfield": "toc"}):
			if d.web_page == self.doc.name:
				webnotes.throw('{web_page} "{name}" {not_in_own} {toc}'.format(
					web_page=_("Web Page"), name=d.web_page,
					not_in_own=_("cannot be in its own"), toc=_(self.meta.get_label("toc"))))

	def on_update(self):
		WebsiteGenerator.on_update(self)
		self.if_home_clear_cache()
		
		# clear all cache if it has toc
		if self.doclist.get({"parentfield": "toc"}):
			from webnotes.webutils import clear_cache
			clear_cache()
			
	def on_trash(self):
		# delete entry from Table of Contents of other pages
		WebsiteGenerator.on_trash(self)
		
		webnotes.conn.sql("""delete from `tabTable of Contents`
			where web_page=%s""", self.doc.name)
		
		# clear all cache if it has toc
		if self.doclist.get({"parentfield": "toc"}):
			from webnotes.webutils import clear_cache
			clear_cache()

	def if_home_clear_cache(self):
		"""if home page, clear cache"""
		if webnotes.conn.get_value("Website Settings", None, "home_page")==self.doc.name:
			if webnotes.conn.exists("Website Sitemap", "index"):
				webnotes.delete_doc("Website Sitemap", "index", ignore_permissions=True)
			WebsiteGenerator.on_update(self, page_name="index")

			from webnotes.sessions import clear_cache
			clear_cache('Guest')
			
			from webnotes.webutils import clear_cache
			clear_cache(self.doc.page_name)
			clear_cache('index')
			
	def get_context(self):
		if self.doc.slideshow:
			from webnotes.website.doctype.website_slideshow.website_slideshow import get_slideshow
			get_slideshow(self)
			
		self.doc.meta_description = self.doc.description
		
		self.doc.breadcrumbs = self.get_breadcrumbs()
		self.doc.toc_list = self.get_toc_list()
		
		# parent, child, next sibling links
		self.doc.links = self.get_navigation_links()
		
		if self.doc.enable_comments:
			self.doc.comment_list = webnotes.conn.sql("""select 
				comment, comment_by_fullname, creation
				from `tabComment` where comment_doctype="Web Page"
				and comment_docname=%s order by creation""", self.doc.name, as_dict=1) or []
			
	def get_breadcrumbs(self):
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
			
		add_parent_of(self.doc.name)
		
		return breadcrumbs
		
	def get_toc_list(self):
		toc_list = self.doclist.get({"parentfield": "toc"})
		if not toc_list: return []

		out = webnotes.conn.sql("""select name, page_name, title
			from `tabWeb Page` where name in (%s)""" % \
			(", ".join(["%s"]*len(toc_list))),
			tuple([d.web_page for d in toc_list]),
			as_dict=True)
		
		toc_idx = dict(((toc.web_page, toc.idx) for toc in toc_list))
		return sorted(out, key=lambda x: toc_idx.get(x.name))
		
	def get_navigation_links(self):
		links = {}
		
		if self.doc.toc_list:
			links["child"] = self.doc.toc_list[0]
		
		if self.doc.breadcrumbs:
			if self.doc.breadcrumbs[-1]:
				links["parent"] = self.doc.breadcrumbs[-1]
			
			def set_next(current, parent, breadcrumbs):
				web_page = webnotes.get_obj("Web Page", parent)
				toc_list = web_page.get_toc_list()
				for i, toc in enumerate(toc_list):
					if toc.name == current and ((i+1)<len(toc_list)):
						links["next"] = toc_list[i+1]
						break
						
				if not links.get("next") and breadcrumbs:
					set_next(parent, breadcrumbs[-1].name, breadcrumbs[:-1])
				
			set_next(self.doc.name, self.doc.breadcrumbs[-1].name, self.doc.breadcrumbs[:-1])

		return links
			
				
			
			
