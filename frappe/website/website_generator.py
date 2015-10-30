# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import now
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.website.utils import cleanup_page_name, get_home_page
from frappe.website.render import clear_cache
from frappe.modules import get_module_name
from frappe.website.router import get_page_route, get_route_info

class WebsiteGenerator(Document):
	website = frappe._dict(
		page_title_field = "name"
	)

	def autoname(self):
		if self.meta.autoname != "hash":
			self.name = self.get_page_name()
			append_number_if_name_exists(self)

	def onload(self):
		self.get("__onload").update({
			"is_website_generator": True,
			"website_route": self.get_route(),
			"published": self.website_published()
		})

	def validate(self):
		self.set_parent_website_route()

		if not self.page_name:
			self.page_name = self.make_page_name()

		if self.meta.get_field("page_name") and not self.get("__islocal"):
			current_route = self.get_route()
			current_page_name = self.page_name
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
		return cleanup_page_name(self.get(self.website.page_title_field or "name"))

	def before_rename(self, oldname, name, merge):
		self._local = self.get_route()
		self.clear_cache()

	def after_rename(self, olddn, newdn, merge):
		if getattr(self, "_local"):
			self.update_routes_of_descendants(self._local)
		self.clear_cache()

	def on_trash(self):
		self.clear_cache()

	def website_published(self):
		if self.website.condition_field:
			return self.get(self.website.condition_field) and True or False
		else:
			return True

	def set_parent_website_route(self):
		parent_website_route_field = self.website.parent_website_route_field
		if parent_website_route_field:
			field = self.meta.get_field(parent_website_route_field)
			parent = self.get(parent_website_route_field)
			if parent:
				parent_doc = frappe.get_doc(field.options, parent)
				if parent_doc.website_published():
					self.parent_website_route = parent_doc.get_route()
				else:
					self.parent_website_route = None

	def update_routes_of_descendants(self, old_route = None):
		if not self.is_new() and self.meta.get_field("parent_website_route"):
			if not old_route:
				old_route = frappe.get_doc(self.doctype, self.name).get_route()

			if old_route and old_route != self.get_route():
				# clear cache of old routes
				old_routes = frappe.get_all(self.doctype, filters={"parent_website_route": ("like", old_route + "%")})

				if old_routes:
					for like_old_route in old_routes:
						clear_cache(frappe.get_doc(self.doctype, like_old_route.name).get_route())

					frappe.db.sql("""update `tab{0}` set
						parent_website_route = replace(parent_website_route, %s, %s),
						modified = %s,
						modified_by = %s
						where parent_website_route like %s""".format(self.doctype),
						(old_route, self.get_route(), now(), frappe.session.user, old_route + "%"))

	def get_route_context(self):
		route = frappe._dict()
		route.update({
			"doc": self,
			"page_or_generator": "Generator",
			"ref_doctype":self.doctype,
			"idx": self.idx,
			"docname": self.name,
			"page_name": self.get_page_name(),
			"controller": get_module_name(self.doctype, self.meta.module),
		})

		route.update(self.website)

		if not route.page_title:
			route.page_title = self.get(self.website.page_title_field or "name")

		return route

	def get_parents(self, context):
		# already set
		if context.parents:
			return context.parents

		home_page = get_home_page()

		parents = []
		me = self
		while me:
			_parent_field = me.website.parent_website_route_field
			_parent_val = me.get(_parent_field) if _parent_field else None

			# if no parent and not home page, then parent is home page
			if not _parent_val and me.get_route() != home_page:
				parents.append(frappe._dict(name=home_page, title=get_route_info(home_page).title))
				break

			elif _parent_val:
				df = me.meta.get_field(_parent_field)
				if not df:
					break
				parent_doc = frappe.get_doc(df.options, _parent_val)

				if not parent_doc.website_published():
					break

				if parent_doc:
					parent_info = frappe._dict(name = parent_doc.get_route(),
						title= parent_doc.get(parent_doc.website.page_title_field or "name"))
				else:
					parent_info = frappe._dict(name=self.parent_website_route,
						title=self.parent_website_route.replace("_", " ").title())

				if parent_info.name in [p.name for p in parents]:
					raise frappe.ValidationError, "Recursion in parent link"

				parents.append(parent_info)
				me = parent_doc
			else:
				# parent route is a page e.g. "blog"
				if me.get("parent_website_route"):
					page_route = get_page_route(me.parent_website_route)
					if page_route:
						parents.append(frappe._dict(name = page_route.name,
							title=page_route.page_title))
				me = None

		parents.reverse()
		return parents

	def get_parent(self):
		parent_website_route_field = self.website.parent_website_route_field
		if parent_website_route_field:
			return self.get(parent_website_route_field)

	def get_children(self, context=None):
		children = []
		route = self.get_route()
		if route==get_home_page():
			children = frappe.db.sql("""select url as name, label as page_title
				from `tabTop Bar Item` where parentfield='sidebar_items'
			order by idx""", as_dict=True)
			route = ""

		if not children and self.meta.get_field("parent_website_route"):
			children = self.get_children_of(route)

			if not children and self.parent_website_route:
				children = self.get_children_of(self.parent_website_route)

		return children

	def get_children_of(self, route):
		"""Return list of children of given route, for generating index in Web Page"""

		condition = 'parent_website_route = %s'
		if route=="index" or not route:
			condition = 'ifnull(parent_website_route, "") = %s and name != "index"'
			route = ""

		children = frappe.db.sql("""select name, page_name,
			parent_website_route, {title_field} as title from `tab{doctype}`
			where {condition}
			order by {order_by}""".format(
				doctype = self.doctype,
				title_field = self.website.page_title_field or "name",
				order_by = self.website.order_by or "idx asc",
				condition = condition
			), route, as_dict=True)

		for c in children:
			c.name = make_route(c)

		return children

	def has_children(self, route):
		return frappe.db.sql('''select name from `tab{0}`
			where parent_website_route = %s limit 1'''.format(self.doctype), route)

	def get_next(self):
		if self.meta.get_field("parent_website_route") and self.parent_website_route:
			route = self.get_route()
			parent = frappe.get_doc(self.doctype, self.get_parent())
			siblings = parent.get_children()
			for i, r in enumerate(siblings):
				if i < len(siblings) - 1:
					if route==r.name:
						return siblings[i+1]

			return parent.get_next()
		else:
			return frappe._dict()

def make_route(doc):
	parent = doc.get("parent_website_route", "")
	return ((parent + "/") if parent else "") + doc.page_name


