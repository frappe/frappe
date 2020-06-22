# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from whoosh.index import create_in, open_dir
from whoosh.fields import TEXT, ID, Schema
from whoosh.qparser import MultifieldParser, FieldsPlugin, WildcardPlugin
from whoosh.query import Prefix
from bs4 import BeautifulSoup
from frappe.website.render import render_page
from frappe.utils import set_request, cint
import os

class FullTextSearch:
	""" Frappe Wrapper for Whoosh """

	def __init__(self, index_name):
		self.index_name = index_name
		self.index_path = get_index_path(index_name)
		self.schema = Schema(
			title=TEXT(stored=True), path=ID(stored=True), content=TEXT(stored=True)
		)

	def get_routes_to_index(self):
		"""Get all routes to be indexed, this includes the static pages
		in www/ and routes from published documents

		Returns:
			self (object): FullTextSearch Instance
		"""
		routes = get_static_pages_from_all_apps()
		routes += get_doctype_routes_with_web_view()
		return routes

	def build(self):
		"""	Build search index for all web routes """

		print("Building search index for all web routes...")
		routes = self.get_routes_to_index()
		self.documents = [self.get_document_to_index(route) for route in routes]
		self.build_index()

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

			frappe.set_user("Administrator")

			return frappe._dict(title=title, content=text_content, path=route)
		except (
			frappe.PermissionError,
			frappe.DoesNotExistError,
			frappe.ValidationError,
			Exception,
		):
			pass

	def update_index_for_path(self, path):
		"""Wraps `update_index` method, gets the document from path
		and updates the index. This function changes the current user
		and should only be run as administrator or in a background job.

		Args:
			self (object): FullTextSearch Instance
			path (str): route of the page to be updated 
		"""
		document = self.get_document_to_index(path)
		self.update_index(document)

	def update_index(self, document):
		"""Update search index for a document

		Args:
			self (object): FullTextSearch Instance
			document (_dict): A dictionary with title, path and content
		"""
		ix = open_dir(self.index_path)

		with ix.searcher() as searcher:
			writer = ix.writer()
			writer.delete_by_term('path', document.path)
			writer.add_document(
				title=document.title, path=document.path, content=document.content
			)
			writer.commit(optimize=True)

	def remove_document_from_index(self, path):
		"""Remove document from search index

		Args:
			self (object): FullTextSearch Instance
			path (str): route of the page to be removed 
		"""
		ix = open_dir(self.index_path)
		with ix.searcher() as searcher:
			writer = ix.writer()
			writer.delete_by_term('path', path)
			writer.commit(optimize=True)

	
	def build_index(self):
		"""Build index for all parsed documents"""
		ix = create_in(self.index_path, self.schema)
		writer = ix.writer()

		for document in self.documents:
			if document:
				writer.add_document(
					title=document.title, path=document.path, content=document.content
				)

		writer.commit(optimize=True)

	def search(self, text, scope=None, limit=20):
		"""Search from the current index

		Args:
			text (str): String to search for
			scope (str, optional): Scope to limit the search. Defaults to None.
			limit (int, optional): Limit number of search results. Defaults to 20.

		Returns:
			[List(_dict)]: Search results
		"""
		ix = open_dir(self.index_path)

		results = None
		out = []
		
		with ix.searcher() as searcher:
			parser = MultifieldParser(["title", "content"], ix.schema)
			parser.remove_plugin_class(FieldsPlugin)
			parser.remove_plugin_class(WildcardPlugin)
			query = parser.parse(text)

			filter_scoped = None
			if scope:
				filter_scoped = Prefix("path", scope)
			results = searcher.search(query, limit=limit, filter=filter_scoped)

			for r in results:
				title_highlights = r.highlights("title")
				content_highlights = r.highlights("content")
				out.append(
					frappe._dict(
						title=r["title"],
						path=r["path"],
						title_highlights=title_highlights,
						content_highlights=content_highlights,
					)
				)

		return out


def get_doctype_routes_with_web_view():
	all_routes = []
	filters = { "has_web_view": 1, "allow_guest_to_view": 1 }
	fields = ["name", "is_published_field"]
	doctype_with_web_views = frappe.get_all("DocType", filters=filters, fields=fields)

	for doctype in doctype_with_web_views:
		if doctype.is_published_field:
			routes = frappe.get_all(doctype.name, filters={doctype.is_published_field: 1}, fields="route")
			all_routes += [route.route for route in routes]

	return all_routes

def get_static_pages_from_all_apps():
	apps = frappe.get_installed_apps()

	routes_to_index = []
	for app in apps:
		base = frappe.get_app_path(app, 'www')
		path_to_index = frappe.get_app_path(app, 'www')

		for dirpath, _, filenames in os.walk(path_to_index, topdown=True):
			for f in filenames:
				if f.endswith(('.md', '.html')):
					filepath = os.path.join(dirpath, f)

					route = os.path.relpath(filepath, base)
					route = route.split('.')[0]

					if route.endswith('index'):
						route = route.rsplit('index', 1)[0]

					routes_to_index.append(route)

	return routes_to_index

@frappe.whitelist(allow_guest=True)
def web_search(index_name, query, scope=None, limit=20):
	limit = cint(limit)
	fts = FullTextSearch(index_name)
	return fts.search(query, scope, limit)

def get_index_path(index_name):
	return frappe.get_site_path("indexes", index_name)

def update_index_for_path(index_name, path):
	fts = FullTextSearch(index_name)
	return fts.update_index_for_path(path)

def remove_document_from_index(index_name, path):
	fts = FullTextSearch(index_name)
	return fts.remove_document_from_index(path)

def build_index_for_all_routes(index_name):
	fts = FullTextSearch(index_name)
	return fts.build()