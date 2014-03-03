# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.widgets import reportview
from frappe.utils import cint

@frappe.whitelist()
def get(module):
	data = get_data(module)
	doctypes = get_doctypes(data)
	
	return {
		"data": data,
		"item_count": get_count(doctypes),
		"reports": get_report_list(module)
	}
	
def get_data(module):
	data = []
	module = frappe.scrub(module)

	for app in frappe.get_installed_apps():
		try:
			data += get_config(app, module)
		except ImportError, e:
			pass
			
	return data
	
def get_config(app, module):
	config = frappe.get_module("{app}.config.{module}".format(app=app, module=module))
	return config.get_data() if hasattr(config, "get_data") else config.data
	
def get_doctypes(data):
	doctypes = []
	
	for section in data:
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
	
def get_report_list(module):
	"""return list on new style reports for modules"""	
	return frappe.db.sql("""
		select distinct "report" as type, tabReport.name, tabReport.ref_doctype as doctype,
			if((tabReport.report_type='Query Report' or 
				tabReport.report_type='Script Report'), 1, 0) as is_query_report,
			report_type as description
		from `tabReport`, `tabDocType`
		where tabDocType.module=%s
			and tabDocType.name = tabReport.ref_doctype
			and tabReport.docstatus in (0, NULL)
			and ifnull(tabReport.is_standard, "No")="No"
			and ifnull(tabReport.disabled,0) != 1
			order by tabReport.name""", module, as_dict=True)