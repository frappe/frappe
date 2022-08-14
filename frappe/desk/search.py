# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Search
from __future__ import unicode_literals

import json
import re

import wrapt
from six import string_types

import frappe
from frappe import _, is_whitelisted
from frappe.permissions import has_permission
from frappe.translate import get_translated_doctypes
from frappe.utils import cint, cstr, unique


def sanitize_searchfield(searchfield):
	blacklisted_keywords = ["select", "delete", "drop", "update", "case", "and", "or", "like"]

	def _raise_exception(searchfield):
		frappe.throw(_("Invalid Search Field {0}").format(searchfield), frappe.DataError)

	if len(searchfield) == 1:
		# do not allow special characters to pass as searchfields
		regex = re.compile(r'^.*[=;*,\'"$\-+%#@()_].*')
		if regex.match(searchfield):
			_raise_exception(searchfield)

	if len(searchfield) >= 3:

		# to avoid 1=1
		if "=" in searchfield:
			_raise_exception(searchfield)

		# in mysql -- is used for commenting the query
		elif " --" in searchfield:
			_raise_exception(searchfield)

		# to avoid and, or and like
		elif any(" {0} ".format(keyword) in searchfield.split() for keyword in blacklisted_keywords):
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
def search_link(
	doctype,
	txt,
	query=None,
	filters=None,
	page_length=20,
	searchfield=None,
	reference_doctype=None,
	ignore_user_permissions=False,
):
	search_widget(
		doctype,
		txt.strip(),
		query,
		searchfield=searchfield,
		page_length=page_length,
		filters=filters,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
	)
	frappe.response["results"] = build_for_autosuggest(frappe.response["values"])
	del frappe.response["values"]


# this is called by the search box
@frappe.whitelist()
def search_widget(
	doctype,
	txt,
	query=None,
	searchfield=None,
	start=0,
	page_length=20,
	filters=None,
	filter_fields=None,
	as_dict=False,
	reference_doctype=None,
	ignore_user_permissions=False,
):

	start = cint(start)

	if isinstance(filters, string_types):
		filters = json.loads(filters)

	if searchfield:
		sanitize_searchfield(searchfield)

	if not searchfield:
		searchfield = "name"

	standard_queries = frappe.get_hooks().standard_queries or {}

	if query and query.split()[0].lower() != "select":
		# by method
		try:
			is_whitelisted(frappe.get_attr(query))
			frappe.response["values"] = frappe.call(
				query, doctype, txt, searchfield, start, page_length, filters, as_dict=as_dict
			)
		except frappe.exceptions.PermissionError as e:
			if frappe.local.conf.developer_mode:
				raise e
			else:
				frappe.respond_as_web_page(
					title="Invalid Method", html="Method not found", indicator_color="red", http_status_code=404
				)
			return
		except Exception as e:
			raise e
	elif not query and doctype in standard_queries:
		# from standard queries
		search_widget(
			doctype, txt, standard_queries[doctype][0], searchfield, start, page_length, filters
		)
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

			if filters == None:
				filters = []
			or_filters = []

			translated_doctypes = frappe.cache().hget(
				"translated_doctypes", "doctypes", get_translated_doctypes
			)
			# build from doctype
			if txt:
				field_types = [
					"Data",
					"Text",
					"Small Text",
					"Long Text",
					"Link",
					"Select",
					"Read Only",
					"Text Editor",
				]
				search_fields = ["name"]
				if meta.title_field:
					search_fields.append(meta.title_field)

				if meta.search_fields:
					search_fields.extend(meta.get_search_fields())

				for f in search_fields:
					fmeta = meta.get_field(f.strip())
					if (doctype not in translated_doctypes) and (
						f == "name" or (fmeta and fmeta.fieldtype in field_types)
					):
						or_filters.append([doctype, f.strip(), "like", "%{0}%".format(txt)])

			if meta.get("fields", {"fieldname": "enabled", "fieldtype": "Check"}):
				filters.append([doctype, "enabled", "=", 1])
			if meta.get("fields", {"fieldname": "disabled", "fieldtype": "Check"}):
				filters.append([doctype, "disabled", "!=", 1])

			# format a list of fields combining search fields and filter fields
			fields = get_std_fields_list(meta, searchfield or "name")
			if filter_fields:
				fields = list(set(fields + json.loads(filter_fields)))
			formatted_fields = ["`tab%s`.`%s`" % (meta.name, f.strip()) for f in fields]

			# find relevance as location of search term from the beginning of string `name`. used for sorting results.
			formatted_fields.append(
				"""locate({_txt}, `tab{doctype}`.`name`) as `_relevance`""".format(
					_txt=frappe.db.escape((txt or "").replace("%", "").replace("@", "")), doctype=doctype
				)
			)

			# In order_by, `idx` gets second priority, because it stores link count
			from frappe.model.db_query import get_order_by

			order_by_based_on_meta = get_order_by(doctype, meta)
			# 2 is the index of _relevance column
			order_by = "_relevance, {0}, `tab{1}`.idx desc".format(order_by_based_on_meta, doctype)

			ptype = "select" if frappe.only_has_select_perm(doctype) else "read"
			ignore_permissions = (
				True
				if doctype == "DocType"
				else (cint(ignore_user_permissions) and has_permission(doctype, ptype=ptype))
			)

			if doctype in translated_doctypes:
				page_length = None

			values = frappe.get_list(
				doctype,
				filters=filters,
				fields=formatted_fields,
				or_filters=or_filters,
				limit_start=start,
				limit_page_length=page_length,
				order_by=order_by,
				ignore_permissions=ignore_permissions,
				reference_doctype=reference_doctype,
				as_list=not as_dict,
				strict=False,
			)

			if doctype in translated_doctypes:
				# Filtering the values array so that query is included in very element
				values = (
					v
					for v in values
					if re.search(f"{re.escape(txt)}.*", _(v.name if as_dict else v[0]), re.IGNORECASE)
				)

			# Sorting the values array so that relevant results always come first
			# This will first bring elements on top in which query is a prefix of element
			# Then it will bring the rest of the elements and sort them in lexicographical order
			values = sorted(values, key=lambda x: relevance_sorter(x, txt, as_dict))

			# remove _relevance from results
			if as_dict:
				for r in values:
					r.pop("_relevance")
				frappe.response["values"] = values
			else:
				frappe.response["values"] = [r[:-1] for r in values]


def get_std_fields_list(meta, key):
	# get additional search fields
	sflist = ["name"]
	if meta.search_fields:
		for d in meta.search_fields.split(","):
			if d.strip() not in sflist:
				sflist.append(d.strip())

	if meta.title_field and meta.title_field not in sflist:
		sflist.append(meta.title_field)

	if key not in sflist:
		sflist.append(key)

	return sflist


def build_for_autosuggest(res):
	results = []
	for r in res:
		out = {"value": r[0], "description": ", ".join(unique(cstr(d) for d in r if d)[1:])}
		results.append(out)
	return results


def scrub_custom_query(query, key, txt):
	if "%(key)s" in query:
		query = query.replace("%(key)s", key)
	if "%s" in query:
		query = query.replace("%s", ((txt or "") + "%"))
	return query


def relevance_sorter(key, query, as_dict):
	value = _(key.name if as_dict else key[0])
	return (value.lower().startswith(query.lower()) is not True, value)


@wrapt.decorator
def validate_and_sanitize_search_inputs(fn, instance, args, kwargs):
	kwargs.update(dict(zip(fn.__code__.co_varnames, args)))
	sanitize_searchfield(kwargs["searchfield"])
	kwargs["start"] = cint(kwargs["start"])
	kwargs["page_len"] = cint(kwargs["page_len"])

	if kwargs["doctype"] and not frappe.db.exists("DocType", kwargs["doctype"]):
		return []

	return fn(**kwargs)


@frappe.whitelist()
def get_names_for_mentions(search_term):
	users_for_mentions = frappe.cache().get_value("users_for_mentions", get_users_for_mentions)
	user_groups = frappe.cache().get_value("user_groups", get_user_groups)

	filtered_mentions = []
	for mention_data in users_for_mentions + user_groups:
		if search_term.lower() not in mention_data.value.lower():
			continue

		mention_data["link"] = frappe.utils.get_url_to_form(
			"User Group" if mention_data.get("is_group") else "User Profile", mention_data["id"]
		)

		filtered_mentions.append(mention_data)

	return sorted(filtered_mentions, key=lambda d: d["value"])


def get_users_for_mentions():
	return frappe.get_all(
		"User",
		fields=["name as id", "full_name as value"],
		filters={
			"name": ["not in", ("Administrator", "Guest")],
			"allowed_in_mentions": True,
			"user_type": "System User",
			"enabled": True,
		},
	)


def get_user_groups():
	return frappe.get_all(
		"User Group", fields=["name as id", "name as value"], update={"is_group": True}
	)
