# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from optparse import Values

import frappe
from frappe.utils import to_markdown
from frappe.website.doctype.web_page.web_page import get_web_blocks_html


@frappe.whitelist()
def update_web_block_property(page, section, type, key, value, table=None, rowid=None):
	section = int(section) - 1
	web_page = frappe.get_doc("Web Page", page)
	values = json.loads(web_page.page_blocks[section].web_template_values or "{}")

	if type == "markdown":
		value = to_markdown(value)

	if table:
		values[table][int(rowid)][key] = value

	else:
		values[key] = value

	web_page.page_blocks[section].web_template_values = json.dumps(values)
	web_page.save()


@frappe.whitelist()
def update_section_idx(page, new_order):
	web_page = frappe.get_doc("Web Page", page)
	new_order = json.loads(new_order)

	section_map = {}
	for d in web_page.page_blocks:
		section_map[d.name] = d

	web_page.page_blocks = []
	for idx, name in enumerate(new_order):
		d = section_map[name]
		d.idx = idx + 1
		web_page.page_blocks.append(d)

	web_page.save()


@frappe.whitelist()
def set_section_property(page, section_id, property, value):
	web_page = frappe.get_doc("Web Page", page)
	section = web_page.page_blocks[int(section_id) - 1]
	section.set(property, value)
	web_page.save()


@frappe.whitelist()
def get_section(page, section_type):
	web_page = frappe.get_doc("Web Page", page)
	web_template_values = values = {}

	web_template = frappe.get_doc("Web Template", section_type)
	for f in web_template.fields:
		if f.fieldtype in ("Data", "Small Text"):
			values[f.fieldname] = f.default or f.label

		elif f.fieldtype == "URL":
			values[f.fieldname] = f.default or "https://"

		elif f.fieldtype == "Select":
			values[f.fieldname] = f.default or f.options.split("\n")[0]

		elif f.fieldtype == "Table Break":
			values = {}
			web_template_values[f.fieldname] = [values]

	d = web_page.append(
		"page_blocks",
		dict(
			web_template=section_type,
			add_container=1,
			add_top_padding=1,
			add_bottom_padding=1,
			web_template_values=json.dumps(web_template_values),
		),
	)

	web_page.save()

	return get_web_blocks_html([d]).html


@frappe.whitelist()
def remove_section(page, section_id):
	web_page = frappe.get_doc("Web Page", page)
	web_page.page_blocks.remove(web_page.page_blocks[int(section_id) - 1])
	web_page.save()


@frappe.whitelist()
def add_item(page, section_id, table):
	web_page = frappe.get_doc("Web Page", page)
	section = web_page.page_blocks[int(section_id) - 1]
	values = json.loads(section.web_template_values or "{}")

	# duplicate last element of the table
	values[table].append(values[table][-1].copy())

	section.web_template_values = json.dumps(values)
	web_page.save()

	return get_web_blocks_html([section]).html


@frappe.whitelist()
def get_values(page, section_id):
	web_page = frappe.get_doc("Web Page", page)
	return json.loads(web_page.page_blocks[int(section_id) - 1].web_template_values)


@frappe.whitelist()
def set_values(page, section_id, web_template_values):
	web_page = frappe.get_doc("Web Page", page)
	section = web_page.page_blocks[int(section_id) - 1]
	section.web_template_values = web_template_values
	web_page.save()

	return get_web_blocks_html([section]).html
