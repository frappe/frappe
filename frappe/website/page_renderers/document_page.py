import frappe
from frappe.model.document import get_controller
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
		for doctype in get_doctypes_with_web_view():
			filters = dict(route=self.path)
			meta = frappe.get_meta(doctype)
			condition_field = self.get_condition_field(meta)

			if condition_field:
				filters[condition_field] = 1

			try:
				self.docname = frappe.db.get_value(doctype, filters, "name")
				if self.docname:
					self.doctype = doctype
					return True
			except Exception as e:
				if not frappe.db.is_missing_column(e):
					raise e

	def search_web_page_dynamic_routes(self):
		d = get_page_info_from_web_page_with_dynamic_routes(self.path)
		if d:
			self.doctype = "Web Page"
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
		self.doc = frappe.get_doc(self.doctype, self.docname)
		self.init_context()
		self.update_context()
		self.post_process_context()
		html = frappe.get_template(self.template_path).render(self.context)
		return html

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

	def get_condition_field(self, meta):
		condition_field = None
		if meta.is_published_field:
			condition_field = meta.is_published_field
		elif not meta.custom:
			controller = get_controller(meta.name)
			condition_field = controller.website.condition_field

		return condition_field
