# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes, json
from webnotes.widgets import reportview

@webnotes.whitelist()
def get_data(module, doctypes='[]'):
	doctypes = json.loads(doctypes)
	return {
		"reports": get_report_list(module),
		"item_count": get_count(doctypes)
	}
	
def get_count(doctypes):
	count = {}
	can_read = webnotes.user.get_can_read()
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
	return count
	
def get_report_list(module):
	"""return list on new style reports for modules"""	
	return webnotes.conn.sql("""
		select distinct tabReport.name, tabReport.ref_doctype as doctype, 
			if((tabReport.report_type='Query Report' or 
				tabReport.report_type='Script Report'), 1, 0) as is_query_report
		from `tabReport`, `tabDocType`
		where tabDocType.module=%s
			and tabDocType.name = tabReport.ref_doctype
			and tabReport.docstatus in (0, NULL)
			and ifnull(tabReport.is_standard, "No")="No"
			and ifnull(tabReport.disabled,0) != 1
			order by tabReport.name""", module, as_dict=True)