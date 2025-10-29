# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.modules import get_module_name
from frappe.search.website_search import remove_document_from_index, update_index_for_path
from frappe.website.utils import cleanup_page_name, clear_cache


class WebsiteGenerator(Document):
	website = frappe._dict()

	def __init__(self, *args, **kwargs):
		self.route = None
		super().__init__(*args, **kwargs)

	def get_website_properties(self, key=None, default=None):
		out = getattr(self, "_website", None) or getattr(self, "website", None) or {}
		if not isinstance(out, dict):
			# website may be a property too, so ignore
			out = {}
		if key:
			return out.get(key, default)
		else:
			return out

	def autoname(self):
		if not self.name and self.meta.autoname != "hash":
			self.name = self.scrubbed_title()

	def onload(self):
		self.get("__onload").update({"is_website_generator": True, "published": self.is_website_published()})

	def validate(self):
		self.set_route()

	def set_route(self):
		if self.is_website_published() and not self.route:
			self.route = self.make_route()

		if self.route:
			self.route = self.route.strip("/.")[:139]

	def make_route(self):
		"""Return the default route. If `route` is specified in DocType it will be route/title."""
		from_title = self.scrubbed_title()
		if self.meta.route:
			return self.meta.route + "/" + from_title
		else:
			return from_title

	def scrubbed_title(self):
		return self.scrub(self.get(self.get_title_field()))

	def get_title_field(self):
		"""return title field from website properties or meta.title_field"""
		title_field = self.get_website_properties("page_title_field")
		if not title_field:
			if self.meta.title_field:
				title_field = self.meta.title_field
			elif self.meta.has_field("title"):
				title_field = "title"
			else:
				title_field = "name"

		return title_field

	def clear_cache(self):
		super().clear_cache()
		clear_cache(self.route)

		frappe.db.after_commit.add(lambda: clear_cache(self.route))
		frappe.db.after_rollback.add(lambda: clear_cache(self.route))

	def scrub(self, text):
		return cleanup_page_name(text).replace("_", "-")

	def get_parents(self, context):
		"""Return breadcrumbs"""
		pass

	def on_update(self):
		self.send_indexing_request()
		self.remove_old_route_from_index()

	def on_change(self):
		# Update the index on change
		# On change is triggered last in the event lifecycle
		self.update_website_search_index()

	def on_trash(self):
		self.clear_cache()
		self.send_indexing_request("URL_DELETED")
		# On deleting the doc, remove the page from the web_routes index
		if self.allow_website_search_indexing():
			frappe.enqueue(remove_document_from_index, path=self.route, enqueue_after_commit=True)

	def is_website_published(self):
		"""Return true if published in website"""
		if condition_field := self.get_condition_field():
			return self.get(condition_field) or False
		else:
			return True

	def get_condition_field(self):
		condition_field = self.get_website_properties("condition_field")
		if not condition_field:
			if self.meta.is_published_field:
				condition_field = self.meta.is_published_field

		return condition_field

	def get_page_info(self):
		route = frappe._dict()
		route.update(
			{
				"doc": self,
				"page_or_generator": "Generator",
				"ref_doctype": self.doctype,
				"idx": self.idx,
				"docname": self.name,
				"controller": get_module_name(self.doctype, self.meta.module),
			}
		)

		route.update(self.get_website_properties())

		if not route.page_title:
			route.page_title = self.get(self.get_title_field())

		route.title = route.page_title

		return route

	def send_indexing_request(self, operation_type="URL_UPDATED"):
		"""Send indexing request on update/trash operation."""

		if (
			frappe.db.get_single_value("Website Settings", "enable_google_indexing")
			and self.is_website_published()
			and self.meta.allow_guest_to_view
		):
			url = frappe.utils.get_url(self.route)
			frappe.enqueue(
				"frappe.website.doctype.website_settings.google_indexing.publish_site",
				url=url,
				operation_type=operation_type,
			)

	# Change the field value in doctype
	# Override this method to disable indexing
	def allow_website_search_indexing(self):
		return self.meta.index_web_pages_for_search

	def remove_old_route_from_index(self):
		"""Remove page from the website index if the route has changed."""
		if self.allow_website_search_indexing() or frappe.in_test:
			return
		old_doc = self.get_doc_before_save()
		# Check if the route is changed
		if old_doc and old_doc.route != self.route:
			# Remove the route from index if the route has changed
			remove_document_from_index(old_doc.route)

	def update_website_search_index(self):
		"""
		Update the full test index executed on document change event.
		- remove document from index if document is unpublished
		- update index otherwise
		"""
		if not self.allow_website_search_indexing() or frappe.in_test:
			return

		if self.is_website_published():
			frappe.enqueue(update_index_for_path, path=self.route, enqueue_after_commit=True)
		elif self.route:
			# If the website is not published
			frappe.enqueue(remove_document_from_index, path=self.route, enqueue_after_commit=True)
