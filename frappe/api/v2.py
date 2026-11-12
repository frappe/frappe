"""REST API v2

This file defines routes and implementation for REST API.

Note:
	- All functions in this file should be treated as "whitelisted" as they are exposed via routes
	- None of the functions present here should be called from python code, their location and
	  internal implementation can change without treating it as "breaking change".
"""

import json
from functools import partial
from typing import Any

from werkzeug.routing import Rule

import frappe
import frappe.client
from frappe import _, cint, cstr, get_newargs, is_whitelisted
from frappe.api import activity, bulk_actions, bulk_collaboration, collaboration, discovery, files
from frappe.api.include import (
	add_document_parts,
	add_list_parts,
	add_meta_parts,
	add_row_parts,
	get_doctype_state_field,
	get_workflow_state_styles,
	parse_include,
	serialize_meta,
)
from frappe.api.utils import FrappeValueError, apply_controller_get_list
from frappe.apps import get_disabled_apps
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.database.utils import DefaultOrderBy
from frappe.exceptions import AppDisabledError
from frappe.handler import is_valid_http_method, resolve_method, run_server_script, upload_file
from frappe.mcp import handle as handle_mcp
from frappe.model.document import Document
from frappe.model.utils import is_virtual_doctype
from frappe.utils.data import is_desk_v2_enabled

SEARCH_PAGE_LENGTH = 10
OVERRIDABLE_METHODS = ("submit", "cancel")
# These act on the saved row, so the desk sends the `modified` it read and the route compares it first.
STALE_CHECKED_METHODS = (*OVERRIDABLE_METHODS, "queue_submit", "queue_cancel")

PERMISSION_MAP = {
	"GET": "read",
	"POST": "write",
	"QUERY": "read",
}


def handle_rpc_call(method: str, doctype: str | None = None):
	from frappe.modules.utils import load_doctype_module

	if doctype:
		# Expand to run actual method from doctype controller
		module = load_doctype_module(doctype)
		method = module.__name__ + "." + method

	method = frappe.override_whitelisted_method(method)

	# via server script
	server_script = get_server_script_map().get("_api", {}).get(method)
	if server_script:
		return run_server_script(server_script)

	method = resolve_method(method)

	is_whitelisted(method)
	is_valid_http_method(method)

	return frappe.call(method, **frappe.form_dict)


def login():
	"""Login happens implicitly, this function doesn't do anything."""
	pass


def logout():
	frappe.local.login_manager.logout()
	frappe.db.commit()


def get_session() -> dict[str, Any]:
	"""
	GET /api/v2/session

	REST API endpoint for the signed-in person and the site settings a client renders for them

	Args:
		None

	Response:
		frappe.response["data"]: dict with the keys `user` (name, full_name, email, user_image),
			`roles`, `lang`, `timezone` and `defaults`, which is empty for anyone but a System User.
			A Guest gets a Guest body, never a 403.
	"""
	from frappe.sessions import get_session_info

	return get_session_info()


def read_doc(doctype: str, name: str):
	"""
	GET /api/v2/document/<doctype>/<name>?fields=[...]

	Query Parameters (accessible via frappe.form_dict):
		fields: JSON string of field names to return; a table field as
		        {"<table field>": ["<child field>", ...]}, as for the list. Default: all.
	"""
	fields: list | None = frappe.parse_json(frappe.form_dict.get("fields", None))
	if fields and not isinstance(fields, list):
		raise FrappeValueError("'fields' must be a list")

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	add_document_parts(doc, parse_include(frappe.form_dict.get("include")))
	_doc = doc.as_dict()

	for key in _doc:
		df = doc.meta.get_field(key)
		if df and df.fieldtype == "Link" and isinstance(_doc.get(key), int):
			_doc[key] = cstr(_doc.get(key))

	return select_fields(_doc, fields) if fields else _doc


def select_fields(doc: dict, fields: list) -> dict:
	"""Pick `fields` from a document dict. Like the list, fields the dict does not have are left out."""
	selected = dict(doc) if "*" in fields else {}
	for field in fields:
		if isinstance(field, dict):
			for fieldname, child_fields in field.items():
				if not isinstance(child_fields, list):
					raise FrappeValueError(f"Fields for '{fieldname}' must be a list")
				if isinstance(rows := doc.get(fieldname), list):
					selected[fieldname] = [select_fields(row, child_fields) for row in rows]
		elif not isinstance(field, str) or not (field == "*" or field.isidentifier()):
			raise FrappeValueError(f"Invalid field for a document: {field}")
		elif field in doc:
			selected[field] = doc[field]
	return selected


def document_list(doctype: str) -> list[dict[str, Any]]:
	"""
	GET /api/v2/document/<doctype>?fields=[...],filters={...},...

	REST API endpoint for fetching doctype records

	Args:
		doctype: DocType name

	Query Parameters (accessible via frappe.form_dict):
		fields: JSON string of field names to fetch
		filters: JSON string of filters to apply
		order_by: Order by field
		start: Starting offset for pagination (default: 0)
		limit: Maximum number of records to fetch (default: 20)
		group_by: Group by field
		as_dict: Return results as dictionary (default: True)
		include: Comma-separated parts to add beside the list: `count`, `favourites` (the page's
			rows the session user starred), `users` (names of the `_assign`/`_liked_by` users),
			`comment_counts` (comments per row of the page) and `tag_colors` (the stored colour of
			each tag in `_user_tags`)

	Response:
		frappe.response["data"]: List of document records as dicts
		frappe.response["has_next_page"]: Indicates if more pages are available
		frappe.response["count"], ["count_capped"]: With include=count, the row count under the
			same filters, reported as frappe.api.include.COUNT_CAP with count_capped when more
			rows than that match; None when the count timed out

	Controller Customization:
		Doctype controllers can customize queries by implementing a static get_list(query) method
		that receives a QueryBuilder object and returns a modified QueryBuilder.
		Virtual DocTypes are listed through their own get_list, as frappe.get_list does.

		Example:
			class Project(Document):
				@staticmethod
				def get_list(query):
					Project = frappe.qb.DocType("Project")
					if user_has_role("Project Owner"):
						query = query.where(Project.owner == frappe.session.user)
					else:
						query = query.where(Project.is_private == 0)
					return query
	"""
	args = frappe.form_dict
	fields: list | None = frappe.parse_json(args.get("fields", None))
	filters: dict | None = frappe.parse_json(args.get("filters", None))
	or_filters: dict | None = frappe.parse_json(args.get("or_filters", None))
	order_by: str | None = args.get("order_by", DefaultOrderBy)
	start: int = cint(args.get("start", 0))
	limit: int = cint(args.get("limit", 20))
	group_by: str | None = args.get("group_by", None)
	debug: bool = bool(args.get("debug", False))
	as_dict: bool = bool(args.get("as_dict", True))

	if fields and not isinstance(fields, list):
		raise FrappeValueError("'fields' must be a list")
	if filters and not isinstance(filters, (list, dict)):
		raise FrappeValueError("'filters' must be a list or dictionary")
	if or_filters and not isinstance(or_filters, (list, dict)):
		raise FrappeValueError("'or_filters' must be a list or dictionary")
	if order_by and not isinstance(order_by, str):
		raise FrappeValueError("'order_by' must be a string")
	if group_by and not isinstance(group_by, str):
		raise FrappeValueError("'group_by' must be a string")

	include = parse_include(args.get("include"))
	add_list_parts(doctype, include, filters, or_filters, group_by)

	if is_virtual_doctype(doctype):
		data = frappe.get_list(
			doctype,
			fields=fields,
			filters=filters,
			order_by=order_by,
			start=start,
			limit=limit + 1,
			group_by=group_by,
			as_list=not as_dict,
		)
		frappe.response["has_next_page"] = len(data) > limit
		data = data[:limit]
		add_row_parts(doctype, include, data)
		return data

	query = frappe.qb.get_query(
		table=doctype,
		fields=fields,
		filters=filters,
		or_filters=or_filters,
		order_by=order_by,
		offset=start,
		limit=limit + 1,  # Fetch one extra to check if there's a next page
		group_by=group_by,
		ignore_permissions=False,
	)

	query = apply_controller_get_list(doctype, query)

	data = query.run(as_dict=as_dict, debug=debug, as_list=not as_dict)
	frappe.response["has_next_page"] = len(data) > limit
	data = data[:limit]
	add_row_parts(doctype, include, data)
	return data


def count(doctype: str) -> int:
	from frappe.desk.reportview import get_count

	frappe.form_dict.doctype = doctype

	return get_count()


def search(doctype: str):
	"""
	GET /api/v2/doctype/<doctype>/search?txt=...

	The link-field search: the same rows `frappe.desk.search.search_link` returns, as
	`data: [{value, label, description}]`.

	Query Parameters:
		txt: The text to match
		filters: JSON filters on the searched doctype
		reference_doctype: The doctype the link field sits on
		query: A whitelisted custom search method
		limit: Rows per page (10 when absent or below 1)
		start: Row offset (default: 0)
	"""
	from frappe.desk.search import build_for_autosuggest, search_widget

	# search_widget skips the permission check for DocType, so a Guest would get every name
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Sign in to search"))

	args = frappe.form_dict
	# a zero limit would mean no limit at all in get_list
	page_length = cint(args.get("limit"))
	if page_length < 1:
		page_length = SEARCH_PAGE_LENGTH

	results = search_widget(
		doctype,
		cstr(args.get("txt")).strip(),
		args.get("query") or None,
		start=cint(args.get("start", 0)),
		page_length=page_length,
		filters=args.get("filters") or None,
		reference_doctype=args.get("reference_doctype") or None,
	)
	# the same Cache-Control that search_link's @http_cache sends; it keys on the v1 path, so it
	# does not fire for this route
	frappe.local.response_headers.set("Cache-Control", "private,max-age=60,stale-while-revalidate=300")
	return build_for_autosuggest(results, doctype=doctype)


def create_doc(doctype: str):
	data = frappe.form_dict
	data.pop("doctype", None)

	doc = frappe.new_doc(doctype, **data)
	desk_v2 = is_desk_v2_enabled()
	doc.flags.attach_text_editor_files = desk_v2
	doc.flags.flat_values_as_rows = desk_v2

	if (name := data.get("name")) and isinstance(name, str | int):
		doc.flags.name_set = True

	return doc.insert().copy_with_fieldlevel_read_permissions().as_dict()


def copy_doc(doctype: str, name: str, ignore_no_copy: bool = True, amend: bool = False):
	"""Return a clean copy of the given document that can be modified and posted as a new document.

	With `amend`, the copy is the draft amendment of a cancelled document, as desk v1 builds it.
	"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()

	copy = frappe.copy_doc(doc, ignore_no_copy=ignore_no_copy)
	if amend:
		check_amendable(doc)
		copy.amended_from = doc.name
		if frappe.get_meta(doctype).has_field("amendment_date"):
			copy.amendment_date = frappe.utils.today()

	return copy.as_dict(no_private_properties=True, no_nulls=True)


def check_amendable(doc):
	doc.check_permission("amend")
	title = _("Amendment Not Allowed")
	if not frappe.get_meta(doc.doctype).has_field("amended_from"):
		frappe.throw(_('"amended_from" field must be present to do an amendment.'), title=title)
	if doc.docstatus != 2:
		frappe.throw(_("{0} cannot be amended because it is not cancelled.").format(doc.name), title=title)
	if frappe.client.is_document_amended(doc.doctype, doc.name):
		frappe.throw(_("This document is already amended, you cannot amend it again"), title=title)


def update_doc(doctype: str, name: str):
	data = frappe.form_dict

	doc = frappe.get_doc(doctype, name, for_update=True)
	doc.check_permission("write")
	data.pop("flags", None)
	doc.update(data)
	doc.flags.attach_text_editor_files = is_desk_v2_enabled()
	doc.save()

	# check for child table doctype
	if doc.get("parenttype"):
		frappe.get_doc(doc.parenttype, doc.parent).save()

	return doc.copy_with_fieldlevel_read_permissions().as_dict()


def delete_doc(doctype: str, name: str):
	frappe.client.delete_doc(doctype, name)
	frappe.response.http_status_code = 202
	return "ok"


def get_meta(doctype: str):
	frappe.only_for("All")
	add_meta_parts(doctype, parse_include(frappe.form_dict.get("include")))
	meta = serialize_meta(frappe.get_meta(doctype))
	return {
		**meta,
		"workflow_state_field": get_doctype_state_field(doctype),
		"workflow_state_styles": get_workflow_state_styles(doctype),
	}


def replace_with_masked(result, doc, masked):
	"""Swap the document and its child rows in a method's result for those of its masked copy."""
	if masked is doc:
		return result

	masked_for = {id(doc): masked}
	for fieldname in doc._non_computed_table_fieldnames:
		masked_for.update(
			(id(row), m)
			for row, m in zip(doc.get(fieldname) or [], masked.get(fieldname) or [], strict=False)
		)

	def swap(value):
		if id(value) in masked_for:
			return masked_for[id(value)]
		if type(value) in (list, tuple):
			return type(value)(swap(v) for v in value)
		if type(value) in (dict, frappe._dict):
			return type(value)((k, swap(v)) for k, v in value.items())
		return value

	return swap(result)


def execute_doc_method(doctype: str, name: str, method: str | None = None):
	"""Get a document from DB and execute method on it.

	Use cases:
	- Submitting/cancelling document
	- Triggering some kind of update on a document
	"""
	method = method or frappe.form_dict.pop("run_method")
	doc = frappe.get_doc(doctype, name)
	fn = whitelisted_doc_function(doc, method)
	is_valid_http_method(fn)

	assert frappe.request.method in PERMISSION_MAP, (
		"execute_doc_method route is only mounted for GET/POST/QUERY"
	)
	doc.check_permission(PERMISSION_MAP[frappe.request.method])
	if method in STALE_CHECKED_METHODS:
		doc.check_not_stale(frappe.form_dict.pop("modified", None))
	result = doc.run_method(method, **frappe.form_dict)
	masked = doc.copy_with_fieldlevel_read_permissions()
	frappe.response.docs.append(masked.as_dict())
	return replace_with_masked(result, doc, masked)


def whitelisted_doc_function(doc: Document, method: str):
	"""Return the function whose whitelist entry covers `method`, or raise.

	An undecorated override of `Document.submit`/`cancel` shares the base method's entry, so the override runs.
	"""
	fn = getattr(getattr(doc, method, None), "__func__", None) if method in OVERRIDABLE_METHODS else None
	if fn and fn is getattr(type(doc), method) and fn not in frappe.whitelisted:
		base = getattr(Document, method)
		is_whitelisted(base)
		app_name = fn.__module__.split(".", 1)[0]
		if app_name in get_disabled_apps():
			frappe.throw(_("App {0} is disabled on this site").format(app_name), AppDisabledError)
		# The override runs before save() checks this right, and ERPNext's locks and queues the document first.
		doc.check_permission(method)
		return base

	doc.is_whitelisted(method)
	method_obj = getattr(doc, method)
	return getattr(method_obj, "__func__", method_obj)


def run_doc_method(method: str, document: dict[str, Any] | str, kwargs=None):
	"""run a whitelisted controller method on in-memory document.


	This is useful for building clients that don't necessarily encode all the business logic but
	call server side function on object to validate and modify the doc.

	The doc CAN exists in DB too and can write to DB as well if method is POST.
	"""

	if isinstance(document, str):
		document = frappe.parse_json(document)

	if not isinstance(document, dict):
		raise FrappeValueError("'document' must be a dictionary")

	if kwargs is None:
		kwargs = {}

	assert frappe.request.method in PERMISSION_MAP, "run_doc_method route is only mounted for GET/POST/QUERY"
	doc = frappe.get_doc(document)
	ptype = PERMISSION_MAP[frappe.request.method]
	# unsaved docs need create, not write; `__islocal` comes from the client, so check the DB too
	# (a Single always exists, whatever name the client sends)
	if (
		ptype == "write"
		and doc.is_new()
		and not doc.meta.issingle
		and not frappe.db.exists(doc.doctype, doc.name)
	):
		ptype = "create"
	doc.check_permission(ptype)
	doc._original_modified = doc.modified
	doc.check_if_latest()

	method_obj = getattr(doc, method)
	fn = getattr(method_obj, "__func__", method_obj)
	is_whitelisted(fn)
	is_valid_http_method(fn)

	new_kwargs = get_newargs(fn, kwargs)
	response = doc.run_method(method, **new_kwargs)
	masked = doc.copy_with_fieldlevel_read_permissions()
	frappe.response.docs.append(masked)  # send modified document and result both.
	return replace_with_masked(response, doc, masked)


def collaboration_rules() -> list[Rule]:
	# only a literal part segment beats the greedy `<path:name>`
	rules = []
	for part in collaboration.ADD:
		path = f"/document/<doctype>/<path:name>/{part}"
		add = partial(collaboration.add, part=part)
		remove = partial(collaboration.remove, part=part)
		update = partial(collaboration.update, part=part)
		rules.append(Rule(path, methods=["POST"], endpoint=add))
		rules.append(Rule(path, methods=["DELETE"], endpoint=remove))
		rules.append(Rule(f"{path}/<path:key>", methods=["DELETE"], endpoint=remove))
		rules.append(Rule(f"{path}/<path:key>", methods=["PATCH"], endpoint=update))
	return rules


url_rules = [
	Rule("/mcp", methods=["POST", "GET", "DELETE"], endpoint=handle_mcp),
	# Discovery APIs
	Rule("/discovery", methods=["GET"], endpoint=discovery.root),
	Rule(
		"/discovery/search",
		methods=["GET"],
		endpoint=lambda: discovery.search(frappe.form_dict.get("q")),
	),
	Rule("/discovery/method", methods=["GET"], endpoint=discovery.methods),
	Rule("/discovery/method/<method>", methods=["GET"], endpoint=discovery.method),
	Rule("/discovery/doctype/<doctype>", methods=["GET"], endpoint=discovery.doctype_methods),
	Rule(
		"/discovery/doctype/<doctype>/method/<method>",
		methods=["GET"],
		endpoint=discovery.doctype_method,
	),
	# Session
	Rule("/session", methods=["GET"], endpoint=get_session),
	# RPC calls
	Rule("/method/login", endpoint=login),
	Rule("/method/logout", endpoint=logout, methods=["POST"]),
	Rule("/method/ping", endpoint=frappe.ping),
	Rule("/method/upload_file", endpoint=upload_file, methods=["POST"]),
	Rule("/method/bulk_delete", endpoint=bulk_actions.bulk_delete, methods=["POST"]),
	Rule("/method/bulk_update", endpoint=bulk_actions.bulk_update, methods=["POST"]),
	Rule("/method/<method>", endpoint=handle_rpc_call),
	Rule(
		"/method/run_doc_method",
		methods=["GET", "POST", "QUERY"],
		endpoint=lambda: frappe.call(run_doc_method, **frappe.form_dict),
	),
	Rule("/method/<doctype>/<method>", endpoint=handle_rpc_call),
	# Document level APIs
	Rule("/document/<doctype>", methods=["GET", "QUERY"], endpoint=document_list),
	Rule("/document/<doctype>", methods=["POST"], endpoint=create_doc),
	# a static rule beats the dynamic one, so an upload of bytes never reaches `create_doc`
	Rule("/document/File", methods=["POST"], endpoint=files.create_file),
	Rule("/document/<doctype>/bulk_delete", methods=["POST"], endpoint=bulk_actions.bulk_delete_docs),
	Rule("/document/<doctype>/bulk_update", methods=["POST"], endpoint=bulk_actions.bulk_update_docs),
	Rule(
		"/document/<doctype>/bulk_assignments", methods=["POST"], endpoint=bulk_collaboration.bulk_assignments
	),
	Rule(
		"/document/<doctype>/bulk_assignments",
		methods=["DELETE"],
		endpoint=bulk_collaboration.bulk_clear_assignments,
	),
	Rule(
		"/document/<doctype>/bulk_assignment_rule",
		methods=["POST"],
		endpoint=bulk_collaboration.bulk_assignment_rule,
	),
	Rule("/document/<doctype>/bulk_tags", methods=["POST"], endpoint=bulk_collaboration.bulk_tags),
	Rule("/document/<doctype>/bulk_tags", methods=["DELETE"], endpoint=bulk_collaboration.bulk_remove_tags),
	Rule("/document/<doctype>/bulk_follows", methods=["POST"], endpoint=bulk_collaboration.bulk_follows),
	Rule("/document/<doctype>/bulk_follows", methods=["DELETE"], endpoint=bulk_collaboration.bulk_unfollows),
	Rule("/document/<doctype>/bulk_shares", methods=["POST"], endpoint=bulk_collaboration.bulk_shares),
	Rule("/document/<doctype>/bulk_seen", methods=["POST"], endpoint=bulk_collaboration.bulk_seen),
	Rule("/document/<doctype>/bulk_seen", methods=["DELETE"], endpoint=bulk_collaboration.bulk_unseen),
	Rule("/document/<doctype>/bulk_print", methods=["POST"], endpoint=bulk_actions.bulk_print_docs),
	Rule("/document/<doctype>/bulk_call", methods=["POST"], endpoint=bulk_actions.bulk_call_docs),
	Rule("/document/<doctype>/bulk_submit", methods=["POST"], endpoint=bulk_actions.bulk_submit_docs),
	Rule("/document/<doctype>/bulk_cancel", methods=["POST"], endpoint=bulk_actions.bulk_cancel_docs),
	Rule("/document/<doctype>/bulk_workflow", methods=["POST"], endpoint=bulk_actions.bulk_workflow_docs),
	Rule(
		"/document/<doctype>/bulk_workflow_actions",
		methods=["POST"],
		endpoint=bulk_actions.bulk_workflow_actions,
	),
	Rule("/document/<doctype>/<path:name>/", methods=["GET"], endpoint=read_doc),
	Rule(
		"/document/<doctype>/<path:name>/copy",
		methods=["GET"],
		endpoint=lambda doctype, name: copy_doc(
			doctype, name, amend=bool(cint(frappe.form_dict.get("amend")))
		),
	),
	Rule("/document/<doctype>/<path:name>/", methods=["PATCH", "PUT"], endpoint=update_doc),
	Rule("/document/<doctype>/<path:name>/", methods=["DELETE"], endpoint=delete_doc),
	Rule(
		"/document/<doctype>/<path:name>/method/<method>/",
		methods=["GET", "POST", "QUERY"],
		endpoint=execute_doc_method,
	),
	*collaboration_rules(),
	Rule("/document/<doctype>/<path:name>/activity", methods=["GET"], endpoint=activity.read),
	Rule("/document/<doctype>/<path:name>/attachments", methods=["POST"], endpoint=files.attach),
	Rule(
		"/document/<doctype>/<path:name>/attachments/<path:file_name>",
		methods=["DELETE"],
		endpoint=files.detach,
	),
	# Collection level APIs
	Rule("/doctype/<doctype>/meta", methods=["GET"], endpoint=get_meta),
	Rule("/doctype/<doctype>/count", methods=["GET", "QUERY"], endpoint=count),
	Rule("/doctype/<doctype>/search", methods=["GET"], endpoint=search),
]
