# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes, os
from webnotes.webutils import WebsiteGenerator
from webnotes import _
from webnotes.utils import cint
from markdown2 import markdown

class DocType(WebsiteGenerator):		
	def validate(self):
		for d in self.doclist.get({"parentfield": "toc"}):
			if d.web_page == self.doc.name:
				webnotes.throw('{web_page} "{name}" {not_in_own} {toc}'.format(
					web_page=_("Web Page"), name=d.web_page,
					not_in_own=_("cannot be in its own"), toc=_(self.meta.get_label("toc"))))

	def on_update(self):
		WebsiteGenerator.on_update(self)
		
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
			
def sync_statics():
	synced = []
	to_insert = []
	
	def sync_file(fname, fpath, statics_path, priority=0):
		url = os.path.relpath(fpath, statics_path).rsplit(".", 1)[0]
		if fname.rsplit(".", 1)[0]=="index":
			url = os.path.dirname(url)
				
		parent_website_sitemap = os.path.dirname(url)
		page_name = os.path.basename(url)
				
		try:
			sitemap = webnotes.bean("Website Sitemap", url)

			if str(os.path.getmtime(fpath))!=sitemap.doc.static_file_timestamp \
				or cint(sitemap.doc.idx) != cint(priority):
				page = webnotes.bean("Web Page", sitemap.doc.docname)
				title, content = get_static_content(fpath)
				page.doc.main_section = content
				if title:
					page.doc.title = title
				page.save()

				sitemap = webnotes.bean("Website Sitemap", url)
				sitemap.doc.static_file_timestamp = os.path.getmtime(fpath)
				sitemap.doc.idx = priority
				sitemap.save()
			
			synced.append(url)
			
		except webnotes.DoesNotExistError:
			title, content = get_static_content(fpath)
			if not title:
				title = page_name.replace("-", " ").replace("_", " ").title()
			to_insert.append([webnotes.bean({
				"doctype":"Web Page",
				"idx": priority,
				"title": title,
				"page_name": page_name,
				"main_section": content,
				"published": 1,
				"parent_website_sitemap": parent_website_sitemap
			}), os.path.getmtime(fpath)])
	
	for app in webnotes.get_installed_apps():
		statics_path = webnotes.get_app_path(app, "templates", "statics")

		if os.path.exists(webnotes.get_app_path(app, "templates", "statics")):
			for basepath, folders, files in os.walk(statics_path):
				# index file first!
				index = []
				if "index.txt" in files:
					with open(os.path.join(basepath, "index.txt"), "r") as indexfile:
						index = indexfile.read().splitlines()
								
				for fname in files:
					page_name = fname.rsplit(".", 1)[0]					
					if page_name=="index" and fname!="index.txt":
						sync_file(fname, os.path.join(basepath, fname), statics_path)
						break
						
				# other files
				for fname in files:
					page_name = fname.rsplit(".", 1)[0]					
					if page_name!="index":
						sync_file(fname, os.path.join(basepath, fname), statics_path, 
							index.index(page_name) if page_name in index else 0)
					
	# delete not synced
	if synced:
		webnotes.delete_doc("Web Page", webnotes.conn.sql_list("""select docname from `tabWebsite Sitemap`
			where ifnull(static_file_timestamp,'')!='' and name not in ({}) 
				order by (rgt-lft) asc""".format(', '.join(["%s"]*len(synced))), tuple(synced)))
	else:
		webnotes.delete_doc("Web Page", webnotes.conn.sql_list("""select docname from `tabWebsite Sitemap`
			where ifnull(static_file_timestamp,'')!='' order by (rgt-lft) asc"""))
		

	# insert
	for page, mtime in to_insert:
		page.insert()

		# update timestamp
		sitemap = webnotes.bean("Website Sitemap", {"ref_doctype": "Web Page", 
			"docname": page.doc.name})
		sitemap.doc.static_file_timestamp = mtime
		sitemap.save()
		

def get_static_content(fpath):
	with open(fpath, "r") as contentfile:
		title = None
		content = unicode(contentfile.read(), 'utf-8')

		if fpath.endswith(".md"):
			lines = content.splitlines()
			first_line = lines[0].strip()

			if first_line.startswith("# "):
				title = first_line[2:]
				content = "\n".join(lines[1:])

			content = markdown(content)
			
		content = unicode(content.encode("utf-8"), 'utf-8')
			
		return title, content
	
				
