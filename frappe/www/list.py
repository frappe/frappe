# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.model.document import get_controller
from frappe.utils import cint
from frappe.website.path_resolver import resolve_path

no_cache = 1


@frappe.whitelist()
def get_list_data(
	doctype: str,
	txt: str | None = None,
	limit_start: int = 0,
	fields: list | None = None,
	cmd: str | None = None,
	limit: int = 20,
	web_form_name: str | None = None,
	**kwargs,
):
	"""Return processed HTML page for a standard listing."""
	limit_start = cint(limit_start)

	if frappe.is_table(doctype):
		frappe.throw(_("Child DocTypes are not allowed"), title=_("Invalid DocType"))

	if not txt and frappe.form_dict.search:
		txt = frappe.form_dict.search
		del frappe.form_dict["search"]

	controller = get_controller(doctype)
	meta = frappe.get_meta(doctype)

	filters = prepare_filters(doctype, controller, kwargs)
	list_context = get_list_context(frappe._dict(), doctype, web_form_name)
	list_context.title_field = getattr(controller, "website", {}).get(
		"page_title_field", meta.title_field or "name"
	)

	if list_context.filters:
		filters.update(list_context.filters)

	_get_list = list_context.get_list or get_list

	kwargs = dict(
		doctype=doctype,
		txt=txt,
		filters=filters,
		limit_start=limit_start,
		limit_page_length=limit,
		order_by=list_context.order_by or "creation desc",
	)

	# allow guest if flag is set
	if not list_context.get_list and (list_context.allow_guest or meta.allow_guest_to_view):
		kwargs["ignore_permissions"] = True

	raw_result = _get_list(**kwargs)

	# list context to be used if called as rendered list
	frappe.flags.list_context = list_context

	return raw_result


def prepare_filters(doctype, controller, kwargs):
	for key in kwargs.keys():
		try:
			kwargs[key] = json.loads(kwargs[key])
		except ValueError:
			pass
	filters = frappe._dict(kwargs)
	meta = frappe.get_meta(doctype)

	if hasattr(controller, "website") and controller.website.get("condition_field"):
		filters[controller.website["condition_field"]] = 1
	elif meta.is_published_field:
		filters[meta.is_published_field] = 1

	if filters.pathname:
		# resolve additional filters from path
		resolve_path(filters.pathname)
		for key, val in frappe.local.form_dict.items():
			if key not in filters and key != "flags":
				filters[key] = val

	# filter the filters to include valid fields only
	from frappe.model.meta import DEFAULT_FIELD_LABELS

	for fieldname in list(filters.keys()):
		# add a check for default fields, as they are not present in meta.fields
		if not meta.has_field(fieldname) and fieldname not in DEFAULT_FIELD_LABELS.keys():
			del filters[fieldname]

	return filters


def get_list_context(context, doctype, web_form_name=None):
	from frappe.modules import load_doctype_module
	from frappe.website.doctype.web_form.web_form import get_web_form_module

	list_context = context or frappe._dict()
	meta = frappe.get_meta(doctype)

	def update_context_from_module(module, list_context):
		# call the user defined method `get_list_context`
		# from the python module
		if hasattr(module, "get_list_context"):
			out = frappe._dict(module.get_list_context(list_context) or {})
			if out:
				list_context = out
		return list_context

	# get context from the doctype module
	if not meta.custom:
		# custom doctypes don't have modules
		module = load_doctype_module(doctype)
		list_context = update_context_from_module(module, list_context)

	# get context for custom webform
	if meta.custom and web_form_name:
		webform_list_contexts = frappe.get_hooks("webform_list_context")
		if webform_list_contexts and not frappe.get_doc("Module Def", meta.module).custom:
			out = frappe._dict(frappe.get_attr(webform_list_contexts[0])(meta.module) or {})
			if out:
				list_context = out

	# get context from web form module
	if web_form_name:
		web_form = frappe.get_lazy_doc("Web Form", web_form_name)
		list_context = update_context_from_module(get_web_form_module(web_form), list_context)

	# get path from '/templates/' folder of the doctype
	if not meta.custom and not list_context.row_template:
		list_context.row_template = meta.get_row_template()

	if not meta.custom and not list_context.list_template:
		list_context.template = meta.get_list_template()

	return list_context


def get_list(
	doctype,
	txt,
	filters,
	limit_start,
	limit_page_length=20,
	ignore_permissions=False,
	fields=None,
	order_by=None,
	or_filters=None,
):
	meta = frappe.get_meta(doctype)
	if not filters:
		filters = []

	distinct = False
	if not fields:
		fields = "*"
		distinct = True

	if or_filters is None:
		or_filters = []

	if txt:
		if meta.search_fields:
			or_filters.extend(
				[doctype, f, "like", "%" + txt + "%"]
				for f in meta.get_search_fields()
				if f == "name" or meta.get_field(f).fieldtype in ("Data", "Text", "Small Text", "Text Editor")
			)
		else:
			if isinstance(filters, dict):
				filters["name"] = ("like", "%" + txt + "%")
			else:
				filters.append([doctype, "name", "like", "%" + txt + "%"])

	return frappe.get_list(
		doctype,
		fields=fields,
		filters=filters,
		or_filters=or_filters,
		limit_start=limit_start,
		limit_page_length=limit_page_length,
		ignore_permissions=ignore_permissions,
		order_by=order_by,
		distinct=distinct,
	)
