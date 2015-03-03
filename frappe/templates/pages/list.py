# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.base_document import get_controller
from frappe.utils import cint
from frappe.website.render import resolve_path

no_cache = 1
no_sitemap = 1

def get_context(context):
	doctype = frappe.local.form_dict.doctype
	context.update(get_list_context(context, doctype) or {})

	context.doctype = doctype
	context.txt = frappe.local.form_dict.txt

	context.update(get(**frappe.local.form_dict))

	return context

def get_list_context(context, doctype):
	controller = get_controller(doctype)
	if hasattr(controller, "get_list_context"):
		return controller.get_list_context(context)

@frappe.whitelist(allow_guest=True)
def get(doctype, txt=None, limit_start=0, **kwargs):
	limit_start = cint(limit_start)
	limit_page_length = 20
	next_start = limit_start + limit_page_length

	filters = frappe._dict(kwargs)
	if filters.pathname:
		# resolve additional filters from path
		resolve_path(filters.pathname)
		for key, val in frappe.local.form_dict.items():
			if not (key in ("doctype", "txt", "limit_start") and key in filters):
				filters[key] = val

	controller = get_controller(doctype)
	meta = frappe.get_meta(doctype)
	list_context = frappe._dict(hasattr(controller, "get_list_context") and controller.get_list_context() or {})

	_get_list = list_context.get_list or get_list
	raw_result = _get_list(doctype=doctype, txt=txt, filters=filters,
		limit_start=limit_start, limit_page_length=limit_page_length)
	show_more = (_get_list(doctype=doctype, txt=txt, filters=filters,
		limit_start=next_start, limit_page_length=1)
		and True or False)

	result = []
	row_template = list_context.row_template or "templates/includes/list/row_template.html"
	for item in raw_result:
		item.doctype = doctype
		item.update(list_context)
		result.append(frappe.render_template(row_template,
			{ "doc": item, "meta": meta, "pathname": frappe.local.request.path.strip("/ ") },
			is_path=True))

	return {
		"result": result,
		"show_more": show_more,
		"next_start": next_start
	}

def get_list(doctype, txt, filters, limit_start, limit_page_length=20, ignore_permissions=False):
	meta = frappe.get_meta(doctype)
	if not filters:
		filters = []

	or_filters = []

	if txt:
		if meta.search_fields:
			for f in meta.get_search_fields():
				or_filters.append([doctype, f.strip(), "like", "%" + txt + "%"])
		else:
			filters.append([doctype, "name", "like", "%" + txt + "%"])

	return frappe.get_list(doctype, fields = ["*"],
		filters=filters, or_filters=or_filters, limit_start=limit_start,
		limit_page_length = limit_page_length, ignore_permissions=ignore_permissions)

