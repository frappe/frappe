# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes, os
from webnotes.webutils import WebsiteGenerator
from webnotes import _
from markdown2 import markdown

class DocType(WebsiteGenerator):
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
	for app in webnotes.get_installed_apps():
		statics_path = webnotes.get_app_path(app, "templates", "statics")
		
		if os.path.exists(webnotes.get_app_path(app, "templates", "statics")):
			for basepath, folders, files in os.walk(statics_path):
				for fname in files:
					fpath = os.path.join(basepath, fname)

					url = os.path.relpath(fpath, statics_path).rsplit(".", 1)[0]
					if fname.rsplit(".", 1)[0]=="index":
						url = os.path.dirname(url)
					
					parent_website_sitemap = os.path.dirname(url)
					page_name = os.path.basename(url)

					try:
						sitemap = webnotes.bean("Website Sitemap", url)

						if str(os.path.getmtime(fpath))!=sitemap.doc.static_file_timestamp:
							page = webnotes.bean("Web Page", sitemap.doc.docname)
							page.doc.main_section = get_static_content(fpath)
							page.save()

							sitemap = webnotes.bean("Website Sitemap", url)
							sitemap.doc.static_file_timestamp = os.path.getmtime(fpath)
							sitemap.save()
						
					except webnotes.DoesNotExistError:
						
						page = webnotes.bean({
							"doctype":"Web Page",
							"title": page_name.replace("-", " ").replace("_", " ").title(),
							"page_name": page_name,
							"main_section": get_static_content(fpath),
							"published": 1,
							"parent_website_sitemap": parent_website_sitemap
						}).insert()
					
						# update timestamp
						sitemap = webnotes.bean("Website Sitemap", {"ref_doctype": "Web Page", 
							"docname": page.doc.name})
						sitemap.doc.static_file_timestamp = os.path.getmtime(fpath)
						sitemap.save()
						
					synced.append(url)
					
	# delete not synced
	webnotes.delete_doc("Web Page", webnotes.conn.sql_list("""select docname from `tabWebsite Sitemap`
		where ifnull(static_file_timestamp,'')!='' 
			and name not in ({}) """.format(', '.join(["%s"]*len(synced))), tuple(synced)))

def get_static_content(fpath):
	with open(fpath, "r") as contentfile:
		content = contentfile.read()
		if fpath.endswith(".md"):
			content = markdown(content)
			
		return content
	
				
