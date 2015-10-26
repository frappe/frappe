# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""
frappe.utils.autodoc
~~~~~~~~~~~~~~~~~~~~

Inspect elements of a given module and return its objects
"""

import inspect, importlib, re, frappe
from frappe.model.document import get_controller


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
		"docs": getattr(obj, "__doc__", "")
	}

installed = None
def get_version(name):
	print name
	global installed

	if not installed:
		installed = frappe.get_installed_apps()

	def _for_module(m):
		return getattr(importlib.import_module(m.split(".")[0]), "__version__", "0.0.0")

	if "." in name or name in installed:
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
	docs = getattr(value, "__doc__")
	return {
		"name": value.__name__,
		"type": "function",
		"args": inspect.getargspec(value),
		"docs": parse(docs) if docs else '<span class="text-muted">No docs</span>',
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
