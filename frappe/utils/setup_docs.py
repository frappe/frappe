"""Automatically setup docs for a project

Call from command line:

	bench setup-docs app path

"""

import os, json, frappe, markdown2, shutil
import frappe.website.statics
from frappe.website.context import get_context
from markdown2 import markdown

class setup_docs(object):
	def __init__(self, app):
		"""Generate source templates for models reference and module API
			and templates at `templates/autodoc`
		"""
		self.app = app
		self.hooks = frappe.get_hooks(app_name = self.app)
		self.app_title = self.hooks.get("app_title")[0]
		self.setup_app_context()

	def setup_app_context(self):
		self.docs_config = frappe.get_module(self.app + ".config.docs")
		version = self.hooks.get("app_version")[0]
		self.app_context =  {
			"app": frappe._dict({
				"name": self.app,
				"title": self.app_title,
				"description": markdown2.markdown(self.hooks.get("app_description")[0]),
				"version": version,
				"publisher": self.hooks.get("app_publisher")[0],
				"icon": self.hooks.get("app_icon")[0],
				"email": self.hooks.get("app_email")[0],
				"headline": self.docs_config.headline,
				"sub_heading": self.docs_config.sub_heading,
				"source_link": self.docs_config.source_link,
				"hide_install": getattr(self.docs_config, "hide_install", False),
				"docs_base_url": self.docs_config.docs_base_url,
				"long_description": getattr(self.docs_config, "long_description", ""),
				"license": self.hooks.get("app_license")[0],
				"branch": getattr(self.docs_config, "branch", None) or "develop",
				"version": getattr(self.docs_config, "version", "")
			}),
			"get_doctype_app": frappe.get_doctype_app
		}

	def build(self, docs_version):
		"""Build templates for docs models and Python API"""
		self.docs_path = frappe.get_app_path(self.app, "docs")
		self.path = os.path.join(self.docs_path, docs_version)
		self.app_context["app"]["docs_version"] = docs_version

		self.app_title = self.hooks.get("app_title")[0]
		self.app_path = frappe.get_app_path(self.app)

		print "Deleting current..."
		shutil.rmtree(self.path, ignore_errors = True)
		os.makedirs(self.path)

		self.make_home_pages()

		for basepath, folders, files in os.walk(self.app_path):

			# make module home page
			if "/doctype/" not in basepath and "doctype" in folders:
				module = os.path.basename(basepath)

				module_folder = os.path.join(self.models_base_path, module)

				self.make_folder(module_folder,
					template = "templates/autodoc/module_home.html",
					context = {"name": module})
				self.update_index_txt(module_folder)

			# make for model files
			if "/doctype/" in basepath:
				parts = basepath.split("/")
				#print parts
				module, doctype = parts[-3], parts[-1]

				if doctype not in ("doctype", "boilerplate"):
					self.write_model_file(basepath, module, doctype)

			# standard python module
			if self.is_py_module(basepath, folders, files):
				self.write_modules(basepath, folders, files)

		self.build_user_docs()

	def make_home_pages(self):
		"""Make standard home pages for docs, developer docs, api and models
			from templates"""
		# make dev home page
		with open(os.path.join(self.docs_path, "index.html"), "w") as home:
			home.write(frappe.render_template("templates/autodoc/docs_home.html",
			self.app_context))

		# make dev home page
		with open(os.path.join(self.path, "index.html"), "w") as home:
			home.write(frappe.render_template("templates/autodoc/dev_home.html",
			self.app_context))

		# make folders
		self.models_base_path = os.path.join(self.path, "models")
		self.make_folder(self.models_base_path,
			template = "templates/autodoc/models_home.html")

		self.api_base_path = os.path.join(self.path, "api")
		self.make_folder(self.api_base_path,
			template = "templates/autodoc/api_home.html")

	def build_user_docs(self):
		"""Build templates for user docs pages, if missing."""
		#user_docs_path = os.path.join(self.docs_path, "user")

		# license
		with open(os.path.join(self.app_path, "..", "license.txt"), "r") as license_file:
			self.app_context["license_text"] = markdown(license_file.read())
			html = frappe.render_template("templates/autodoc/license.html",
				context = self.app_context)

		with open(os.path.join(self.docs_path, "license.html"), "w") as license_file:
			license_file.write(html.encode("utf-8"))

		# contents
		shutil.copy(os.path.join(frappe.get_app_path("frappe", "templates", "autodoc",
			"contents.html")), os.path.join(self.docs_path, "contents.html"))

		shutil.copy(os.path.join(frappe.get_app_path("frappe", "templates", "autodoc",
			"contents.py")), os.path.join(self.docs_path, "contents.py"))

		# install
		html = frappe.render_template("templates/autodoc/install.md",
			context = self.app_context)

		with open(os.path.join(self.docs_path, "install.md"), "w") as f:
			f.write(html)

		self.update_index_txt(self.docs_path)

	def sync_docs(self):
		"""Sync docs from /docs folder to **Web Page**.

		Called as `bench --site [sitename] sync-docs [appname]`
		"""
		frappe.db.sql("delete from `tabWeb Page`")
		sync = frappe.website.statics.sync()
		sync.start(path="docs", rebuild=True, apps = [self.app])

	def make_docs(self, target, local = False):
		self.target = target
		self.local = local

		if self.local:
			self.docs_base_url = ""
		else:
			self.docs_base_url = self.docs_config.docs_base_url

		# add for processing static files (full-index)
		frappe.local.docs_base_url = self.docs_base_url

		# write in target path
		self.write_files()

		# copy assets/js, assets/css, assets/img
		self.copy_assets()

	def is_py_module(self, basepath, folders, files):
		return "__init__.py" in files \
			and (not "/doctype" in basepath) \
			and (not "/patches" in basepath) \
			and (not "/change_log" in basepath) \
			and (not "/report" in basepath) \
			and (not "/page" in basepath) \
			and (not "/templates" in basepath) \
			and (not "/tests" in basepath) \
			and (not "/docs" in basepath)

	def write_modules(self, basepath, folders, files):
		module_folder = os.path.join(self.api_base_path, os.path.relpath(basepath, self.app_path))
		self.make_folder(module_folder)

		for f in files:
			if f.endswith(".py"):
				module_name = os.path.relpath(os.path.join(basepath, f),
					self.app_path)[:-3].replace("/", ".").replace(".__init__", "")

				module_doc_path = os.path.join(module_folder,
					self.app + "." + module_name + ".html")

				self.make_folder(basepath)

				if not os.path.exists(module_doc_path):
					print "Writing " + module_doc_path
					with open(module_doc_path, "w") as f:
						context = {"name": self.app + "." + module_name}
						context.update(self.app_context)
						f.write(frappe.render_template("templates/autodoc/pymodule.html",
							context))

		self.update_index_txt(module_folder)

	def make_folder(self, path, template=None, context=None):
		if not template:
			template = "templates/autodoc/package_index.html"

		if not os.path.exists(path):
			os.makedirs(path)

			index_txt_path = os.path.join(path, "index.txt")
			print "Writing " + index_txt_path
			with open(index_txt_path, "w") as f:
				f.write("")

			index_html_path = os.path.join(path, "index.html")
			if not context:
				name = os.path.basename(path)
				if name==".":
					name = self.app
				context = {
					"title": name
				}
			context.update(self.app_context)
			print "Writing " + index_html_path
			with open(index_html_path, "w") as f:
				f.write(frappe.render_template(template, context))

	def update_index_txt(self, path):
		index_txt_path = os.path.join(path, "index.txt")
		pages = filter(lambda d: ((d.endswith(".html") or d.endswith(".md")) and d not in ("index.html",)) \
			or os.path.isdir(os.path.join(path, d)), os.listdir(path))
		pages = [d.rsplit(".", 1)[0] for d in pages]

		index_parts = []
		if os.path.exists(index_txt_path):
			with open(index_txt_path, "r") as f:
				index_parts = filter(None, f.read().splitlines())

		if not set(pages).issubset(set(index_parts)):
			print "Updating " + index_txt_path
			with open(index_txt_path, "w") as f:
				f.write("\n".join(pages))

	def write_model_file(self, basepath, module, doctype):
		model_path = os.path.join(self.models_base_path, module, doctype + ".html")

		if not os.path.exists(model_path):
			model_json_path = os.path.join(basepath, doctype + ".json")
			if os.path.exists(model_json_path):
				with open(model_json_path, "r") as j:
					doctype_real_name = json.loads(j.read()).get("name")

				print "Writing " + model_path

				with open(model_path, "w") as f:
					context = {"doctype": doctype_real_name}
					context.update(self.app_context)
					f.write(frappe.render_template("templates/autodoc/doctype.html",
						context).encode("utf-8"))

	def write_files(self):
		"""render templates and write files to target folder"""
		frappe.local.flags.home_page = "index"

		for page in frappe.db.sql("""select parent_website_route,
			page_name from `tabWeb Page` where ifnull(template_path, '')!=''""", as_dict=True):

			if page.parent_website_route:
				path = page.parent_website_route + "/" + page.page_name
			else:
				path = page.page_name

			print "Writing {0}".format(path)

			# set this for get_context / website libs
			frappe.local.path = path

			context = {
				"page_links_with_extn": True,
				"relative_links": True,
				"docs_base_url": self.docs_base_url,
				"url_prefix": self.docs_base_url
			}

			context.update(self.app_context)

			context = get_context(path, context)

			target_path_fragment = context.template_path.split('/docs/', 1)[1]
			target_filename = os.path.join(self.target, target_path_fragment)

			# rename .md files to .html
			if target_filename.rsplit(".", 1)[1]=="md":
				target_filename = target_filename[:-3] + ".html"

			context.brand_html = context.top_bar_items = context.favicon = None

			self.docs_config.get_context(context)

			if not context.brand_html:
				if context.docs_icon:
					context.brand_html = '<i class="{0}"></i> {1}'.format(context.docs_icon, context.app.title)
				else:
					context.brand_html = context.app.title

			if not context.top_bar_items:
				context.top_bar_items = [
					# {"label": "Contents", "url": self.docs_base_url + "/contents.html", "right": 1},
					{"label": "User Guide", "url": self.docs_base_url + "/user", "right": 1},
					{"label": "Developer Docs", "url": self.docs_base_url + "/current", "right": 1},
				]

			if not context.favicon:
				context.favicon = "/assets/img/favicon.ico"

			context.only_static = True

			html = frappe.get_template("templates/autodoc/base_template.html").render(context)

			if not "<!-- autodoc -->" in html:
				html = html.replace('<!-- edit-link -->',
					'<p><br><a class="text-muted" href="{source_link}/blob/{branch}/{app_name}/docs/{target}">Improve this page</a></p>'.format(\
						source_link = self.docs_config.source_link,
						app_name = self.app,
						branch = context.app.branch,
						target = target_path_fragment))

			if not os.path.exists(os.path.dirname(target_filename)):
				os.makedirs(os.path.dirname(target_filename))

			with open(target_filename, "w") as htmlfile:
				htmlfile.write(html.encode("utf-8"))


	def copy_assets(self):
		"""Copy jquery, bootstrap and other assets to files"""

		print "Copying assets..."
		assets_path = os.path.join(self.target, "assets")

		# copy assets from docs
		source_assets = frappe.get_app_path(self.app, "docs", "assets")
		if os.path.exists(source_assets):
			for basepath, folders, files in os.walk(source_assets):
				target_basepath = os.path.join(assets_path, os.path.relpath(basepath, source_assets))

				# make the base folder
				if not os.path.exists(target_basepath):
					os.makedirs(target_basepath)

				# copy all files in the current folder
				for f in files:
					shutil.copy(os.path.join(basepath, f), os.path.join(target_basepath, f))

		# make missing folders
		for fname in ("js", "css", "img"):
			path = os.path.join(assets_path, fname)
			if not os.path.exists(path):
				os.makedirs(path)

		copy_files = {
			"js/lib/jquery/jquery.min.js": "js/jquery.min.js",
			"js/lib/bootstrap.min.js": "js/bootstrap.min.js",
			"js/lib/highlight.pack.js": "js/highlight.pack.js",
			"css/bootstrap.css": "css/bootstrap.css",
			"css/font-awesome.css": "css/font-awesome.css",
			"css/docs.css": "css/docs.css",
			"css/hljs.css": "css/hljs.css",
			"css/font": "css/font",
			"css/octicons": "css/octicons",
			# always overwrite octicons.css to fix the path
			"css/octicons/octicons.css": "css/octicons/octicons.css",
			"images/frappe-bird-grey.svg": "img/frappe-bird-grey.svg"
		}

		for source, target in copy_files.iteritems():
			source_path = frappe.get_app_path("frappe", "public", source)
			if os.path.isdir(source_path):
				if not os.path.exists(os.path.join(assets_path, target)):
					shutil.copytree(source_path, os.path.join(assets_path, target))
			else:
				shutil.copy(source_path, os.path.join(assets_path, target))

		# fix path for font-files
		files = (
			os.path.join(assets_path, "css", "octicons", "octicons.css"),
			os.path.join(assets_path, "css", "font-awesome.css"),
		)

		for path in files:
			with open(path, "r") as css_file:
				text = css_file.read()
			with open(path, "w") as css_file:
				css_file.write(text.replace("/assets/frappe/", self.docs_base_url + '/assets/'))
