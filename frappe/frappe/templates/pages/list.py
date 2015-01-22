# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.modules import get_doc_path, load_doctype_module
from jinja2 import Template

no_cache = 1
no_sitemap = 1

def get_context(context):
	context.doctype = frappe.local.form_dict.doctype
	context.txt = frappe.local.form_dict.txt
	module = load_doctype_module(context.doctype)
	context.update(get_items(context.doctype, context.txt))
	return context

@frappe.whitelist(allow_guest=True)
def get_items(doctype, txt, limit_start=0):
	meta = frappe.get_meta(doctype)
	filters, or_filters = [], []
	out = frappe._dict()
	module = load_doctype_module(doctype)

	if txt:
		if meta.search_fields:
			for f in meta.get_search_fields():
				or_filters.append([doctype, f.strip(), "like", "%" + txt + "%"])
		else:
			filters.append([doctype, "name", "like", "%" + txt + "%"])


	out.raw_items = frappe.get_list(doctype, fields = ["*"],
		filters=filters, or_filters = or_filters, limit_start=limit_start,
		limit_page_length = 20)

	if hasattr(module, "get_list_item"):
		out["items"] = []
		for i in out.raw_items:
			i.doc = i
			out["items"].append(module.get_list_item(i))
	else:
		template = Template("""<div><a href="/{{ doctype }}/{{ doc.name }}" no-pjax>
			{{ doc[title_field] }}</a></div>""")

		out.items = [template.render(doc=i, doctype=doctype,
			title_field = meta.title_field or "name") for i in out.raw_items]

	out.meta = meta

	return out
