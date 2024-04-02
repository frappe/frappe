import frappe
from frappe.model.document import get_controller
from frappe.utils.caching import redis_cache
from frappe.website.page_renderers.base_template_page import BaseTemplatePage
from frappe.website.router import (
	get_doctypes_with_web_view,
	get_page_info_from_web_page_with_dynamic_routes,
)
from frappe.website.utils import cache_html


class DocumentPage(BaseTemplatePage):
	def can_render(self):
		"""
		Find a document with matching `route` from all doctypes with `has_web_view`=1
		"""
		if self.search_in_doctypes_with_web_view():
			return True

		if self.search_web_page_dynamic_routes():
			return True

		return False

	def search_in_doctypes_with_web_view(self):
		if document := _find_matching_document_webview(self.path):
			self.doctype, self.docname = document
			doc = frappe.get_cached_doc(self.doctype, self.docname)
			return doc.meta.allow_guest_to_view or doc.has_permission() or frappe.has_website_permission(doc)

	def search_web_page_dynamic_routes(self):
		d = get_page_info_from_web_page_with_dynamic_routes(self.path)
		if d:
			self.doctype = d.doctype
			self.docname = d.name
			return True
		else:
			return False

	def render(self):
		html = self.get_html()
		html = self.add_csrf_token(html)

		return self.build_response(html)

	@cache_html
	def get_html(self):
		self.doc = frappe.get_cached_doc(self.doctype, self.docname)
		self.init_context()
		self.update_context()
		self.post_process_context()
		return frappe.get_template(self.template_path).render(self.context)

	def update_context(self):
		self.context.doc = self.doc
		self.context.update(self.context.doc.as_dict())
		self.context.update(self.context.doc.get_page_info())

		self.template_path = self.context.template or self.template_path

		if not self.template_path:
			self.template_path = self.context.doc.meta.get_web_template()

		if hasattr(self.doc, "get_context"):
			ret = self.doc.get_context(self.context)

			if ret:
				self.context.update(ret)

		for prop in ("no_cache", "sitemap"):
			if prop not in self.context:
				self.context[prop] = getattr(self.doc, prop, False)

	@staticmethod
	def get_condition_field(meta):
		condition_field = None
		if meta.is_published_field:
			condition_field = meta.is_published_field
		elif not meta.custom:
			controller = get_controller(meta.name)
			condition_field = controller.website.condition_field

		return condition_field


@redis_cache(ttl=60 * 60)
def _find_matching_document_webview(route: str) -> tuple[str, str] | None:
	for doctype in get_doctypes_with_web_view():
		filters = dict(route=route)
		meta = frappe.get_meta(doctype)
		condition_field = DocumentPage.get_condition_field(meta)

		if condition_field:
			filters[condition_field] = 1

		try:
			docname = None
			if meta.is_virtual:
				if doclist := frappe.get_all(doctype, filters=filters, fields=["name"], limit=1):
					docname = doclist[0].get("name")
			else:
				docname = frappe.db.get_value(doctype, filters, "name")

			if docname:
				return (doctype, docname)
		except Exception as e:
			if not frappe.db.is_missing_column(e):
				raise e
