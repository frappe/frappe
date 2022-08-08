# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from markdownify import markdownify as md

import frappe


def get_parent_doc(doc):
	"""Returns document of `reference_doctype`, `reference_doctype`"""
	if not hasattr(doc, "parent_doc"):
		if doc.reference_doctype and doc.reference_name:
			doc.parent_doc = frappe.get_doc(doc.reference_doctype, doc.reference_name)
		else:
			doc.parent_doc = None
	return doc.parent_doc


def set_timeline_doc(doc):
	"""Set timeline_doctype and timeline_name"""
	parent_doc = get_parent_doc(doc)
	if (doc.timeline_doctype and doc.timeline_name) or not parent_doc:
		return

	timeline_field = parent_doc.meta.timeline_field
	if not timeline_field:
		return

	doctype = parent_doc.meta.get_link_doctype(timeline_field)
	name = parent_doc.get(timeline_field)

	if doctype and name:
		doc.timeline_doctype = doctype
		doc.timeline_name = name

	else:
		return


def find(list_of_dict, match_function):
	"""Returns a dict in a list of dicts on matching the conditions
	        provided in match function

	Usage:
	        list_of_dict = [{'name': 'Suraj'}, {'name': 'Aditya'}]

	        required_dict = find(list_of_dict, lambda d: d['name'] == 'Aditya')
	"""

	for entry in list_of_dict:
		if match_function(entry):
			return entry
	return None


def find_all(list_of_dict, match_function):
	"""Returns all matching dicts in a list of dicts.
	        Uses matching function to filter out the dicts

	Usage:
	        colored_shapes = [
	                {'color': 'red', 'shape': 'square'},
	                {'color': 'red', 'shape': 'circle'},
	                {'color': 'blue', 'shape': 'triangle'}
	        ]

	        red_shapes = find_all(colored_shapes, lambda d: d['color'] == 'red')
	"""
	found = []
	for entry in list_of_dict:
		if match_function(entry):
			found.append(entry)
	return found


def ljust_list(_list, length, fill_word=None):
	"""
	Similar to ljust but for list.

	Usage:
	        $ ljust_list([1, 2, 3], 5)
	        > [1, 2, 3, None, None]
	"""
	# make a copy to avoid mutation of passed list
	_list = list(_list)
	fill_length = length - len(_list)
	if fill_length > 0:
		_list.extend([fill_word] * fill_length)

	return _list


def html2text(html, strip_links=False, wrap=True):
	strip = ["a"] if strip_links else None
	return md(html, heading_style="ATX", strip=strip, wrap=wrap)
