# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
from typing import ClassVar

from bs4 import BeautifulSoup

import frappe
from frappe.search.sqlite_search import SQLiteSearch
from frappe.utils import md_to_html, set_request, update_progress_bar
from frappe.website.serve import get_response_content

INDEX_NAME = "web_routes"

# Synthetic doctype label used as the `doctype` for indexed routes. Website pages
# are not real documents, but SQLiteSearch validates `doctype`/`name` on every row.
ROUTE_DOCTYPE = "Website Route"


class WebsiteSearch(SQLiteSearch):
	"""Full text search over website routes, backed by SQLite FTS5.

	Unlike a regular :class:`SQLiteSearch` subclass, the website index is built from
	*rendered routes* (static ``www/`` pages + published web-view documents) rather
	than from doctype records, so document sourcing and the build loop are overridden.
	"""

	INDEX_NAME = f"{INDEX_NAME}.db"

	INDEX_SCHEMA: ClassVar = {
		"text_fields": ["title", "content"],
		"metadata_fields": ["path"],
	}

	# Routes are not sourced from doctype tables; the build loop is overridden below.
	INDEXABLE_DOCTYPES: ClassVar = {}

	def __init__(self, index_name=INDEX_NAME):
		# Preserve the legacy `WebsiteSearch(index_name)` signature while giving
		# SQLiteSearch a proper `.db` filename (needed for temp-db handling).
		db_name = index_name if index_name.endswith(".db") else f"{index_name}.db"
		super().__init__(db_name=db_name)

	def get_search_filters(self):
		"""No permission filters: only guest-visible routes are indexed in the first place."""
		return {}

	# --- Indexing -------------------------------------------------------------

	def build(self):
		"""Build search index for all website routes (legacy entrypoint)."""
		self.build_index()

	def build_index(self, batch_size=1000, is_continuation=False):
		"""Rebuild the website index from all routes, swapping it in atomically."""
		if not self.is_search_enabled():
			return

		documents = [doc for route_doc in self.get_items_to_index() if (doc := self._to_index_doc(route_doc))]

		original_db_path = self.db_path
		temp_db_path = self._get_db_path(is_temp=True)
		if os.path.exists(temp_db_path):
			os.unlink(temp_db_path)

		# Build into a temporary database so the live index stays queryable until swap.
		self.db_path = temp_db_path
		try:
			self._ensure_fts_table()
			self._index_documents(documents)
			self._build_vocabulary_incremental()
		finally:
			self.db_path = original_db_path

		if os.path.exists(temp_db_path):
			if os.path.exists(original_db_path):
				os.unlink(original_db_path)
			os.rename(temp_db_path, original_db_path)

	def update_index_by_name(self, doc_name):
		"""Render and (re)index a single route. Runs as a background job."""
		route_doc = self.get_document_to_index(doc_name)
		if route_doc:
			self.update_index(route_doc)

	def update_index(self, route_doc):
		"""Insert or replace a single route in the index."""
		document = self._to_index_doc(route_doc)
		if not document:
			return
		# `_index_documents` deletes any existing row with the same doc_id before insert.
		self._ensure_fts_table()
		self._index_documents([document])

	def remove_document_from_index(self, doc_name):
		"""Remove a route from the index by its path."""
		if not doc_name or not self.index_exists():
			return
		self.sql("DELETE FROM search_fts WHERE doc_id = ?", (doc_name,), commit=True)

	def _to_index_doc(self, route_doc):
		"""Map a rendered route ``_dict(title, content, path)`` to an FTS document.

		``id`` is set to the route path so the path doubles as the FTS ``doc_id``,
		making per-route update/remove straightforward.
		"""
		if not route_doc:
			return None
		path = route_doc.get("path")
		if not path:
			return None
		return {
			"id": path,
			"doctype": ROUTE_DOCTYPE,
			"name": path,
			"title": route_doc.get("title") or "",
			"content": route_doc.get("content") or "",
			"path": path,
		}

	# --- Searching ------------------------------------------------------------

	def search(self, text: str, scope: str | None = None, limit: int = 20) -> list[frappe._dict]:
		"""Search the website index.

		Returns a list of ``_dict(title, path, title_highlights, content_highlights)``
		to preserve the response shape consumed by the website search box.
		"""
		if not text or not self.index_exists():
			return []

		results = super().search(text).get("results", [])

		if scope:
			scopes = [scope] if isinstance(scope, str) else list(scope)
			results = [r for r in results if any((r.get("path") or "").startswith(s) for s in scopes)]

		output = []
		for result in results[:limit]:
			title_highlights = result.get("title") or ""
			output.append(
				frappe._dict(
					title=_strip_marks(title_highlights),
					path=result.get("path"),
					title_highlights=title_highlights,
					content_highlights=result.get("content") or "",
				)
			)
		return output

	# --- Document sourcing ----------------------------------------------------

	def get_items_to_index(self):
		"""Get all routes to be indexed: static pages in www/ and published web-view documents.

		Return:
		        list[frappe._dict]: dictionaries with title, content and path.
		"""

		if getattr(self, "_items_to_index", None) is not None:
			return self._items_to_index

		self._items_to_index = []

		routes = get_static_pages_from_all_apps() + slugs_with_web_view(self._items_to_index)

		for i, route in enumerate(routes):
			update_progress_bar("Retrieving Routes", i, len(routes))
			self._items_to_index += [self.get_document_to_index(route)]

		print()

		return self.get_items_to_index()

	def get_document_to_index(self, route: str) -> frappe._dict | None:
		"""Render a page and parse it using `BeautifulSoup`.

		Args:
		        route: route of the page to be parsed

		Return a dictionary with title, path and content.
		"""
		frappe.set_user("Guest")
		frappe.local.no_cache = True

		try:
			set_request(method="GET", path=route)
			content = get_response_content(route)
			soup = BeautifulSoup(content, "html.parser")
			page_content = soup.find(class_="page_content")
			text_content = page_content.text if page_content else ""
			title = soup.title.text.strip() if soup.title else route

			return frappe._dict(title=title, content=text_content, path=route)
		except Exception:
			pass
		finally:
			frappe.set_user("Administrator")


def _strip_marks(text: str) -> str:
	"""Strip the ``<mark>`` highlight tags FTS adds, to recover the plain title."""
	return text.replace("<mark>", "").replace("</mark>", "")


def slugs_with_web_view(_items_to_index):
	all_routes = []
	filters = {"has_web_view": 1, "allow_guest_to_view": 1, "index_web_pages_for_search": 1}
	fields = ["name", "is_published_field", "website_search_field"]
	doctype_with_web_views = frappe.get_all("DocType", filters=filters, fields=fields)

	for doctype in doctype_with_web_views:
		if doctype.is_published_field:
			fields = ["route", doctype.website_search_field]
			filters = {doctype.is_published_field: 1}
			if doctype.website_search_field:
				docs = frappe.get_all(doctype.name, filters=filters, fields=[*fields, "title"])
				for doc in docs:
					content = md_to_html(getattr(doc, doctype.website_search_field))
					soup = BeautifulSoup(content, "html.parser")
					text_content = soup.text if soup else ""
					_items_to_index += [frappe._dict(title=doc.title, content=text_content, path=doc.route)]
			else:
				docs = frappe.get_all(doctype.name, filters=filters, fields=fields)
				all_routes += [route.route for route in docs]

	return all_routes


def get_static_pages_from_all_apps():
	from glob import glob

	apps = frappe.get_installed_apps()

	routes_to_index = []
	for app in apps:
		path_to_index = frappe.get_app_path(app, "www")

		files_to_index = glob(path_to_index + "/**/*.html", recursive=True)
		files_to_index.extend(glob(path_to_index + "/**/*.md", recursive=True))
		for file in files_to_index:
			route = os.path.relpath(file, path_to_index).split(".", maxsplit=1)[0]
			if route.endswith("index"):
				route = route.rsplit("index", 1)[0]
			routes_to_index.append(route)
	return routes_to_index


def update_index_for_path(path):
	ws = WebsiteSearch(INDEX_NAME)
	return ws.update_index_by_name(path)


def remove_document_from_index(path):
	ws = WebsiteSearch(INDEX_NAME)
	return ws.remove_document_from_index(path)


def build_index_for_all_routes():
	from frappe.utils.synchronization import filelock

	with filelock("building_website_search"):
		ws = WebsiteSearch(INDEX_NAME)
		return ws.build()
