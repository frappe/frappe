# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os, time, sys

from frappe.utils import update_progress_bar

def sync_statics(rebuild=False):
	s = sync()
	s.verbose = True
	while True:
		s.start(rebuild)
		frappe.db.commit()
		time.sleep(2)
		rebuild = False

class sync(object):
	def __init__(self, verbose=False):
		self.verbose = verbose

	def start(self, rebuild=False):
		self.synced = []
		self.synced_paths = []
		self.to_insert = []
		self.to_update = []
		self.updated = 0
		self.rebuild = rebuild
		for app in frappe.get_installed_apps():
			self.sync_for_app(app)

		self.insert_and_update()
		self.cleanup()

	def sync_for_app(self, app):
		self.statics_path = frappe.get_app_path(app, "templates", "statics")
		if os.path.exists(self.statics_path):
			for basepath, folders, files in os.walk(self.statics_path):
				self.sync_folder(basepath, folders, files)

	def sync_folder(self, basepath, folders, files):
		self.get_index_txt(basepath, files)
		index_found = self.sync_index_page(basepath, files)

		if not index_found and basepath!=self.statics_path:
			# not synced either by generator or by index.html
			return

		if self.index:
			self.sync_using_given_index(basepath, folders, files)
		else:
			self.sync_alphabetically(basepath, folders, [filename for filename in files if filename.endswith('html') or filename.endswith('md')])

	def get_index_txt(self, basepath, files):
		self.index = []
		if "index.txt" in files:
			with open(os.path.join(basepath, "index.txt"), "r") as indexfile:
				self.index = indexfile.read().splitlines()

	def sync_index_page(self, basepath, files):
		for extn in ("md", "html"):
			fname = "index." + extn
			if fname in files:
				self.sync_file(fname, os.path.join(basepath, fname), None)
				return True

	def sync_using_given_index(self, basepath, folders, files):
		for i, page_name in enumerate(self.index):
			if page_name in folders:
				# for folder, sync inner index first (so that idx is set)
				for extn in ("md", "html"):
					path = os.path.join(basepath, page_name, "index." + extn)
					if os.path.exists(path):
						self.sync_file("index." + extn, path, i)
						break

			# other files
			for extn in ("md", "html"):
				fname = page_name + "." + extn
				if fname in files:
					self.sync_file(fname, os.path.join(basepath, fname), i)
					break
				elif page_name not in folders:
					print page_name + " not found in " + basepath

	def sync_alphabetically(self, basepath, folders, files):
		files.sort()
		for fname in files:
			page_name = fname.rsplit(".", 1)[0]
			if not (page_name=="index" and basepath!=self.statics_path):
				self.sync_file(fname, os.path.join(basepath, fname), None)

	def sync_file(self, fname, template_path, priority):
		route = os.path.relpath(template_path, self.statics_path).rsplit(".", 1)[0]

		if fname.rsplit(".", 1)[0]=="index" and \
			os.path.dirname(template_path) != self.statics_path:
			route = os.path.dirname(route)


		page_name = os.path.basename(route)
		parent_web_page = os.path.basename(os.path.dirname(route))
		published = 1
		idx = priority

		if page_name in self.synced:
			return

		title = self.get_title(template_path)

		if not frappe.db.get_value("Web Page", {"page_name":page_name}):
			web_page = frappe.new_doc("Web Page")
			web_page.page_name = page_name
			web_page.parent_web_page = parent_web_page
			web_page.template_path = template_path
			web_page.title = title
			web_page.published = published
			web_page.idx = idx
			web_page.from_website_sync = True
			self.to_insert.append(web_page)

		else:
			web_page = frappe.get_doc("Web Page", {"page_name":page_name})
			dirty = False
			for key in ("parent_web_page", "title", "template_path", "published", "idx"):
				if web_page.get(key) != locals().get(key):
					web_page.set(key, locals().get(key))
					dirty = True

			if dirty:
				web_page.from_website_sync = True
				self.to_update.append(web_page)

		self.synced.append(page_name)

	def get_title(self, fpath):
		title = os.path.basename(fpath).rsplit(".", 1)[0]
		if title =="index":
			title = os.path.basename(os.path.dirname(fpath))

		title = title.replace("-", " ").replace("_", " ").title()

		with open(fpath, "r") as f:
			content = unicode(f.read().strip(), "utf-8")

			if content.startswith("# "):
				title = content.splitlines()[0][2:]

			if "<!-- title:" in content:
				title = content.split("<!-- title:", 1)[1].split("-->", 1)[0].strip()

		return title

	def insert_and_update(self):
		if self.to_insert:
			l = len(self.to_insert)
			for i, page in enumerate(self.to_insert):
				if self.verbose:
					print "Inserting " + page.page_name
				else:
					update_progress_bar("Updating Static Pages", i, l)

				page.insert()
			if not self.verbose: print ""

		if self.to_update:
			for i, page in enumerate(self.to_update):
				if not self.verbose:
					print "Updating " + page.page_name
				else:
					sys.stdout.write("\rUpdating statics {0}/{1}".format(i+1, len(self.to_update)))
					sys.stdout.flush()

				page.save()
			if not self.verbose: print ""

	def cleanup(self):
		if self.synced:
			# delete static web pages that are not in immediate list
			frappe.delete_doc("Web Page", frappe.db.sql_list("""select name
				from `tabWeb Page`
				where ifnull(template_path,'')!=''
				and name not in ({})""".format(', '.join(["%s"]*len(self.synced))),
					tuple(self.synced)), force=1)
		else:
			# delete all static web pages
			frappe.delete_doc("Web Page", frappe.db.sql_list("""select name
				from `tabWeb Page`
				where ifnull(template_path,'')!=''"""), force=1)


