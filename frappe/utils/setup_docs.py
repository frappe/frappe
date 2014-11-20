"""Automatically setup docs for a project"""

import os, json

models_base_path = "apps/frappe_io/frappe_io/www/docs/models"
api_base_path = "apps/frappe_io/frappe_io/www/docs/api"
app_path = "apps/frappe/frappe"
app_name = "frappe"

def make_docs():
	"""Generate source templates for models reference and module API.

	Must set globals `models_base_path`, `api_base_path` and `app_path`.
	"""
	for basepath, folders, files in os.walk(app_path):
		if "doctype" in folders and not "doctype" in basepath:
			module = os.path.basename(basepath)

			module_folder = os.path.join(models_base_path, module)

			make_folder(module_folder)
			update_index_txt(module_folder)

		if "doctype" in basepath:
			parts = basepath.split("/")
			#print parts
			module, doctype = parts[-3], parts[-1]

			if doctype not in ("doctype", "boilerplate"):
				write_model_file(basepath, module, doctype)

		elif is_py_module(basepath, folders, files):
			write_modules(basepath, folders, files)

def is_py_module(basepath, folders, files):
	return "__init__.py" in files \
		and (not "/doctype" in basepath) \
		and (not "/patches" in basepath) \
		and (not "/report" in basepath) \
		and (not "/page" in basepath) \
		and (not "/templates" in basepath) \
		and (not "/tests" in basepath) \
		and (not "doctype" in folders)

def write_modules(basepath, folders, files):
	module_folder = os.path.join(api_base_path, os.path.relpath(basepath, app_path))
	make_folder(module_folder)

	for f in files:
		if f.endswith(".py"):
			module_name = os.path.relpath(os.path.join(basepath, f),
				app_path)[:-3].replace("/", ".").replace(".__init__", "")

			module_doc_path = os.path.join(module_folder,
				app_name + "." + module_name + ".md")

			make_folder(basepath)

			if not os.path.exists(module_doc_path):
				print "Writing " + module_doc_path
				with open(module_doc_path, "w") as f:
					f.write("""# %s

{%%- from "templates/autodoc/macros.html" import automodule -%%}

{{ automodule("%s") }}""" % (app_name + "." + module_name, app_name + "." + module_name))

	update_index_txt(module_folder)

def make_folder(path):
	if not os.path.exists(path):
		os.makedirs(path)

	index_txt_path = os.path.join(path, "index.txt")
	if not os.path.exists(index_txt_path):
		print "Writing " + index_txt_path
		with open(index_txt_path, "w") as f:
			f.write("")

	index_md_path = os.path.join(path, "index.md")
	if not os.path.exists(index_md_path):
		print "Writing " + index_md_path
		with open(index_md_path, "w") as f:
			f.write("# {0}\n\n{{index}}".format(os.path.basename(path).title()))

def update_index_txt(path):
	index_txt_path = os.path.join(path, "index.txt")
	pages = filter(lambda d: d.endswith(".md") and d!="index.md", os.listdir(path))
	pages = [d[:-3] for d in pages]

	with open(index_txt_path, "r") as f:
		index_parts = filter(None, f.read().splitlines())

	if not set(pages).issubset(set(index_parts)):
		print "Updating " + index_txt_path
		with open(index_txt_path, "w") as f:
			f.write("\n".join(pages))

def write_model_file(basepath, doctype, module):
	model_path = os.path.join(models_base_path, module, doctype + ".md")

	if not os.path.exists(model_path):
		model_json_path = os.path.join(basepath, doctype + ".json")
		if os.path.exists(model_json_path):
			with open(model_json_path, "r") as j:
				doctype_real_name = json.loads(j.read()).get("name")

			print "Writing " + model_path

			with open(model_path, "w") as f:
				f.write("""# %s

{%% from "templates/autodoc/doctype.html" import render_doctype %%}

{{ render_doctype("%s") }}

<!-- jinja --><!-- static -->
""" % (doctype_real_name, doctype_real_name))

if __name__ == "__main__":
	make_docs()
