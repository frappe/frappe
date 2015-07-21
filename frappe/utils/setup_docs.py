"""Automatically setup docs for a project

Call from command line:

	bench frappe --setup_docs app docs_app path

"""

import os, json, frappe, markdown2, shutil

class setup_docs(object):
	def __init__(self):
		"""Generate source templates for models reference and module API
			and templates at `templates/autodoc`
		"""
		self.app = frappe.get_hooks("autodoc").get("for_app")[0]
		docs_app = frappe.get_hooks("autodoc").get("docs_app")[0]

		hooks = frappe.get_hooks(app_name = self.app)
		self.app_title = hooks.get("app_title")[0]

		self.app_path = frappe.get_app_path(self.app)
		path = frappe.get_app_path(docs_app, "www", "current")

		print "Deleting current..."
		shutil.rmtree(path, ignore_errors = True)
		os.makedirs(path)

		self.app_context =  {
			"app": {
				"name": self.app,
				"title": self.app_title,
				"description": markdown2.markdown(hooks.get("app_description")[0]),
				"version": hooks.get("app_version")[0],
				"publisher": hooks.get("app_publisher")[0],
				"github_link": hooks.get("github_link")[0],
			}
		}

		# make home page
		with open(os.path.join(path, "index.html"), "w") as home:
			home.write(frappe.render_template("templates/autodoc/docs_home.html",
			self.app_context))

		# make folders
		self.models_base_path = os.path.join(path, "models")
		self.make_folder(self.models_base_path,
			template = "templates/autodoc/models_home.html")

		self.api_base_path = os.path.join(path, "api")
		self.make_folder(self.api_base_path,
			template = "templates/autodoc/api_home.html")

		for basepath, folders, files in os.walk(self.app_path):
			if "doctype" not in basepath:
				if "doctype" in folders:
					module = os.path.basename(basepath)

					module_folder = os.path.join(self.models_base_path, module)

					self.make_folder(module_folder,
						template = "templates/autodoc/module_home.html",
						context = {"name": module})
					self.update_index_txt(module_folder)

			if "doctype" in basepath:
				parts = basepath.split("/")
				#print parts
				module, doctype = parts[-3], parts[-1]

				if doctype not in ("doctype", "boilerplate"):
					self.write_model_file(basepath, module, doctype)

			elif self.is_py_module(basepath, folders, files):
				self.write_modules(basepath, folders, files)

	def is_py_module(self, basepath, folders, files):
		return "__init__.py" in files \
			and (not "/doctype" in basepath) \
			and (not "/patches" in basepath) \
			and (not "/change_log" in basepath) \
			and (not "/report" in basepath) \
			and (not "/page" in basepath) \
			and (not "/templates" in basepath) \
			and (not "/tests" in basepath) \
			and (not "doctype" in folders)

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
		pages = filter(lambda d: (d.endswith(".html") and d!="index.html") \
			or os.path.isdir(os.path.join(path, d)), os.listdir(path))
		pages = [d.rsplit(".", 1)[0] for d in pages]

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
