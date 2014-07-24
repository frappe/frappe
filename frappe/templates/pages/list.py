# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.modules import get_doc_path
from jinja2 import Environment, Template, FileSystemLoader

no_cache = 1
no_sitemap = 1

def get_context(context):
	context.type = frappe.local.form_dict.type
	context.txt = frappe.local.form_dict.txt
	context.update(get_items(context.type, context.txt))
	return context

@frappe.whitelist(allow_guest=True)
def get_items(type, txt, limit_start=0):
	meta = frappe.get_meta(type)
	filters, or_filters = [], []
	out = frappe._dict()

	if txt:
		if meta.search_fields:
			for f in meta.get_search_fields():
				or_filters.append([type, f.strip(), "like", "%" + txt + "%"])
		else:
			filters.append([type, "name", "like", "%" + txt + "%"])


	out.raw_items = frappe.get_list(type, fields = ["*"],
		filters=filters, or_filters = or_filters, limit_start=limit_start,
		limit_page_length = 20)
	template_path = os.path.join(get_doc_path(meta.module, "DocType", meta.name), "list_item.html")

	if os.path.exists(template_path):
		env = Environment(loader = FileSystemLoader("/"))
		#template_path = os.path.relpath(template_path)
		template = env.get_template(template_path)
	else:
		template = Template("""<div><a href="/{{ doctype }}/{{ doc.name }}" no-pjax>
			{{ doc[title_field] }}</a></div>""")

	out.items = [template.render(doc=i, doctype=type,
		title_field = meta.title_field or "name") for i in out.raw_items]

	out.meta = meta

	return out
