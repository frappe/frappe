# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, quoted
from frappe.website.render import resolve_path
from frappe import _

no_cache = 1
no_sitemap = 1

def get_context(context):
	"""Returns context for a list standard list page.
	Will also update `get_list_context` from the doctype module file"""
	doctype = frappe.local.form_dict.doctype
	context.parents = [{"route":"me", "title":_("My Account")}]
	context.update(get_list_context(context, doctype) or {})
	context.doctype = doctype
	context.txt = frappe.local.form_dict.txt
	context.update(get(**frappe.local.form_dict))

@frappe.whitelist(allow_guest=True)
def get(doctype, txt=None, limit_start=0, limit=20, **kwargs):
	"""Returns processed HTML page for a standard listing."""
	limit_start = cint(limit_start)
	limit_page_length = limit
	next_start = limit_start + limit_page_length

	if not txt and frappe.form_dict.search:
		txt = frappe.form_dict.search
		del frappe.form_dict['search']

	filters = prepare_filters(doctype, kwargs)
	meta = frappe.get_meta(doctype)
	list_context = get_list_context(frappe._dict(), doctype)

	if list_context.filters:
		filters.update(list_context.filters)

	_get_list = list_context.get_list or get_list

	raw_result = _get_list(doctype=doctype, txt=txt, filters=filters,
		limit_start=limit_start, limit_page_length=limit_page_length)

	if not raw_result: return {"result": []}

	show_more = (_get_list(doctype=doctype, txt=txt, filters=filters,
		limit_start=next_start, limit_page_length=1) and True or False)

	if txt:
		list_context.default_subtitle = _('Filtered by "{0}"').format(txt)

	result = []
	row_template = list_context.row_template or "templates/includes/list/row_template.html"
	for doc in raw_result:
		doc.doctype = doctype
		new_context = frappe._dict(doc=doc, meta=meta)
		new_context.doc = frappe.get_doc(doc)

		if not frappe.flags.in_test:
			new_context["pathname"] = frappe.local.request.path.strip("/ ")
		new_context.update(list_context)
		set_route(new_context)
		rendered_row = frappe.render_template(row_template, new_context, is_path=True)
		result.append(rendered_row)

	return {
		"result": result,
		"show_more": show_more,
		"next_start": next_start
	}

def set_route(context):
	'''Set link for the list item'''
	if context.is_web_form:
		context.route = "{0}?name={1}".format(context.pathname, quoted(context.doc.name))
	elif context.doc and getattr(context.doc, 'route', None):
		context.route = context.doc.route
	else:
		context.route = "{0}/{1}".format(context.pathname or quoted(context.doc.doctype),
			quoted(context.doc.name))

def prepare_filters(doctype, kwargs):
	filters = frappe._dict(kwargs)
	meta = frappe.get_meta(doctype)

	if filters.pathname:
		# resolve additional filters from path
		resolve_path(filters.pathname)
		for key, val in frappe.local.form_dict.items():
			if key not in filters:
				filters[key] = val

	# filter the filters to include valid fields only
	for fieldname, val in filters.items():
		if not meta.has_field(fieldname):
			del filters[fieldname]

	if "is_web_form" in filters:
		del filters["is_web_form"]

	return filters

def get_list_context(context, doctype):
	from frappe.modules import load_doctype_module
	from frappe.website.doctype.web_form.web_form import get_web_form_list

	list_context = frappe._dict()
	module = load_doctype_module(doctype)
	if hasattr(module, "get_list_context"):
		list_context = frappe._dict(module.get_list_context(context) or {})

	# is web form
	if cint(frappe.local.form_dict.is_web_form):
		list_context.is_web_form = 1
		if not list_context.get("get_list"):
			list_context.get_list = get_web_form_list

	return list_context

def get_list(doctype, txt, filters, limit_start, limit_page_length=20, ignore_permissions=False,
	fields=None, order_by=None):
	meta = frappe.get_meta(doctype)
	if not filters:
		filters = []

	if not fields:
		fields = "distinct *"

	or_filters = []

	if txt:
		if meta.search_fields:
			for f in meta.get_search_fields():
				if f == 'name' or meta.get_field(f).fieldtype in ('Data', 'Text', 'Small Text', 'Text Editor'):
					or_filters.append([doctype, f, "like", "%" + txt + "%"])
		else:
			if isinstance(filters, dict):
				filters["name"] = ("like", "%" + txt + "%")
			else:
				filters.append([doctype, "name", "like", "%" + txt + "%"])

	return frappe.get_list(doctype, fields = fields,
		filters=filters, or_filters=or_filters, limit_start=limit_start,
		limit_page_length = limit_page_length, ignore_permissions=ignore_permissions,
		order_by=order_by)

