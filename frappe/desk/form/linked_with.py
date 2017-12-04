# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, json
from frappe.model.meta import is_single
from frappe.modules import load_doctype_module
import frappe.desk.form.meta
import frappe.desk.form.load
from six import string_types

@frappe.whitelist()
def get_linked_docs(doctype, name, linkinfo=None, for_doctype=None):
	if isinstance(linkinfo, string_types):
		# additional fields are added in linkinfo
		linkinfo = json.loads(linkinfo)

	results = {}

	if not linkinfo:
		return results

	if for_doctype:
		links = frappe.get_doc(doctype, name).get_link_filters(for_doctype)

		if links:
			linkinfo = links

		if for_doctype in linkinfo:
			# only get linked with for this particular doctype
			linkinfo = { for_doctype: linkinfo.get(for_doctype) }
		else:
			return results

	me = frappe.db.get_value(doctype, name, ["parenttype", "parent"], as_dict=True)

	for dt, link in linkinfo.items():
		link["doctype"] = dt
		link_meta_bundle = frappe.desk.form.load.get_meta_bundle(dt)
		linkmeta = link_meta_bundle[0]
		if not linkmeta.get("issingle"):
			fields = [d.fieldname for d in linkmeta.get("fields", {"in_list_view":1,
				"fieldtype": ["not in", ["Image", "HTML", "Button", "Table"]]})] \
				+ ["name", "modified", "docstatus"]

			if link.get("add_fields"):
				fields += link["add_fields"]

			fields = ["`tab{dt}`.`{fn}`".format(dt=dt, fn=sf.strip()) for sf in fields if sf
				and "`tab" not in sf]

			try:
				if link.get("filters"):
					ret = frappe.get_list(doctype=dt, fields=fields, filters=link.get("filters"))

				elif link.get("get_parent"):
					if me and me.parent and me.parenttype == dt:
						ret = frappe.get_list(doctype=dt, fields=fields,
							filters=[[dt, "name", '=', me.parent]])
					else:
						ret = None

				elif link.get("child_doctype"):
					filters = [[link.get('child_doctype'), link.get("fieldname"), '=', name]]

					# dynamic link
					if link.get("doctype_fieldname"):
						filters.append([link.get('child_doctype'), link.get("doctype_fieldname"), "=", doctype])

					ret = frappe.get_list(doctype=dt, fields=fields, filters=filters, distinct=True)

				else:
					if link.get("fieldname"):
						filters = [[dt, link.get("fieldname"), '=', name]]
						# dynamic link
						if link.get("doctype_fieldname"):
							filters.append([dt, link.get("doctype_fieldname"), "=", doctype])
						ret = frappe.get_list(doctype=dt, fields=fields, filters=filters)

					else:
						ret = None

			except frappe.PermissionError:
				if frappe.local.message_log:
					frappe.local.message_log.pop()

				continue

			if ret:
				results[dt] = ret

	return results

@frappe.whitelist()
def get_linked_doctypes(doctype):
	"""add list of doctypes this doctype is 'linked' with.

	Example, for Customer:

		{"Address": {"fieldname": "customer"}..}
	"""
	return frappe.cache().hget("linked_doctypes", doctype, lambda: _get_linked_doctypes(doctype))

def _get_linked_doctypes(doctype):
	ret = {}

	# find fields where this doctype is linked
	ret.update(get_linked_fields(doctype))

	ret.update(get_dynamic_linked_fields(doctype))

	# find links of parents
	links = frappe.db.sql("""select dt from `tabCustom Field`
		where (fieldtype="Table" and options=%s)""", (doctype))
	links += frappe.db.sql("""select parent from tabDocField
		where (fieldtype="Table" and options=%s)""", (doctype))

	for dt, in links:
		if not dt in ret:
			ret[dt] = {"get_parent": True}

	for dt in list(ret.keys()):
		try:
			doctype_module = load_doctype_module(dt)
		except ImportError:
			# in case of Custom DocType
			continue

		if getattr(doctype_module, "exclude_from_linked_with", False):
			del ret[dt]

	return ret

def get_linked_fields(doctype):
	links = frappe.db.sql("""select parent, fieldname from tabDocField
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))
	links += frappe.db.sql("""select dt as parent, fieldname from `tabCustom Field`
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))

	links = dict(links)

	ret = {}

	if links:
		for dt in links:
			ret[dt] = { "fieldname": links[dt] }

		# find out if linked in a child table
		for parent, options in frappe.db.sql("""select parent, options from tabDocField
			where fieldtype="Table"
				and options in (select name from tabDocType
					where istable=1 and name in (%s))""" % ", ".join(["%s"] * len(links)) ,tuple(links)):

			ret[parent] = {"child_doctype": options, "fieldname": links[options] }
			if options in ret:
				del ret[options]

	return ret

def get_dynamic_linked_fields(doctype):
	ret = {}

	links = frappe.db.sql("""select parent as doctype, fieldname, options as doctype_fieldname
		from `tabDocField` where fieldtype='Dynamic Link'""", as_dict=True)
	links += frappe.db.sql("""select dt as doctype, fieldname, options as doctype_fieldname
		from `tabCustom Field` where fieldtype='Dynamic Link'""", as_dict=True)

	for df in links:
		if is_single(df.doctype):
			continue

		# optimized to get both link exists and parenttype
		possible_link = frappe.db.sql("""select distinct `{doctype_fieldname}`, parenttype
			from `tab{doctype}` where `{doctype_fieldname}`=%s""".format(**df), doctype, as_dict=True)
		if possible_link:
			for d in possible_link:
				# is child
				if d.parenttype:
					ret[d.parenttype] = {
						"child_doctype": df.doctype,
						"fieldname": df.fieldname,
						"doctype_fieldname": df.doctype_fieldname
					}

				else:
					ret[df.doctype] = {
						"fieldname": df.fieldname,
						"doctype_fieldname": df.doctype_fieldname
					}

	return ret