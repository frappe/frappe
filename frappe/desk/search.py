# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import re
from typing import TypedDict

from typing_extensions import NotRequired  # not required in 3.11+

import frappe

# Backward compatbility
from frappe import _, is_whitelisted, validate_and_sanitize_search_inputs
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.model.db_query import get_order_by
from frappe.permissions import has_permission
from frappe.utils import cint, cstr, unique
from frappe.utils.data import make_filter_tuple


def sanitize_searchfield(searchfield: str):
	if not searchfield:
		return

	if SPECIAL_CHAR_PATTERN.search(searchfield):
		frappe.throw(_("Invalid Search Field {0}").format(searchfield), frappe.DataError)


class LinkSearchResults(TypedDict):
	value: str
	description: str
	label: NotRequired[str]


# this is called by the Link Field
@frappe.whitelist(allow_guest=True)
def search_link(
	doctype: str,
	txt: str,
	query: str | None = None,
	filters: str | dict | list | None = None,
	page_length: int = 10,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
) -> list[LinkSearchResults]:
	if frappe.session.user == 'Guest':
		ignore_user_permissions = 0
	results = search_widget(
		doctype,
		txt.strip(),
		query,
		searchfield=searchfield,
		page_length=page_length,
		filters=filters,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
	)
	return build_for_autosuggest(results, doctype=doctype)


# this is called by the search box
@frappe.whitelist()
def search_widget(
	doctype: str,
	txt: str,
	query: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_length: int = 10,
	filters: str | None | dict | list = None,
	filter_fields=None,
	as_dict: bool = False,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
):
	start = cint(start)

	if isinstance(filters, str):
		filters = json.loads(filters)

	if searchfield:
		sanitize_searchfield(searchfield)

	if not searchfield:
		searchfield = "name"

	standard_queries = frappe.get_hooks().standard_queries or {}

	if not query and doctype in standard_queries:
		query = standard_queries[doctype][-1]

	if query:  # Query = custom search query i.e. python function
		try:
			is_whitelisted(frappe.get_attr(query))
			return frappe.call(
				query,
				doctype,
				txt,
				searchfield,
				start,
				page_length,
				filters,
				as_dict=as_dict,
				reference_doctype=reference_doctype,
			)
		except (frappe.PermissionError, frappe.AppNotInstalledError, ImportError):
			if frappe.local.conf.developer_mode:
				raise
			else:
				frappe.respond_as_web_page(
					title="Invalid Method",
					html="Method not found",
					indicator_color="red",
					http_status_code=404,
				)
				return []

	meta = frappe.get_meta(doctype)

	if isinstance(filters, dict):
		filters = [make_filter_tuple(doctype, key, value) for key, value in filters.items()]
	elif filters is None:
		filters = []
	or_filters = []

	# build from doctype
	if txt:
		field_types = {
			"Data",
			"Text",
			"Small Text",
			"Long Text",
			"Link",
			"Select",
			"Read Only",
			"Text Editor",
		}
		search_fields = ["name"]
		if meta.title_field:
			search_fields.append(meta.title_field)

		if meta.search_fields:
			search_fields.extend(meta.get_search_fields())

		for f in search_fields:
			fmeta = meta.get_field(f.strip())
			if not meta.translated_doctype and (f == "name" or (fmeta and fmeta.fieldtype in field_types)):
				or_filters.append([doctype, f.strip(), "like", f"%{txt}%"])

	if meta.get("fields", {"fieldname": "enabled", "fieldtype": "Check"}):
		filters.append([doctype, "enabled", "=", 1])
	if meta.get("fields", {"fieldname": "disabled", "fieldtype": "Check"}):
		filters.append([doctype, "disabled", "!=", 1])

	# format a list of fields combining search fields and filter fields
	fields = get_std_fields_list(meta, searchfield or "name")
	if filter_fields:
		fields = list(set(fields + json.loads(filter_fields)))
	formatted_fields = [f"`tab{meta.name}`.`{f.strip()}`" for f in fields]

	# Insert title field query after name
	if meta.show_title_field_in_link and meta.title_field:
		formatted_fields.insert(1, f"`tab{meta.name}`.{meta.title_field} as `label`")

	order_by_based_on_meta = get_order_by(doctype, meta)
	# `idx` is number of times a document is referred, check link_count.py
	order_by = f"`tab{doctype}`.idx desc, {order_by_based_on_meta}"

	if not meta.translated_doctype:
		_txt = frappe.db.escape((txt or "").replace("%", "").replace("@", ""))
		# locate returns 0 if string is not found, convert 0 to null and then sort null to end in order by
		_relevance = f"(1 / nullif(locate({_txt}, `tab{doctype}`.`name`), 0))"
		formatted_fields.append(f"""{_relevance} as `_relevance`""")
		# Since we are sorting by alias postgres needs to know number of column we are sorting
		if frappe.db.db_type == "mariadb":
			order_by = f"ifnull(_relevance, -9999) desc, {order_by}"
		elif frappe.db.db_type == "postgres":
			# Since we are sorting by alias postgres needs to know number of column we are sorting
			order_by = f"{len(formatted_fields)} desc nulls last, {order_by}"

	ignore_permissions = doctype == "DocType" or (
		cint(ignore_user_permissions)
		and has_permission(
			doctype,
			ptype="select" if frappe.only_has_select_perm(doctype) else "read",
			parent_doctype=reference_doctype,
		)
	)

	values = frappe.get_list(
		doctype,
		filters=filters,
		fields=formatted_fields,
		or_filters=or_filters,
		limit_start=start,
		limit_page_length=None if meta.translated_doctype else page_length,
		order_by=order_by,
		ignore_permissions=ignore_permissions,
		reference_doctype=reference_doctype,
		as_list=not as_dict,
		strict=False,
	)

	if meta.translated_doctype:
		# Filtering the values array so that query is included in very element
		values = (
			result
			for result in values
			if any(
				re.search(f"{re.escape(txt)}.*", _(cstr(value)) or "", re.IGNORECASE)
				for value in (result.values() if as_dict else result)
			)
		)

	# Sorting the values array so that relevant results always come first
	# This will first bring elements on top in which query is a prefix of element
	# Then it will bring the rest of the elements and sort them in lexicographical order
	values = sorted(values, key=lambda x: relevance_sorter(x, txt, as_dict))

	# remove _relevance from results
	if not meta.translated_doctype:
		if as_dict:
			for r in values:
				r.pop("_relevance", None)
		else:
			values = [r[:-1] for r in values]

	return values


def get_std_fields_list(meta, key):
	# get additional search fields
	sflist = ["name"]

	if meta.title_field and meta.title_field not in sflist:
		sflist.append(meta.title_field)

	if key not in sflist:
		sflist.append(key)

	if meta.search_fields:
		for d in meta.search_fields.split(","):
			if d.strip() not in sflist:
				sflist.append(d.strip())

	return sflist


def build_for_autosuggest(res: list[tuple], doctype: str) -> list[LinkSearchResults]:
	def to_string(parts):
		return ", ".join(
			unique(_(cstr(part)) if meta.translated_doctype else cstr(part) for part in parts if part)
		)

	results = []
	meta = frappe.get_meta(doctype)
	if meta.show_title_field_in_link:
		for item in res:
			item = list(item)
			if len(item) == 1:
				item = [item[0], item[0]]
			label = item[1]  # use title as label
			item[1] = item[0]  # show name in description instead of title

			if len(item) >= 3 and item[2] == label:
				# remove redundant title ("label") value
				del item[2]

			autosuggest_row = {"value": item[0], "description": to_string(item[1:])}
			if label:
				autosuggest_row["label"] = label

			results.append(autosuggest_row)
	else:
		results.extend({"value": item[0], "description": to_string(item[1:])} for item in res)

	return results


def scrub_custom_query(query, key, txt):
	if "%(key)s" in query:
		query = query.replace("%(key)s", key)
	if "%s" in query:
		query = query.replace("%s", ((txt or "") + "%"))
	return query


def relevance_sorter(key, query, as_dict):
	value = _(key.name if as_dict else key[0])
	return (cstr(value).casefold().startswith(query.casefold()) is not True, value)


@frappe.whitelist()
def get_names_for_mentions(search_term):
	users_for_mentions = frappe.cache.get_value("users_for_mentions", get_users_for_mentions)
	user_groups = frappe.cache.get_value("user_groups", get_user_groups)

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
	return frappe.get_all("User Group", fields=["name as id", "name as value"], update={"is_group": True})


@frappe.whitelist()
def get_link_title(doctype, docname):
	meta = frappe.get_meta(doctype)

	if meta.show_title_field_in_link:
		return frappe.db.get_value(doctype, docname, meta.title_field)

	return docname
