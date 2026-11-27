# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib.parse import urlparse

import frappe

NON_WEB_URL_SCHEMES = ("cid", "data", "javascript", "mailto", "tel")


def get_parent_doc(doc):
	"""Return document of `reference_doctype`, `reference_doctype`."""
	if not getattr(doc, "parent_doc", None):
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
	"""Return a dict in a list of dicts on matching the conditions provided in match function.

	Usage:
	        list_of_dict = [{'name': 'Suraj'}, {'name': 'Aditya'}]

	        required_dict = find(list_of_dict, lambda d: d['name'] == 'Aditya')
	"""

	for entry in list_of_dict:
		if match_function(entry):
			return entry
	return None


def find_all(list_of_dict, match_function):
	"""Return all matching dicts in a list of dicts. Uses matching function to filter out the dicts.

	Usage:
	        colored_shapes = [
	                {'color': 'red', 'shape': 'square'},
	                {'color': 'red', 'shape': 'circle'},
	                {'color': 'blue', 'shape': 'triangle'}
	        ]

	        red_shapes = find_all(colored_shapes, lambda d: d['color'] == 'red')
	"""
	return [entry for entry in list_of_dict if match_function(entry)]


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


def html2text(html: str, strip_links=False, wrap=True) -> str:
	"""Return the given `html` as markdown text."""
	from markdownify import markdownify as md

	strip = ["a"] if strip_links else None
	return md(html, heading_style="ATX", strip=strip, wrap=wrap)


def html_to_plain_text(html: str, exclude: str | None = None) -> str:
	"""Return the given `html` as plain text, with the URLs of its links and images.

	`exclude` is a CSS selector of elements to leave out.
	"""

	if not html:
		return ""

	from bs4 import BeautifulSoup

	soup = BeautifulSoup(html, "html.parser")

	for element in soup(["head", "script", "style"]):
		element.decompose()

	if exclude:
		for element in soup.select(exclude):
			element.decompose()

	for image in soup.find_all("img", src=_is_web_url):
		image.replace_with(_join_label_and_url(image.get("alt", ""), image["src"]))

	for link in soup.find_all("a", href=_is_web_url):
		link.replace_with(_join_label_and_url(link.get_text(" ", strip=True), link["href"]))

	soup.smooth()

	# Introduce explicit newlines for block-level elements while keeping inline content on the same line.
	for br in soup.find_all("br"):
		br.replace_with("\n")

	for block in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
		block.append("\n")

	# Use a space separator between text nodes so inline tags don't break lines
	text = soup.get_text(separator=" ")

	lines = [line.strip() for line in text.splitlines()]
	cleaned = []
	previous_blank = False

	for line in lines:
		if line:
			cleaned.append(line)
			previous_blank = False
		else:
			if not previous_blank:
				cleaned.append("")
			previous_blank = True

	return "\n".join(cleaned).strip()


def _is_web_url(url: str | None) -> bool:
	return bool(url) and not url.startswith("#") and urlparse(url).scheme not in NON_WEB_URL_SCHEMES


def _join_label_and_url(label: str, url: str) -> str:
	return f"{label} ({url})" if label and label != url else url
