# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import now
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.website.utils import cleanup_page_name, get_home_page
from frappe.website.render import clear_cache
from frappe.modules import get_module_name
from frappe.website.router import get_page_route

class WebsiteGenerator(Document):
	page_title_field = "name"
	def autoname(self):
		if self.meta.autoname != "hash":
			self.name = self.get_page_name()
			append_number_if_name_exists(self)

	def onload(self):
		self.get("__onload").website_route = self.get_route()

	def validate(self):
		self.set_parent_website_route()

		if self.meta.get_field("page_name") and not self.get("__islocal"):
			current_route = self.get_route()
			current_page_name = self.page_name

			self.page_name = self.make_page_name()

			# page name changed, rename everything
			if current_page_name and current_page_name != self.page_name:
				self.update_routes_of_descendants(current_route)

	def on_update(self):
		clear_cache(self.get_route())
		if getattr(self, "save_versions", False):
			frappe.add_version(self)

	def get_route(self, doc = None):
		self.get_page_name()
		return make_route(self)

	def clear_cache(self):
		clear_cache(self.get_route())

	def get_page_name(self):
		return self.get_or_make_page_name()

	def get_or_make_page_name(self):
		page_name = self.get("page_name")
		if not page_name:
			page_name = self.make_page_name()
			self.set("page_name", page_name)

		return page_name

	def make_page_name(self):
		return cleanup_page_name(self.get(self.page_title_field))

	def before_rename(self, oldname, name, merge):
		self._local = self.get_route()
		self.clear_cache()

	def after_rename(self, olddn, newdn, merge):
		if getattr(self, "_local"):
			self.update_routes_of_descendants(self._local)
		self.clear_cache()

	def on_trash(self):
		clear_cache(self.get_route())

	def website_published(self):
		if hasattr(self, "condition_field"):
			return self.get(self.condition_field) and True or False
		else:
			return True

	def set_parent_website_route(self):
		if hasattr(self, "parent_website_route_field"):
			field = self.meta.get_field(self.parent_website_route_field)
			parent = self.get(self.parent_website_route_field)
			if parent:
				self.parent_website_route = frappe.get_doc(field.options,
					parent).get_route()

	def update_routes_of_descendants(self, old_route = None):
		if not self.is_new() and self.meta.get_field("parent_website_route"):
			if not old_route:
				old_route = frappe.get_doc(self.doctype, self.name).get_route()

			if old_route and old_route != self.get_route():
				# clear cache of old routes
				old_routes = frappe.get_all(self.doctype, fields=["parent_website_route", "page_name"],
					filters={"parent_website_route": ("like", old_route + "%")})

				if old_routes:
					for old_route in old_routes:
						clear_cache(make_route(old_route))

					frappe.db.sql("""update `tab{0}` set
						parent_website_route = replace(parent_website_route, %s, %s),
						modified = %s
						modified_by = %s
						where parent_website_route like %s""".format(self.doctype),
						(old_route, self.get_route(), now(), frappe.session.user, old_route + "%"))

	def get_website_route(self):
		route = frappe._dict()
		route.update({
			"doc": self,
			"page_or_generator": "Generator",
			"ref_doctype":self.doctype,
			"idx": self.idx,
			"docname": self.name,
			"page_name": self.get_page_name(),
			"controller": get_module_name(self.doctype, self.meta.module),
			"template": self.template,
			"parent_website_route": self.get("parent_website_route", ""),
			"page_title": getattr(self, "page_title", None) or self.get(self.page_title_field)
		})

		self.update_permissions(route)

		return route

	def update_permissions(self, route):
		if self.meta.get_field("public_read"):
			route.public_read = self.public_read
			route.public_write = self.public_write
		else:
			route.public_read = 1

	def get_parents(self, context):
		parents = []
		parent = self
		while parent:
			_parent_field = getattr(parent, "parent_website_route_field", None)
			_parent_val = parent.get(_parent_field) if _parent_field else None
			if _parent_val:
				df = parent.meta.get_field(_parent_field)
				parent_doc = frappe.get_doc(df.options, _parent_val)

				if not parent_doc.website_published():
					break

				if parent_doc:
					parent_info = frappe._dict(name = parent_doc.get_route(),
						title= parent_doc.get(getattr(parent_doc, "page_title_field", "name")))
				else:
					parent_info = frappe._dict(name=self.parent_website_route,
						title=self.parent_website_route.replace("_", " ").title())

				if parent_info.name in [p.name for p in parents]:
					raise frappe.ValidationError, "Recursion in parent link"

				parents.append(parent_info)
				parent = parent_doc
			else:
				# parent route is a page e.g. "blog"
				if parent.get("parent_website_route"):
					page_route = get_page_route(parent.parent_website_route)
					if page_route:
						parents.append(frappe._dict(name = page_route.name,
							title=page_route.page_title))
				parent = None

		parents.reverse()
		return parents

	def get_parent(self):
		if hasattr(self, "parent_website_route_field"):
			return self.get(self.parent_website_route_field)

	def get_children(self):
		if self.get_route()==get_home_page():
			return frappe.db.sql("""select url as name, label as page_title,
			1 as public_read from `tabTop Bar Item` where parentfield='sidebar_items'
			order by idx""", as_dict=True)

		if self.meta.get_field("parent_website_route"):
			children = self.get_children_of(self.get_route())

			if not children and self.parent_website_route:
				children = self.get_children_of(self.parent_website_route)

			return children
		else:
			return []

	def get_children_of(self, route):
		children = frappe.db.sql("""select name, page_name,
			parent_website_route, {title_field} as title from `tab{doctype}`
			where ifnull(parent_website_route,'')=%s
			order by {order_by}""".format(
				doctype = self.doctype,
				title_field = getattr(self, "page_title_field", "name"),
				order_by = getattr(self, "order_by", "idx asc")),
				route, as_dict=True)

		for c in children:
			c.name = make_route(c)

		return children

	def get_next(self):
		if self.meta.get_field("parent_website_route") and self.parent_website_route:
			route = self.get_route()
			siblings = frappe.get_doc(self.doctype, self.get_parent()).get_children()
			for i, r in enumerate(siblings):
				if i < len(siblings) - 1:
					if route==r.name:
						return siblings[i+1]
		else:
			return frappe._dict()

def make_route(doc):
	parent = doc.get("parent_website_route", "")
	return ((parent + "/") if parent else "") + doc.page_name


