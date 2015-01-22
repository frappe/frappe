# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.widgets import reportview
from frappe.utils import cint
from frappe import _

@frappe.whitelist()
def get(module):
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
	data = build_config_from_file(module)

	if not data:
		data = build_standard_config(module)

	data = combine_common_sections(data)

	return data

def build_config_from_file(module):
	data = []
	module = frappe.scrub(module)

	for app in frappe.get_installed_apps():
		try:
			data += get_config(app, module)
		except ImportError:
			pass

	return data

def build_standard_config(module):
	if not frappe.db.get_value("Module Def", module):
		frappe.throw(_("Module Not Found"))

	data = []

	doctypes = frappe.db.sql("""select "doctype" as type, name, description,
		ifnull(document_type, "") as document_type
		from `tabDocType` where module=%s and ifnull(istable, 0)=0
		order by document_type desc, name asc""", module, as_dict=True)

	for d in doctypes:
		d.description = _(d.description or "")

	documents = [d for d in doctypes if d.document_type in ("Transaction", "Master", "")]
	if documents:
		data.append({
			"label": _("Documents"),
			"icon": "icon-star",
			"items": documents
		})

	setup = [d for d in doctypes if d.document_type in ("System", "Other")]
	if setup:
		data.append({
			"label": _("Setup"),
			"icon": "icon-cog",
			"items": setup
		})

	reports = get_report_list(module, is_standard="Yes")
	if reports:
		data.append({
			"label": _("Standard Reports"),
			"icon": "icon-list",
			"items": reports
		})

	return data

def combine_common_sections(data):
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
	config = frappe.get_module("{app}.config.{module}".format(app=app, module=module))
	config = config.get_data()

	for section in config:
		for item in section["items"]:
			if not "label" in item:
				item["label"] = _(item["name"])
	return config

def add_setup_section(config, app, module, label, icon):
	try:
		setup_section = get_setup_section(app, module, label, icon)
		if setup_section:
			config.append(setup_section)
	except ImportError:
		pass

def get_setup_section(app, module, label, icon):
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
	"""return list on new style reports for modules"""
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
