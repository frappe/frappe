# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.utils import to_markdown


@frappe.whitelist()
def update_web_block_property(page, section, type, key, value, table=None, rowid=None):
	section = int(section) - 1
	web_page = frappe.get_doc("Web Page", page)
	values = json.loads(web_page.page_blocks[section].web_template_values)

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
def get_section(section_type):
	pass
