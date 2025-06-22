# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

# select doctypes that are accessed by the user (not read_only) first, so that the
# the validation message shows the user-facing doctype first.
# For example Journal Entry should be validated before GL Entry (which is an internal doctype)

dynamic_link_queries = [
	"""select `tabDocField`.parent,
		`tabDocType`.read_only, `tabDocType`.in_create,
		`tabDocField`.fieldname, `tabDocField`.options
	from `tabDocField`, `tabDocType`
	where `tabDocField`.fieldtype='Dynamic Link' and
	`tabDocType`.`name`=`tabDocField`.parent and `tabDocType`.is_virtual = 0
	order by `tabDocType`.read_only, `tabDocType`.in_create""",
	"""select `tabCustom Field`.dt as parent,
		`tabDocType`.read_only, `tabDocType`.in_create,
		`tabCustom Field`.fieldname, `tabCustom Field`.options
	from `tabCustom Field`, `tabDocType`
	where `tabCustom Field`.fieldtype='Dynamic Link' and
	`tabDocType`.`name`=`tabCustom Field`.dt
	order by `tabDocType`.read_only, `tabDocType`.in_create""",
]


def get_dynamic_link_map(for_delete=False):
	"""Build a map of all dynamically linked tables. For example,
	        if Note is dynamically linked to ToDo, the function will return
	        `{"Note": ["ToDo"], "Sales Invoice": ["Journal Entry Detail"]}`

	Note: Will not map single doctypes
	"""
	if getattr(frappe.local, "dynamic_link_map", None) is None or frappe.in_test:
		# Build from scratch
		dynamic_link_map = {}
		for df in get_dynamic_links():
			meta = frappe.get_meta(df.parent)
			if meta.issingle:
				# always check in Single DocTypes
				dynamic_link_map.setdefault(meta.name, []).append(df)
			else:
				try:
					links = fetch_distinct_link_doctypes(df.parent, df.options)
					for doctype in links:
						dynamic_link_map.setdefault(doctype, []).append(df)
				except frappe.db.TableMissingError:
					pass

		frappe.local.dynamic_link_map = dynamic_link_map
	return frappe.local.dynamic_link_map


def get_dynamic_links():
	"""Return list of dynamic link fields as DocField.
	Uses cache if possible"""
	df = []
	for query in dynamic_link_queries:
		df += frappe.db.sql(query, as_dict=True)
	return df


def _dynamic_link_map_key(doctype, fieldname):
	return f"dynamic_link_map::{doctype}::{fieldname}"


def fetch_distinct_link_doctypes(doctype: str, fieldname: str):
	"""Return all unique doctypes a dynamic link is linking against.
	Note:
	- results are cached and can *possibly be outdated*
	- cache gets updated when a document with different document link is discovered
	- raw queries adding dynamic link won't update this cache
	- cache miss can often be VERY expensive on large table.
	"""

	key = _dynamic_link_map_key(doctype, fieldname)
	doctypes = frappe.cache.get_value(key)

	if doctypes is None:
		doctypes = frappe.db.sql(f"""select distinct `{fieldname}` from `tab{doctype}`""", pluck=True)
		frappe.cache.set_value(key, doctypes, expires_in_sec=12 * 60 * 60)

	return doctypes


def invalidate_distinct_link_doctypes(doctype: str, fieldname: str, linked_doctype: str):
	"""If new linked doctype is discovered for a dynamic link then cache is evicted."""

	key = _dynamic_link_map_key(doctype, fieldname)
	doctypes = frappe.cache.get_value(key)

	if doctypes is None or not isinstance(doctypes, list):
		return

	if linked_doctype not in doctypes:
		# Note: Do NOT "update" cache because it can lead to concurrency bugs.
		frappe.cache.delete_value(key)
		frappe.db.after_commit.add(lambda: frappe.cache.delete_value(key))
