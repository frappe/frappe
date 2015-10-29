# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os

def sync_statics(rebuild=False):
	s = sync()
	s.verbose = True
	s.start(rebuild)
	frappe.db.commit()

	# while True:
	# 	s.start(rebuild)
	# 	frappe.db.commit()
	# 	time.sleep(2)
	# 	rebuild = False

class sync(object):
	def __init__(self, verbose=False, path=None):
		self.verbose = verbose

	def start(self, rebuild=False, path="www", apps=None):
		self.path = path
		self.synced = []
		self.synced_paths = []
		self.updated = 0
		if rebuild:
			frappe.db.sql("delete from `tabWeb Page` where ifnull(template_path, '')!=''")

		for app in apps or frappe.get_installed_apps():
			# print "Syncing for {0}".format(app)
			self.sync_for_app(app)
		self.cleanup()

	def sync_for_app(self, app):
		self.statics_path = frappe.get_app_path(app, self.path)
		if os.path.exists(self.statics_path):
			for basepath, folders, files in os.walk(self.statics_path):
				self.sync_folder(basepath, folders, files, app)

	def sync_folder(self, basepath, folders, files, app):
		self.get_index_txt(basepath, files)
		index_found = self.sync_index_page(basepath, files, app)

		if not index_found and basepath!=self.statics_path:
			# not synced either by generator or by index.html
			return

		if self.index:
			self.sync_using_given_index(basepath, folders, files, app)
		else:
			self.sync_alphabetically(basepath, folders, [filename for filename in files if filename.endswith('html') or filename.endswith('md')], app)

	def get_index_txt(self, basepath, files):
		self.index = []
		if "index.txt" in files:
			with open(os.path.join(basepath, "index.txt"), "r") as indexfile:
				self.index = indexfile.read().splitlines()

	def sync_index_page(self, basepath, files, app):
		for extn in ("md", "html"):
			fname = "index." + extn
			if fname in files:
				self.sync_file(fname, os.path.join(basepath, fname), None, app)
				return True

	def sync_using_given_index(self, basepath, folders, files, app):
		for i, page_name in enumerate(self.index):
			if page_name in folders:
				# for folder, sync inner index first (so that idx is set)
				for extn in ("md", "html"):
					path = os.path.join(basepath, page_name, "index." + extn)
					if os.path.exists(path):
						self.sync_file("index." + extn, path, i, app)
						break

			# other files
			if page_name + ".md" in files:
				self.sync_file(page_name + ".md", os.path.join(basepath, page_name + ".md"), i, app)
			elif page_name + ".html" in files:
				self.sync_file(page_name + ".html", os.path.join(basepath, page_name + ".html"), i, app)
			else:
				if page_name not in folders:
					print page_name + " not found in " + basepath

	def sync_alphabetically(self, basepath, folders, files, app):
		files.sort()
		for fname in files:
			page_name = fname.rsplit(".", 1)[0]
			if not (page_name=="index" and basepath!=self.statics_path):
				self.sync_file(fname, os.path.join(basepath, fname), None, app)

	def sync_file(self, fname, template_path, priority, app):
		route = os.path.relpath(template_path, self.statics_path).rsplit(".", 1)[0]

		if fname.rsplit(".", 1)[0]=="index" and \
			os.path.dirname(template_path) != self.statics_path:
			route = os.path.dirname(route)

		parent_web_page = frappe.db.sql("""select name from `tabWeb Page` where
			page_name=%s and ifnull(parent_website_route, '')=ifnull(%s, '')""",
				(os.path.basename(os.path.dirname(route)), os.path.dirname(os.path.dirname(route))))

		parent_web_page = parent_web_page and parent_web_page[0][0] or ""

		page_name = os.path.basename(route)

		published = 1
		idx = priority

		if (parent_web_page, page_name) in self.synced:
			return

		with open(template_path, "r") as f:
			content = unicode(f.read().strip(), "utf-8")

		title = self.get_title(template_path, content)

		relative_template_path = os.path.join(app, os.path.relpath(template_path, frappe.get_app_path(app)))
		if not frappe.db.get_value("Web Page", {"template_path":relative_template_path}):
			web_page = frappe.new_doc("Web Page")
			web_page.page_name = page_name
			web_page.parent_web_page = parent_web_page
			web_page.template_path = relative_template_path
			web_page.main_section = content
			web_page.title = title
			web_page.published = published
			web_page.idx = idx
			web_page.from_website_sync = True
			web_page.insert()
			if self.verbose: print "Inserted: " + web_page.name

		else:
			web_page = frappe.get_doc("Web Page", {"template_path":relative_template_path})
			dirty = False
			for key in ("parent_web_page", "title", "published", "idx"):
				if web_page.get(key) != locals().get(key):
					web_page.set(key, locals().get(key))
					dirty = True

			if web_page.template_path != relative_template_path:
				web_page.template_path = relative_template_path
				dirty = True

			if dirty:
				web_page.from_website_sync = True
				web_page.save()
				if self.verbose: print "Updated: " + web_page.name

		self.synced.append((parent_web_page, page_name))

	def get_title(self, fpath, content):
		title = os.path.basename(fpath).rsplit(".", 1)[0]
		if title =="index":
			title = os.path.basename(os.path.dirname(fpath))

		title = title.replace("-", " ").replace("_", " ").title()

		if content.startswith("# "):
			title = content.splitlines()[0][2:]

		if "<!-- title:" in content:
			title = content.split("<!-- title:", 1)[1].split("-->", 1)[0].strip()

		return title

	def cleanup(self):
		if self.synced:
			# delete static web pages that are not in immediate list
			for static_page in frappe.db.sql("""select name, page_name, parent_web_page
				from `tabWeb Page` where ifnull(template_path,'')!=''""", as_dict=1):
				if (static_page.parent_web_page, static_page.page_name) not in self.synced:
					frappe.delete_doc("Web Page", static_page.name, force=1)
		else:
			# delete all static web pages
			frappe.delete_doc("Web Page", frappe.db.sql_list("""select name
				from `tabWeb Page`
				where ifnull(template_path,'')!=''"""), force=1)


