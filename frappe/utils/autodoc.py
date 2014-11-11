# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""
frappe.utils.autodoc
~~~~~~~~~~~~~~~~~~~~

Inspect elements of a given module and return its objects
"""

import inspect, importlib

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
			"docs": docs
		}
