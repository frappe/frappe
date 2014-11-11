# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""
frappe.utils.autodoc
~~~~~~~~~~~~~~~~~~~~

Inspect elements of a given module and return its objects
"""

import inspect, importlib, re

def automodule(name):
	attributes = []
	obj = importlib.import_module(name)

	for attrname in dir(obj):
		value = getattr(obj, attrname)
		if inspect.isfunction(value):
			attributes.append(get_function_info(value, name))

	return filter(None, attributes)

def get_function_info(value, module_name):
	docs = getattr(value, "__doc__", "")
	if docs:
		return {
			"name": value.__name__,
			"type": "function",
			"args": inspect.getargspec(value),
			"docs": parse(docs)
		}

def parse(docs):
	if ":param" in docs:
		out, title_set = [], False
		for line in docs.splitlines():
			if ":param" in line and not title_set:
				# add title and list
				out.append("")
				out.append("**Parameters:**")
				out.append("")
				title_set = True

			if ":param" in line:
				line = re.sub("\s*:param\s([^:]+):(.*)", "- **\g<1>** - \g<2>", line)

			if title_set and not ":param" in line:
				# marker for end of list
				out.append("")

			out.append(line)

		docs = "\n".join(out)

	return docs
