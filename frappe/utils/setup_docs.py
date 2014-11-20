"""Automatically setup docs for a project"""

import os, json

models_base_path = "apps/frappe_io/frappe_io/www/docs/models"
api_base_path = "apps/frappe_io/frappe_io/www/docs/api"
app_path = "apps/frappe/frappe"

def make_docs():
	"""Generate source templates for models reference and module API.

	Must set globals `models_base_path`, `api_base_path` and `app_path`.
	"""
	for basepath, folders, files in os.walk(app_path):
		if "doctype" in folders and not "doctype" in basepath:
			module = os.path.basename(basepath)
			make_index_txt_and_index_md(module)
			update_index_txt(module)

		if "doctype" in basepath:
			parts = basepath.split("/")
			#print parts
			module, doctype = parts[-3], parts[-1]

			if doctype not in ("doctype", "boilerplate"):
				write_model_file(basepath, module, doctype)

def make_index_txt_and_index_md(module):
	module_folder = os.path.join(models_base_path, module)
	if not os.path.exists(module_folder):
		os.makedirs(module_folder)
		index_txt_path = os.path.join(module_folder, "index.txt")
		if not os.path.exists(index_txt_path):
			with open(index_txt_path, "w") as f:
				f.write("")
		index_md_path = os.path.join(module_folder, "index.md")
		if not os.path.exists(index_md_path):
			with open(index_md_path, "w") as f:
				f.write("# {0}\n\n{{index}}".format(module.title()))

def update_index_txt(module):
	module_folder = os.path.join(models_base_path, module)
	index_txt_path = os.path.join(module_folder, "index.txt")
	models = filter(lambda d: d.endswith(".md") and d!="index.md", os.listdir(module_folder))
	models = [d[:-3] for d in models]
	with open(index_txt_path, "r") as f:
		index_parts = filter(None, f.read().splitlines())

	if set(models) != set(index_parts):
		with open(index_txt_path, "w") as f:
			f.write("\n".join(models))

def write_model_file(basepath, doctype, module):
	model_path = os.path.join(models_base_path, module, doctype + ".md")

	if not os.path.exists(model_path):
		model_json_path = os.path.join(basepath, doctype + ".json")
		if os.path.exists(model_json_path):
			with open(model_json_path, "r") as j:
				doctype_real_name = json.loads(j.read()).get("name")

			print doctype_real_name

			with open(model_path, "w") as f:
				f.write("""# %s

{%% from "templates/autodoc/doctype.html" import render_doctype %%}

{{ render_doctype("%s") }}

<!-- jinja --><!-- static -->
""" % (doctype_real_name, doctype_real_name))

if __name__ == "__main__":
	make_docs()
