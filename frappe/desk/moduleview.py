# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk import reportview
from frappe.utils import cint
from frappe import _

@frappe.whitelist()
def get(module):
	"""Returns data (sections, list of reports, counts) to render module view in desk:
	`/desk/#Module/[name]`."""
	data = get_data(module)

	out = {
		"data": data,
		"item_count": {
			data[0]["label"]: get_section_count(section=data[0])
		},
		"reports": get_report_list(module)
	}

	return out

def get_data(module):
	"""Get module data for the module view `desk/#Module/[name]`"""
	doctype_info = get_doctype_info(module)
	data = build_config_from_file(module)

	if not data:
		data = build_standard_config(module, doctype_info)
	else:
		add_custom_doctypes(data, doctype_info)

	data = combine_common_sections(data)

	return data

def build_config_from_file(module):
	"""Build module info from `app/config/desktop.py` files."""
	data = []
	module = frappe.scrub(module)

	for app in frappe.get_installed_apps():
		try:
			data += get_config(app, module)
		except ImportError:
			pass

	return data

def build_standard_config(module, doctype_info):
	"""Build standard module data from DocTypes."""
	if not frappe.db.get_value("Module Def", module):
		frappe.throw(_("Module Not Found"))

	data = []

	add_section(data, _("Documents"), "icon-star",
		[d for d in doctype_info if in_document_section(d)])

	add_section(data, _("Setup"), "icon-cog",
		[d for d in doctype_info if not in_document_section(d)])

	add_section(data, _("Standard Reports"), "icon-list",
		get_report_list(module, is_standard="Yes"))

	return data

def add_section(data, label, icon, items):
	"""Adds a section to the module data."""
	if not items: return
	data.append({
		"label": label,
		"icon": icon,
		"items": items
	})


def add_custom_doctypes(data, doctype_info):
	"""Adds Custom DocTypes to modules setup via `config/desktop.py`."""
	add_section(data, _("Documents"), "icon-star",
		[d for d in doctype_info if (d.custom and in_document_section(d))])

	add_section(data, _("Setup"), "icon-cog",
		[d for d in doctype_info if (d.custom and not in_document_section(d))])

def in_document_section(d):
	"""Returns True if `document_type` property is one of `Master`, `Transaction` or not set."""
	return d.document_type in ("Transaction", "Master", "")

def get_doctype_info(module):
	"""Returns list of non child DocTypes for given module."""
	doctype_info = frappe.db.sql("""select "doctype" as type, name, description,
		ifnull(document_type, "") as document_type, ifnull(custom, 0) as custom,
		ifnull(issingle, 0) as issingle
		from `tabDocType` where module=%s and ifnull(istable, 0)=0
		order by ifnull(custom, 0) asc, document_type desc, name asc""", module, as_dict=True)

	for d in doctype_info:
		d.description = _(d.description or "")

	return doctype_info

def combine_common_sections(data):
	"""Combine sections declared in separate apps."""
	sections = []
	sections_dict = {}
	for each in data:
		if each["label"] not in sections_dict:
			sections_dict[each["label"]] = each
			sections.append(each)
		else:
			sections_dict[each["label"]]["items"] += each["items"]

	return sections

def get_config(app, module):
	"""Load module info from `[app].config.[module]`."""
	config = frappe.get_module("{app}.config.{module}".format(app=app, module=module))
	config = config.get_data()

	for section in config:
		for item in section["items"]:
			if not "label" in item:
				item["label"] = _(item["name"])
	return config

def add_setup_section(config, app, module, label, icon):
	"""Add common sections to `/desk#Module/Setup`"""
	try:
		setup_section = get_setup_section(app, module, label, icon)
		if setup_section:
			config.append(setup_section)
	except ImportError:
		pass

def get_setup_section(app, module, label, icon):
	"""Get the setup section from each module (for global Setup page)."""
	config = get_config(app, module)
	for section in config:
		if section.get("label")==_("Setup"):
			return {
				"label": label,
				"icon": icon,
				"items": section["items"]
			}

@frappe.whitelist()
def get_section_count(section=None, module=None, section_label=None):
	"""Get count for doctypes listed in module info."""
	doctypes = []
	if module and section_label:
		data = get_data(module)
		for each in data:
			if each["label"] == section_label:
				section = each
				break

	if section:
		doctypes = get_doctypes(section)

	count = get_count(doctypes)

	return count

def get_doctypes(section):
	doctypes = []

	for item in section.get("items", []):
		if item.get("type")=="doctype":
			doctypes.append(item["name"])
		elif item.get("doctype"):
			doctypes.append(item["doctype"])

	return list(set(doctypes))

def get_count(doctypes):
	count = {}
	can_read = frappe.user.get_can_read()
	for d in doctypes:
		if d in can_read:
			count[d] = get_doctype_count_from_table(d)
	return count

def get_doctype_count_from_table(doctype):
	try:
		count = reportview.execute(doctype, fields=["count(*)"], as_list=True)[0][0]
	except Exception, e:
		if e.args[0]==1146:
			count = None
		else:
			raise
	return cint(count)

def get_report_list(module, is_standard="No"):
	"""Returns list on new style reports for modules."""
	reports =  frappe.get_list("Report", fields=["name", "ref_doctype", "report_type"], filters=
		{"is_standard": is_standard, "disabled": ("in", ("0", "NULL", "")), "module": module},
		order_by="name")

	out = []
	for r in reports:
		out.append({
			"type": "report",
			"doctype": r.ref_doctype,
			"is_query_report": 1 if r.report_type in ("Query Report", "Script Report") else 0,
			"description": _(r.report_type),
			"label": _(r.name),
			"name": r.name
		})

	return out
