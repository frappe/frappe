# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Search
from __future__ import unicode_literals
import frappe, json
from frappe.utils import cstr, unique, cint
from frappe.permissions import has_permission
from frappe import _
from six import string_types
import re

UNTRANSLATED_DOCTYPES = ["DocType", "Role"]

def sanitize_searchfield(searchfield):
	blacklisted_keywords = ['select', 'delete', 'drop', 'update', 'case', 'and', 'or', 'like']

	def _raise_exception(searchfield):
		frappe.throw(_('Invalid Search Field {0}').format(searchfield), frappe.DataError)

	if len(searchfield) == 1:
		# do not allow special characters to pass as searchfields
		regex = re.compile(r'^.*[=;*,\'"$\-+%#@()_].*')
		if regex.match(searchfield):
			_raise_exception(searchfield)

	if len(searchfield) >= 3:

		# to avoid 1=1
		if '=' in searchfield:
			_raise_exception(searchfield)

		# in mysql -- is used for commenting the query
		elif ' --' in searchfield:
			_raise_exception(searchfield)

		# to avoid and, or and like
		elif any(' {0} '.format(keyword) in searchfield.split() for keyword in blacklisted_keywords):
			_raise_exception(searchfield)

		# to avoid select, delete, drop, update and case
		elif any(keyword in searchfield.split() for keyword in blacklisted_keywords):
			_raise_exception(searchfield)

		else:
			regex = re.compile(r'^.*[=;*,\'"$\-+%#@()].*')
			if any(regex.match(f) for f in searchfield.split()):
				_raise_exception(searchfield)

# this is called by the Link Field
@frappe.whitelist()
def search_link(doctype, txt, query=None, filters=None, page_length=20, searchfield=None, reference_doctype=None, ignore_user_permissions=False):
	search_widget(doctype, txt, query, searchfield=searchfield, page_length=page_length, filters=filters, reference_doctype=reference_doctype, ignore_user_permissions=ignore_user_permissions)
	frappe.response['results'] = build_for_autosuggest(frappe.response["values"])
	del frappe.response["values"]

# this is called by the search box
@frappe.whitelist()
def search_widget(doctype, txt, query=None, searchfield=None, start=0,
	page_length=10, filters=None, filter_fields=None, as_dict=False, reference_doctype=None, ignore_user_permissions=False):
	if isinstance(filters, string_types):
		filters = json.loads(filters)
	
	if searchfield:
		sanitize_searchfield(searchfield)

	if not searchfield:
		searchfield = "name"

	standard_queries = frappe.get_hooks().standard_queries or {}

	if query and query.split()[0].lower()!="select":
		# by method
		frappe.response["values"] = frappe.call(query, doctype, txt,
			searchfield, start, page_length, filters, as_dict=as_dict)
	elif not query and doctype in standard_queries:
		# from standard queries
		search_widget(doctype, txt, standard_queries[doctype][0],
			searchfield, start, page_length, filters)
	else:
		meta = frappe.get_meta(doctype)

		if query:
			frappe.throw(_("This query style is discontinued"))
			# custom query
			# frappe.response["values"] = frappe.db.sql(scrub_custom_query(query, searchfield, txt))
		else:
			if isinstance(filters, dict):
				filters_items = filters.items()
				filters = []
				for f in filters_items:
					if isinstance(f[1], (list, tuple)):
						filters.append([doctype, f[0], f[1][0], f[1][1]])
					else:
						filters.append([doctype, f[0], "=", f[1]])

			if filters==None:
				filters = []
			or_filters = []


			# build from doctype
			if txt:
				search_fields = ["name"]
				if meta.title_field:
					search_fields.append(meta.title_field)

				if meta.search_fields:
					search_fields.extend(meta.get_search_fields())

				for f in search_fields:
					fmeta = meta.get_field(f.strip())
					if (doctype not in UNTRANSLATED_DOCTYPES) and (f == "name" or (fmeta and fmeta.fieldtype in ["Data", "Text", "Small Text", "Long Text",
						"Link", "Select", "Read Only", "Text Editor"])):
							or_filters.append([doctype, f.strip(), "like", "%{0}%".format(txt)])

			if meta.get("fields", {"fieldname":"enabled", "fieldtype":"Check"}):
				filters.append([doctype, "enabled", "=", 1])
			if meta.get("fields", {"fieldname":"disabled", "fieldtype":"Check"}):
				filters.append([doctype, "disabled", "!=", 1])

			# format a list of fields combining search fields and filter fields
			fields = get_std_fields_list(meta, searchfield or "name")
			if filter_fields:
				fields = list(set(fields + json.loads(filter_fields)))
			formatted_fields = ['`tab%s`.`%s`' % (meta.name, f.strip()) for f in fields]

			# find relevance as location of search term from the beginning of string `name`. used for sorting results.
			formatted_fields.append("""locate({_txt}, `tab{doctype}`.`name`) as `_relevance`""".format(
				_txt=frappe.db.escape((txt or "").replace("%", "")), doctype=doctype))


			# In order_by, `idx` gets second priority, because it stores link count
			from frappe.model.db_query import get_order_by
			order_by_based_on_meta = get_order_by(doctype, meta)
			# 2 is the index of _relevance column
			order_by = "2 , {0}, `tab{1}`.idx desc".format(order_by_based_on_meta, doctype)

			ignore_permissions = True if doctype == "DocType" else (cint(ignore_user_permissions) and has_permission(doctype))

			if doctype in UNTRANSLATED_DOCTYPES:
				page_length = None

			values = frappe.get_list(doctype,
				filters=filters,
				fields=formatted_fields,
				or_filters=or_filters,
				limit_start=start,
				limit_page_length=page_length,
				order_by=order_by,
				ignore_permissions=ignore_permissions,
				reference_doctype=reference_doctype,
				as_list=not as_dict)

			if doctype in UNTRANSLATED_DOCTYPES:
				values = tuple([v for v in list(values) if re.search(txt+".*", (_(v.name) if as_dict else _(v[0])), re.IGNORECASE)])

			# remove _relevance from results
			if as_dict:
				for r in values:
					r.pop("_relevance")
				frappe.response["values"] = values
			else:
				frappe.response["values"] = [r[:-1] for r in values]

def get_std_fields_list(meta, key):
	# get additional search fields
	sflist = meta.search_fields and meta.search_fields.split(",") or []
	title_field = [meta.title_field] if (meta.title_field and meta.title_field not in sflist) else []
	sflist = ['name'] + sflist + title_field
	if not key in sflist:
		sflist = sflist + [key]

	return sflist

def build_for_autosuggest(res):
	results = []
	for r in res:
		out = {"value": r[0], "description": ", ".join(unique(cstr(d) for d in r if d)[1:])}
		results.append(out)
	return results

def scrub_custom_query(query, key, txt):
	if '%(key)s' in query:
		query = query.replace('%(key)s', key)
	if '%s' in query:
		query = query.replace('%s', ((txt or '') + '%'))
	return query
