"""Automatically setup docs for a project

Call from command line:

	bench setup-docs app path

"""
from __future__ import unicode_literals, print_function

import os, json, frappe, shutil, re
from frappe.website.context import get_context
from frappe.utils import markdown

class setup_docs(object):
	def __init__(self, app):
		"""Generate source templates for models reference and module API
			and templates at `templates/autodoc`
		"""
		self.app = app


		frappe.flags.web_pages_folders = ['docs',]
		frappe.flags.web_pages_apps = [self.app,]

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
				"description": self.hooks.get("app_description")[0],
				"version": version,
				"publisher": self.hooks.get("app_publisher")[0],
				"icon": self.hooks.get("app_icon")[0],
				"email": self.hooks.get("app_email")[0],
				"headline": self.docs_config.headline,
				"brand_html": getattr(self.docs_config, 'brand_html', None),
				"sub_heading": self.docs_config.sub_heading,
				"source_link": self.docs_config.source_link,
				"hide_install": getattr(self.docs_config, "hide_install", False),
				"docs_base_url": self.docs_config.docs_base_url,
				"long_description": markdown(getattr(self.docs_config, "long_description", "")),
				"license": self.hooks.get("app_license")[0],
				"branch": getattr(self.docs_config, "branch", None) or "develop",
				"style": getattr(self.docs_config, "style", ""),
				"google_analytics_id": getattr(self.docs_config, "google_analytics_id", "")
			}),
			"metatags": {
				"description": self.hooks.get("app_description")[0],
			},
			"get_doctype_app": frappe.get_doctype_app
		}

	def build(self, docs_version):
		"""Build templates for docs models and Python API"""
		self.docs_path = frappe.get_app_path(self.app, "docs")
		self.path = os.path.join(self.docs_path, docs_version)
		self.app_context["app"]["docs_version"] = docs_version

		self.app_title = self.hooks.get("app_title")[0]
		self.app_path = frappe.get_app_path(self.app)

		print("Deleting current...")
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

		# make /user
		user_path = os.path.join(self.docs_path, "user")
		if not os.path.exists(user_path):
			os.makedirs(user_path)

		# make /assets/img
		img_path = os.path.join(self.docs_path, "assets", "img")
		if not os.path.exists(img_path):
			os.makedirs(img_path)

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

	def make_docs(self, target, local = False):
		self.target = target
		self.local = local

		frappe.flags.local_docs = local

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
				full_module_name = os.path.relpath(os.path.join(basepath, f),
					self.app_path)[:-3].replace("/", ".")

				module_name = full_module_name.replace(".__init__", "")

				module_doc_path = os.path.join(module_folder,
					self.app + "." + module_name + ".html")

				self.make_folder(basepath)

				if not os.path.exists(module_doc_path):
					print("Writing " + module_doc_path)
					with open(module_doc_path, "w") as f:
						context = {"name": self.app + "." + module_name}
						context.update(self.app_context)
						context['full_module_name'] = self.app + '.' + full_module_name
						f.write(frappe.render_template("templates/autodoc/pymodule.html",
							context).encode('utf-8'))

		self.update_index_txt(module_folder)

	def make_folder(self, path, template=None, context=None):
		if not template:
			template = "templates/autodoc/package_index.html"

		if not os.path.exists(path):
			os.makedirs(path)

			index_txt_path = os.path.join(path, "index.txt")
			print("Writing " + index_txt_path)
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
			print("Writing " + index_html_path)
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
			print("Updating " + index_txt_path)
			with open(index_txt_path, "w") as f:
				f.write("\n".join(pages))

	def write_model_file(self, basepath, module, doctype):
		model_path = os.path.join(self.models_base_path, module, doctype + ".html")

		if not os.path.exists(model_path):
			model_json_path = os.path.join(basepath, doctype + ".json")
			if os.path.exists(model_json_path):
				with open(model_json_path, "r") as j:
					doctype_real_name = json.loads(j.read()).get("name")

				print("Writing " + model_path)

				with open(model_path, "w") as f:
					context = {"doctype": doctype_real_name}
					context.update(self.app_context)
					f.write(frappe.render_template("templates/autodoc/doctype.html",
						context).encode("utf-8"))

	def write_files(self):
		"""render templates and write files to target folder"""
		frappe.flags.home_page = "index"

		from frappe.website.router import get_pages, make_toc
		pages = get_pages(self.app)

		# clear the user, current folder in target
		shutil.rmtree(os.path.join(self.target, "user"), ignore_errors=True)
		shutil.rmtree(os.path.join(self.target, "current"), ignore_errors=True)

		def raw_replacer(matchobj):
			if '{% raw %}' in matchobj.group(0):
				return matchobj.group(0)
			else:
				return '{% raw %}' + matchobj.group(0) + '{% endraw %}'

		cnt = 0
		for path, context in pages.iteritems():
			print("Writing {0}".format(path))

			# set this for get_context / website libs
			frappe.local.path = path

			context.update({
				"page_links_with_extn": True,
				"relative_links": True,
				"docs_base_url": self.docs_base_url,
				"url_prefix": self.docs_base_url,
			})

			context.update(self.app_context)

			context = get_context(path, context)

			if context.basename:
				target_path_fragment = context.route + '.html'
			else:
				# index.html
				target_path_fragment = context.route + '/index.html'

			target_filename = os.path.join(self.target, target_path_fragment.strip('/'))

			context.brand_html = context.app.brand_html
			context.top_bar_items = context.favicon = None

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

			context.top_bar_items = [{"label": '<i class="octicon octicon-search"></i>', "url": "#",
				"right": 1}] + context.top_bar_items

			context.parents = []
			parent_route = os.path.dirname(context.route)
			if pages[parent_route]:
				context.parents = [pages[parent_route]]

			context.only_static = True
			context.base_template_path = "templates/autodoc/base_template.html"

			if '<code>' in context.source:
				context.source = re.sub('\<code\>(.*)\</code\>', raw_replacer, context.source)

			html = frappe.render_template(context.source, context)

			html = make_toc(context, html, self.app)

			if not "<!-- autodoc -->" in html:
				html = html.replace('<!-- edit-link -->',
					edit_link.format(\
						source_link = self.docs_config.source_link,
						app_name = self.app,
						branch = context.app.branch,
						target = context.template))

			if not os.path.exists(os.path.dirname(target_filename)):
				os.makedirs(os.path.dirname(target_filename))

			with open(target_filename, "w") as htmlfile:
				htmlfile.write(html.encode("utf-8"))

				cnt += 1

		print("Wrote {0} files".format(cnt))


	def copy_assets(self):
		"""Copy jquery, bootstrap and other assets to files"""

		print("Copying assets...")
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
			"js/docs.js": "js/docs.js",
			"css/bootstrap.css": "css/bootstrap.css",
			"css/font-awesome.css": "css/font-awesome.css",
			"css/docs.css": "css/docs.css",
			"css/hljs.css": "css/hljs.css",
			"css/fonts": "css/fonts",
			"css/octicons": "css/octicons",
			# always overwrite octicons.css to fix the path
			"css/octicons/octicons.css": "css/octicons/octicons.css",
			"images/frappe-bird-grey.svg": "img/frappe-bird-grey.svg",
			"images/favicon.png": "img/favicon.png",
			"images/background.png": "img/background.png",
			"images/smiley.png": "img/smiley.png",
			"images/up.png": "img/up.png"
		}

		for source, target in copy_files.iteritems():
			source_path = frappe.get_app_path("frappe", "public", source)
			if os.path.isdir(source_path):
				if not os.path.exists(os.path.join(assets_path, target)):
					shutil.copytree(source_path, os.path.join(assets_path, target))
			else:
				shutil.copy(source_path, os.path.join(assets_path, target))

		# fix path for font-files, background
		files = (
			os.path.join(assets_path, "css", "octicons", "octicons.css"),
			os.path.join(assets_path, "css", "font-awesome.css"),
			os.path.join(assets_path, "css", "docs.css"),
		)

		for path in files:
			with open(path, "r") as css_file:
				text = unicode(css_file.read(), 'utf-8')
			with open(path, "w") as css_file:
				if "docs.css" in path:
					css_file.write(text.replace("/assets/img/",
						self.docs_base_url + '/assets/img/').encode('utf-8'))
				else:
					css_file.write(text.replace("/assets/frappe/", self.docs_base_url + '/assets/').encode('utf-8'))


edit_link = '''
<div class="page-container">
	<div class="page-content">
	<div class="edit-container text-center">
		<i class="fa fa-smile"></i>
		<a class="text-muted edit" href="{source_link}/blob/{branch}/{app_name}/{target}">
			Improve this page
		</a>
	</div>
	</div>
</div>'''
