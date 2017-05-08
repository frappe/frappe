# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

# select doctypes that are accessed by the user (not read_only) first, so that the 
# the validation message shows the user-facing doctype first. 
# For example Journal Entry should be validated before GL Entry (which is an internal doctype)

dynamic_link_queries =  [
	"""select parent,
		(select read_only from `tabDocType` where name=tabDocField.parent) as read_only,
		fieldname, options 
	from tabDocField 
	where fieldtype='Dynamic Link' 
	order by read_only""",

	"""select dt as parent,
		(select read_only from `tabDocType` where name=`tabCustom Field`.dt) as read_only,
		fieldname, options 
	from `tabCustom Field` 
	where fieldtype='Dynamic Link' 
	order by read_only""",
]

def get_dynamic_link_map(for_delete=False):
	'''Build a map of all dynamically linked tables. For example,
		if Note is dynamically linked to ToDo, the function will return
		`{"Note": ["ToDo"], "Sales Invoice": ["Journal Entry Detail"]}`

	Note: Will not map single doctypes
	'''
	if getattr(frappe.local, 'dynamic_link_map', None)==None or frappe.flags.in_test:
		# Build from scratch
		dynamic_link_map = {}
		for df in get_dynamic_links():
			meta = frappe.get_meta(df.parent)
			if meta.issingle:
				# always check in Single DocTypes
				dynamic_link_map.setdefault(meta.name, []).append(df)
			else:
				links = frappe.db.sql_list("""select distinct {options} from `tab{parent}`""".format(**df))
				for doctype in links:
					dynamic_link_map.setdefault(doctype, []).append(df)

		frappe.local.dynamic_link_map = dynamic_link_map
	return frappe.local.dynamic_link_map

def get_dynamic_links():
	'''Return list of dynamic link fields as DocField.
	Uses cache if possible'''
	df = []
	for query in dynamic_link_queries:
		df += frappe.db.sql(query, as_dict=True)
	return df
