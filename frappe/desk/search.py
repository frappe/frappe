# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import re
from typing import NotRequired, TypedDict

import frappe

# Backward compatbility
from frappe import _, bold, is_whitelisted, validate_and_sanitize_search_inputs
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.model.db_query import get_order_by
from frappe.permissions import has_permission
from frappe.utils import cint, cstr, escape_html, unique
from frappe.utils.caching import http_cache
from frappe.utils.data import make_filter_tuple

PAGE_LENGTH_FOR_LINK_VALIDATION = 25_000


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
@frappe.whitelist()
@http_cache(max_age=60, stale_while_revalidate=5 * 60)
def search_link(
	doctype: str,
	txt: str,
	query: str | None = None,
	filters: str | dict | list | None = None,
	page_length: int = 10,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
	*,
	link_fieldname: str | None = None,
) -> list[LinkSearchResults]:
	results = search_widget(
		doctype,
		txt.strip(),
		query,
		searchfield=searchfield,
		page_length=page_length,
		filters=filters,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
		link_fieldname=link_fieldname,
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
	*,
	link_fieldname: str | None = None,
	for_link_validation: bool = False,
):
	if ignore_user_permissions:
		if reference_doctype and link_fieldname:
			validate_ignore_user_permissions(reference_doctype, link_fieldname, doctype)
		else:
			frappe.logger().error(
				"setting ignore_user_permissions=True requires reference_doctype and link_fieldname to be set. "
				f"Got reference_doctype={reference_doctype}, link_fieldname={link_fieldname}. Ignoring flag."
			)
			ignore_user_permissions = False

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

	if filters is None:
		filters = {}

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
				ignore_user_permissions=ignore_user_permissions,
				link_fieldname=link_fieldname,
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

	include_disabled = False
	if isinstance(filters, dict):
		if "include_disabled" in filters:
			if filters["include_disabled"] == 1:
				include_disabled = True
			filters.pop("include_disabled")

		filters = [make_filter_tuple(doctype, key, value) for key, value in filters.items()]

	if for_link_validation:
		filters.append([doctype, "name", "=", txt])

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

	if not include_disabled:
		if meta.get("fields", {"fieldname": "enabled", "fieldtype": "Check"}):
			filters.append([doctype, "enabled", "=", 1])
		if meta.get("fields", {"fieldname": "disabled", "fieldtype": "Check"}):
			filters.append([doctype, "disabled", "!=", 1])

	# format a list of fields combining search fields and filter fields
	fields = get_std_fields_list(meta, searchfield or "name")
	if filter_fields:
		fields = list(set(fields + json.loads(filter_fields)))
	formatted_fields = [f.strip() for f in fields]

	# Insert title field query after name
	if meta.show_title_field_in_link and meta.title_field:
		formatted_fields.insert(1, f"{meta.title_field} as label")

	order_by_based_on_meta = get_order_by(doctype, meta)
	# `idx` is number of times a document is referred, check link_count.py
	order_by = f"idx desc, {order_by_based_on_meta}"

	if not for_link_validation and not meta.translated_doctype:
		_txt = frappe.db.escape((txt or "").replace("%", "").replace("@", ""))
		# locate returns 0 if string is not found, convert 0 to null and then sort null to end in order by
		_relevance_expr = {"DIV": [1, {"NULLIF": [{"LOCATE": [_txt, "name"]}, 0]}]}

		# For MariaDB, wrap in IFNULL for sorting to push nulls to end
		_relevance = {"IFNULL": [_relevance_expr, -9999], "as": "_relevance"}
		formatted_fields.append(_relevance)
		order_by = f"_relevance desc, {order_by}"

	values = frappe.get_list(
		doctype,
		filters=filters,
		fields=formatted_fields,
		or_filters=or_filters,
		limit_start=start,
		limit_page_length=None if meta.translated_doctype else page_length,
		order_by=order_by,
		ignore_permissions=doctype == "DocType",
		ignore_user_permissions=ignore_user_permissions,
		reference_doctype=reference_doctype,
		as_list=not as_dict,
		strict=False,
	)

	if not for_link_validation:
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


def validate_ignore_user_permissions(form_doctype, link_fieldname, link_doctype):
	def _throw(message):
		frappe.throw(message, title=_('Error validating "Ignore User Permissions"'))

	meta = frappe.get_meta(form_doctype)
	link_field = meta.get_field(link_fieldname)

	if not link_field:
		_throw(
			_("Field <code>{0}</code> not found in {1}").format(
				escape_html(link_fieldname), bold(_(form_doctype))
			)
		)

	ignore_user_permissions = link_field.ignore_user_permissions
	found_doctype = None

	if link_field.fieldtype == "Link":
		found_doctype = link_field.options

	if link_field.fieldtype == "Table MultiSelect":
		child_meta = frappe.get_meta(link_field.options)
		child_link_field = next((field for field in child_meta.fields if field.fieldtype == "Link"), None)
		if not child_link_field:
			_throw(
				_(
					"Table MultiSelect requires a table with at least one Link field, but none was found in {0}"
				).format(bold(_(link_field.options)))
			)

		found_doctype = child_link_field.options
		if not ignore_user_permissions:
			# ignore user permissions should be set in parent table field
			# or in child table link field
			ignore_user_permissions = child_link_field.ignore_user_permissions

	if not ignore_user_permissions:
		_throw(
			_("The field {0} in {1} does not allow ignoring user permissions").format(
				bold(meta.get_label(link_fieldname)), bold(_(form_doctype))
			)
		)

	if link_field.fieldtype == "Dynamic Link":
		return  # skip doctype check for Dynamic Link fields

	if found_doctype != link_doctype:
		_throw(
			_("The field {0} in {1} links to {2} and not {3}").format(
				bold(meta.get_label(link_fieldname)),
				bold(_(form_doctype)),
				bold(_(found_doctype)),
				bold(escape_html(link_doctype)),
			)
		)


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
			label = _(item[1]) if meta.translated_doctype else item[1]
			item[1] = item[0]

			if len(item) >= 3 and item[2] == label:
				# remove redundant title ("label") value
				del item[2]

			autosuggest_row = {"value": item[0], "description": to_string(item[1:])}
			if label:
				autosuggest_row["label"] = label

			results.append(autosuggest_row)
	else:
		for item in res:
			label = _(item[0]) if meta.translated_doctype else item[0]
			results.append({"value": item[0], "description": to_string(item[1:]), "label": label})

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
		fields=["name as id", "full_name as value", "email"],
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
