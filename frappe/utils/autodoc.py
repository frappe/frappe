# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""
frappe.utils.autodoc
~~~~~~~~~~~~~~~~~~~~

Inspect elements of a given module and return its objects
"""

import inspect, importlib, re, frappe, os, shutil
from frappe.model.document import get_controller
from markdown2 import markdown

def build(app):
	app_path = frappe.get_app_path(app)
	source = frappe.get_app_path(app, "src")
	dest = frappe.get_app_path(app, "www")
	for basepath, folders, files in os.walk(source):
		destpath = os.path.join(dest, os.path.relpath(basepath, source))

		# make target dir if missing
		if not os.path.exists(destpath):
			os.makedirs(destpath)

		# delete removed folders in source from dest
		for destfolder in os.listdir(destpath):
			if os.path.isdir(os.path.join(destpath, destfolder)):
				if destfolder not in folders:
					os.path.join(destpath, destfolder)
					shutil.rmtree(os.path.join(destpath, destfolder))

		for fname in files:
			# delete file
			if os.path.exists(os.path.join(destpath, fname)):
				os.remove(os.path.join(destpath, fname))

			print fname
			if fname.rsplit(".", 1)[-1] in ("md", "html"):
				# render template and build file
				with open(os.path.join(destpath, fname.rsplit(".", 1)[0] + ".html"), "w") as destfile:
					if fname.endswith(".md"):
						# convert markdown to html before rendering
						with open(os.path.join(basepath, fname), "r") as template_file:
							template = markdown(template_file.read())
						html = frappe.render_template(template, {}).encode("utf-8")
						destfile.write(html)
					else:
						template_path = os.path.relpath(os.path.join(basepath, fname), app_path)
						html = frappe.render_template(template_path, {}, is_path=True).encode("utf-8")
						destfile.write(html)
			else:
				# not a template, copy
				shutil.copyfile(os.path.join(basepath, fname), os.path.join(destpath, fname))

def automodule(name):
	"""Returns a list of attributes for given module string.

	Attribute Format:

		{
			"name": [__name__],
			"type": ["function" or "class"]
			"args": [inspect.getargspec(value) (for function)]
			"docs": [__doc__ as markdown]
		}

	:param name: Module name as string."""
	attributes = []
	obj = importlib.import_module(name)

	for attrname in dir(obj):
		value = getattr(obj, attrname)
		if getattr(value, "__module__", None) != name:
			# imported member, ignore
			continue

		if inspect.isclass(value):
			attributes.append(get_class_info(value, name))

		if inspect.isfunction(value):
			attributes.append(get_function_info(value))

	return {
		"members": filter(None, attributes),
	}

def get_version(name):
	def _for_module(m):
		return importlib.import_module(m.split(".")[0]).__version__

	if "." in name or name=="frappe":
		return _for_module(name)
	else:
		return _for_module(get_controller(name).__module__)


def get_class_info(class_obj, module_name):
	members = []
	for attrname in dir(class_obj):
		member = getattr(class_obj, attrname)

		if inspect.ismethod(member):

			if getattr(member, "__module__", None) != module_name:
				# inherited member, ignore
				continue

			members.append(get_function_info(member))

	return {
		"name": class_obj.__name__,
		"type": "class",
		"bases": [b.__module__ + "." + b.__name__ for b in class_obj.__bases__],
		"members": filter(None, members),
		"docs": parse(getattr(class_obj, "__doc__", ""))
	}

def get_function_info(value):
	docs = getattr(value, "__doc__", "")
	if docs:
		return {
			"name": value.__name__,
			"type": "function",
			"args": inspect.getargspec(value),
			"docs": parse(docs),
			"whitelisted": value in frappe.whitelisted
		}

def parse(docs):
	"""Parse __docs__ text into markdown. Will parse directives like `:param name:` etc"""
	# strip leading tabs
	if not docs:
		return ""

	docs = strip_leading_tabs(docs)

	if ":param" in docs:
		out, title_set = [], False
		for line in docs.splitlines():
			if ":param" in line:
				if not title_set:
					# add title and list
					out.append("")
					out.append("**Parameters:**")
					out.append("")
					title_set = True

				line = re.sub("\s*:param\s([^:]+):(.*)", "- **`\g<1>`** - \g<2>", line)

			elif title_set and not ":param" in line:
				# marker for end of list
				out.append("")
				title_set = False

			out.append(line)

		docs = "\n".join(out)

	return docs

def strip_leading_tabs(docs):
	"""Strip leading tabs from __doc__ text."""
	lines = docs.splitlines()
	if len(lines) > 1:
		start_line = 1
		ref_line = lines[start_line]
		while not ref_line:
			start_line += 1
			if start_line > len(lines): break
			ref_line = lines[start_line]

		strip_left = len(ref_line) - len(ref_line.lstrip())
		if strip_left:
			docs = "\n".join([lines[0]] + [l[strip_left:] for l in lines[1:]])

	return docs

def automodel(doctype):
	"""return doctype template"""
	pass

def get_doclink(name):
	"""Returns `__doclink__` property of a module or DocType if exists"""
	if name=="[Select]": return ""

	if "." in name:
		obj = frappe.get_attr(name)
	else:
		obj = get_controller(name)

	if hasattr(obj, "__doclink__"):
		return obj.__doclink__
	else:
		return ""
