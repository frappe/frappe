# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os, time
from frappe.website.website_generator import WebsiteGenerator
from frappe import _
from frappe.utils import cint
from markdown2 import markdown

class DocType(WebsiteGenerator):		
	def validate(self):
		for d in self.doclist.get({"parentfield": "toc"}):
			if d.web_page == self.doc.name:
				frappe.throw('{web_page} "{name}" {not_in_own} {toc}'.format(
					web_page=_("Web Page"), name=d.web_page,
					not_in_own=_("cannot be in its own"), toc=_(self.meta.get_label("toc"))))

	def on_update(self):
		WebsiteGenerator.on_update(self)
		
		# clear all cache if it has toc
		if self.doclist.get({"parentfield": "toc"}):
			from frappe.website.render import clear_cache
			clear_cache()
						
	def on_trash(self):
		# delete entry from Table of Contents of other pages
		WebsiteGenerator.on_trash(self)
		
		frappe.conn.sql("""delete from `tabTable of Contents`
			where web_page=%s""", self.doc.name)
		
		# clear all cache if it has toc
		if self.doclist.get({"parentfield": "toc"}):
			from frappe.website.render import clear_cache
			clear_cache()

def sync_statics():
	while True:
		_sync_statics()
		frappe.conn.commit()
		time.sleep(2)

def _sync_statics():
	synced = []
	to_insert = []
	
	def sync_file(fname, fpath, statics_path, priority=0):
		url = os.path.relpath(fpath, statics_path).rsplit(".", 1)[0]
		if fname.rsplit(".", 1)[0]=="index" and os.path.dirname(fpath) != statics_path:
			url = os.path.dirname(url)
				
		parent_website_route = os.path.dirname(url)
		page_name = os.path.basename(url)
				
		try:
			sitemap = frappe.bean("Website Route", url)
		
		except frappe.DoesNotExistError:
			title, content = get_static_content(fpath)
			if not title:
				title = page_name.replace("-", " ").replace("_", " ").title()
			to_insert.append([frappe.bean({
				"doctype":"Web Page",
				"idx": priority,
				"title": title,
				"page_name": page_name,
				"main_section": content,
				"published": 1,
				"parent_website_route": parent_website_route
			}), os.path.getmtime(fpath)])
			
		else:
			if str(os.path.getmtime(fpath))!=sitemap.doc.static_file_timestamp \
				or cint(sitemap.doc.idx) != cint(priority):

				page = frappe.bean("Web Page", sitemap.doc.docname)
				title, content = get_static_content(fpath)
				page.doc.main_section = content
				page.doc.idx = priority
				if not title:
					title = page_name.replace("-", " ").replace("_", " ").title()
				page.doc.title = title
				page.save()

				sitemap = frappe.bean("Website Route", url)
				sitemap.doc.static_file_timestamp = os.path.getmtime(fpath)
				sitemap.save()
			
			synced.append(url)
	
	for app in frappe.get_installed_apps():
		statics_path = frappe.get_app_path(app, "templates", "statics")

		if os.path.exists(frappe.get_app_path(app, "templates", "statics")):
			for basepath, folders, files in os.walk(statics_path):
				# index file first!
				index = []
				has_index = False
				if "index.txt" in files:
					with open(os.path.join(basepath, "index.txt"), "r") as indexfile:
						index = indexfile.read().splitlines()
								
				if basepath!=statics_path:
					for fname in files:
						page_name = fname.rsplit(".", 1)[0]					
						if page_name=="index" and fname!="index.txt":
							sync_file(fname, os.path.join(basepath, fname), statics_path)
							has_index = True
							break
				
					if not has_index:
						continue
				
				# other files
				for fname in files:
					page_name = fname.rsplit(".", 1)[0]
					if not (page_name=="index" and basepath!=statics_path):
						sync_file(fname, os.path.join(basepath, fname), statics_path, 
							index.index(page_name) if page_name in index else 0)
					
	# delete not synced
	if synced:
		frappe.delete_doc("Web Page", frappe.conn.sql_list("""select docname from `tabWebsite Route`
			where ifnull(static_file_timestamp,'')!='' and name not in ({}) 
				order by (rgt-lft) asc""".format(', '.join(["%s"]*len(synced))), tuple(synced)))
	else:
		frappe.delete_doc("Web Page", frappe.conn.sql_list("""select docname from `tabWebsite Route`
			where ifnull(static_file_timestamp,'')!='' order by (rgt-lft) asc"""))
		

	# insert
	for page, mtime in to_insert:
		page.insert()

		# update timestamp
		sitemap = frappe.bean("Website Route", {"ref_doctype": "Web Page", 
			"docname": page.doc.name})
		sitemap.doc.static_file_timestamp = mtime
		sitemap.save()
		

def get_static_content(fpath):
	with open(fpath, "r") as contentfile:
		title = None
		content = unicode(contentfile.read(), 'utf-8')

		if fpath.endswith(".md"):
			if content:
				lines = content.splitlines()
				first_line = lines[0].strip()

				if first_line.startswith("# "):
					title = first_line[2:]
					content = "\n".join(lines[1:])

				content = markdown(content)
			
		content = unicode(content.encode("utf-8"), 'utf-8')
			
		return title, content
	
				
