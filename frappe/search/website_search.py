# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import os

from bs4 import BeautifulSoup
from whoosh.fields import ID, TEXT, Schema

import frappe
from frappe.search.full_text_search import FullTextSearch
from frappe.utils import set_request, update_progress_bar
from frappe.website.render import render_page

INDEX_NAME = "web_routes"

class WebsiteSearch(FullTextSearch):
	""" Wrapper for WebsiteSearch """

	def get_schema(self):
		return Schema(
			title=TEXT(stored=True), path=ID(stored=True), content=TEXT(stored=True)
		)

	def get_id(self):
		return "path"

	def get_items_to_index(self):
		"""Get all routes to be indexed, this includes the static pages
		in www/ and routes from published documents

		Returns:
			self (object): FullTextSearch Instance
		"""

		if getattr(self, "_items_to_index", False):
			return self._items_to_index

		routes = get_static_pages_from_all_apps() + slugs_with_web_view()

		self._items_to_index = []

		for i, route in enumerate(routes):
			update_progress_bar("Retrieving Routes", i, len(routes))
			self._items_to_index += [self.get_document_to_index(route)]

		print()

		return self.get_items_to_index()

	def get_document_to_index(self, route):
		"""Render a page and parse it using BeautifulSoup

		Args:
			path (str): route of the page to be parsed

		Returns:
			document (_dict): A dictionary with title, path and content
		"""
		frappe.set_user("Guest")
		frappe.local.no_cache = True

		try:
			set_request(method="GET", path=route)
			content = render_page(route)
			soup = BeautifulSoup(content, "html.parser")
			page_content = soup.find(class_="page_content")
			text_content = page_content.text if page_content else ""
			title = soup.title.text.strip() if soup.title else route

			return frappe._dict(title=title, content=text_content, path=route)
		except Exception:
			pass
		finally:
			frappe.set_user("Administrator")

	def parse_result(self, result):
		title_highlights = result.highlights("title")
		content_highlights = result.highlights("content")

		return frappe._dict(
			title=result["title"],
			path=result["path"],
			title_highlights=title_highlights,
			content_highlights=content_highlights,
		)


def slugs_with_web_view():
	all_routes = []
	filters = { "has_web_view": 1, "allow_guest_to_view": 1, "index_web_pages_for_search": 1}
	fields = ["name", "is_published_field"]
	doctype_with_web_views = frappe.get_all("DocType", filters=filters, fields=fields)

	for doctype in doctype_with_web_views:
		if doctype.is_published_field:
			routes = frappe.get_all(doctype.name, filters={doctype.is_published_field: 1}, fields="route")
			all_routes += [route.route for route in routes]

	return all_routes

def get_static_pages_from_all_apps():
	from glob import glob
	apps = frappe.get_installed_apps()

	routes_to_index = []
	for app in apps:
		path_to_index = frappe.get_app_path(app, 'www')

		files_to_index = glob(path_to_index + '/**/*.html', recursive=True)
		files_to_index.extend(glob(path_to_index + '/**/*.md', recursive=True))
		for file in files_to_index:
			route = os.path.relpath(file, path_to_index).split('.')[0]
			if route.endswith('index'):
				route = route.rsplit('index', 1)[0]
			routes_to_index.append(route)
	return routes_to_index

def update_index_for_path(path):
	ws = WebsiteSearch(INDEX_NAME)
	return ws.update_index_by_name(path)

def remove_document_from_index(path):
	ws = WebsiteSearch(INDEX_NAME)
	return ws.remove_document_from_index(path)

def build_index_for_all_routes():
	ws = WebsiteSearch(INDEX_NAME)
	return ws.build()
