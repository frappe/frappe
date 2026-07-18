# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public document API — CRUD and related operations on documents.

This is the canonical integration/RPC surface for working with documents,
mapped to `/api/method/frappe.core.api.document.*`. Requests to the
`/api/resource` REST routes and via FrappeClient are also handled here.

Endpoints were consolidated from `frappe.client` (which remains as a
permanent alias module), `frappe.model.document`, `frappe.model.rename_doc`,
`frappe.model.mapper` and `frappe.share`.
"""

from types import NoneType
from typing import TYPE_CHECKING, Any

import frappe
import frappe.model
import frappe.utils
from frappe import _
from frappe.desk.reportview import validate_args
from frappe.desk.search import PAGE_LENGTH_FOR_LINK_VALIDATION, search_widget
from frappe.model.document import Document
from frappe.public_api import public
from frappe.utils import attach_expanded_links, get_safe_filters
from frappe.utils.caching import http_cache
from frappe.utils.data import sbool
from frappe.utils.scheduler import is_scheduler_inactive

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File


@public(group="Documents")
@frappe.whitelist()
def get_list(
	doctype: str,
	fields: str | list[str | dict[str, Any]] | None = None,
	filters: str | list | dict[str, Any] | None = None,
	group_by: str | list[str] | None = None,
	order_by: str | list[str] | None = None,
	limit_start: int | str | None = None,
	limit_page_length: int | str = 20,
	parent: str | None = None,
	debug: bool | int = False,
	as_dict: bool | int = True,
	or_filters: str | list[list] | dict[str, Any] | None = None,
	expand: str | list[str] | None = None,
) -> list:
	"""Return a list of records by filters, fields, ordering and limit.

	:param doctype: DocType of the data to be queried
	:param fields: fields to be returned. Default is `name`
	:param filters: filter list by this dict
	:param group_by: group results by this fieldname
	:param order_by: Order by this fieldname
	:param limit_start: Start at this index
	:param limit_page_length: Number of records to be returned (default 20)
	:param parent: parent DocType if `doctype` is a child table
	:param debug: log the executed query
	:param as_dict: return records as dicts instead of lists of values
	:param or_filters: filters combined with OR instead of AND
	:param expand: link fields to be expanded into the linked document's data
	:return: List of records, each a dict (or a list of values if `as_dict` is falsy).
	"""

	args = frappe._dict(
		doctype=doctype,
		parent_doctype=parent,
		fields=fields,
		filters=filters,
		or_filters=or_filters,
		group_by=group_by,
		order_by=order_by,
		limit_start=limit_start,
		limit_page_length=limit_page_length,
		debug=debug,
		as_list=not as_dict,
	)

	validate_args(args)
	_list = frappe.get_list(**args)

	if not expand:
		return _list

	if fields and not fields[0] == "*":
		expand = [f for f in expand if f in fields]

	attach_expanded_links(doctype, _list, expand)

	return _list


@public(group="Documents")
@frappe.whitelist()
def get_count(
	doctype: str,
	filters: str | list | dict[str, Any] | None = None,
	debug: int | bool = False,
	cache: int | bool = False,
) -> int:
	"""Return the number of records that match the given filters.

	:param doctype: DocType of the data to be counted
	:param filters: filter by this dict
	:param debug: log the executed query
	:param cache: allow returning a cached count
	:return: Number of matching records.
	"""
	from frappe.desk.reportview import get_count

	frappe.form_dict.doctype = doctype
	frappe.form_dict.filters = get_safe_filters(filters)
	frappe.form_dict.debug = debug

	return get_count()


@public(group="Documents")
@frappe.whitelist()
def get(
	doctype: str,
	name: str | int | None = None,
	filters: str | list | dict[str, Any] | None = None,
	parent: str | None = None,
) -> dict[str, Any]:
	"""Return a document by name or filters.

	:param doctype: DocType of the document to be returned
	:param name: return document of this `name`
	:param filters: If name is not set, filter by these values and return the first match
	:param parent: parent DocType if `doctype` is a child table
	:return: The document as a dict.
	"""

	if name:
		doc = frappe.get_doc(doctype, name)
	elif filters or filters == {}:
		doc = frappe.get_doc(doctype, frappe.parse_json(filters))
	else:
		doc = frappe.get_doc(doctype)  # single

	doc.check_permission()
	doc.apply_fieldlevel_read_permissions()

	return doc.as_dict(no_nulls=True)


@public(group="Documents")
@frappe.whitelist()
def get_value(
	doctype: str,
	fieldname: str | list[str] | dict[str, Any],
	filters: str | list | dict[str, Any] | None = None,
	as_dict: int | bool = True,
	debug: int | bool = False,
	parent: str | None = None,
) -> Any:
	"""Return a value from a document.

	:param doctype: DocType to be queried
	:param fieldname: Field to be returned (default `name`)
	:param filters: dict or string for identifying the record
	:param as_dict: return values as a dict keyed by fieldname
	:param debug: log the executed query
	:param parent: parent DocType if `doctype` is a child table
	:return: The requested value(s) — a dict if `as_dict`, else a bare value or list of values.
	"""

	if not frappe.has_permission(doctype, parent_doctype=parent):
		frappe.throw(_("No permission for {0}").format(_(doctype)), frappe.PermissionError)

	filters = get_safe_filters(filters)
	if isinstance(filters, str):
		filters = {"name": filters}

	try:
		fields = frappe.parse_json(fieldname)
	except (TypeError, ValueError):
		# name passed, not json
		fields = [fieldname]

	# check whether the used filters were really parseable and usable
	# and did not just result in an empty string or dict
	if not filters:
		filters = None

	if frappe.get_meta(doctype).issingle:
		value = frappe.db.get_values_from_single(fields, filters, doctype, as_dict=as_dict, debug=debug)
	else:
		value = get_list(
			doctype,
			filters=filters,
			fields=fields,
			debug=debug,
			limit_page_length=1,
			parent=parent,
			as_dict=as_dict,
		)

	if as_dict:
		return value[0] if value else {}

	if not value:
		return

	return value[0] if len(fields) > 1 else value[0][0]


@public(group="Documents")
@frappe.whitelist()
def get_single_value(doctype: str, field: str) -> Any:
	"""Return a field value from a Single doctype.

	:param doctype: Single DocType to be queried
	:param field: field to be returned
	:return: The field's value.
	"""
	if not frappe.has_permission(doctype):
		frappe.throw(_("No permission for {0}").format(_(doctype)), frappe.PermissionError)

	return frappe.db.get_single_value(doctype, field)


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def set_value(
	doctype: str, name: str | int, fieldname: str | dict[str, Any], value: Any | None = None
) -> dict[str, Any]:
	"""Set a value in a document, or a group of values.

	:param doctype: DocType of the document
	:param name: name of the document
	:param fieldname: fieldname string or JSON / dict with key value pair
	:param value: value if fieldname is JSON / dict
	:return: The saved document (the parent document if `doctype` is a child table) as a dict.
	"""

	values = {}
	if value is None:
		values = fieldname
		if isinstance(fieldname, str):
			try:
				values = frappe.parse_json(fieldname)
			except ValueError:
				values = {fieldname: ""}
	else:
		values = {fieldname: value}

	forbidden = set(frappe.model.default_fields + frappe.model.child_table_fields)

	# In whole-doc payloads, framework-managed fields are incidental (e.g. name,
	# owner, creation, idx echoed back), so strip them instead of failing.
	# throws if only editing framework-managed fields
	editable = {field: val for field, val in values.items() if field not in forbidden}
	if values and not editable:
		frappe.throw(_("Cannot edit standard fields"))

	values = editable

	# check for child table doctype
	if not frappe.get_meta(doctype).istable:
		doc = frappe.get_doc(doctype, name)
		doc.update(values)
	else:
		doc = frappe.db.get_value(doctype, name, ["parenttype", "parent"], as_dict=True)
		doc = frappe.get_doc(doc.parenttype, doc.parent)
		child = doc.getone({"doctype": doctype, "name": name})
		child.update(values)

	doc.save()

	return doc.as_dict()


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def insert(doc: str | dict[str, Any] | None = None) -> dict[str, Any]:
	"""Insert a document.

	:param doc: JSON or dict object to be inserted
	:return: The inserted document (the parent document if `doc` is a child record) as a dict.
	"""
	doc = frappe.parse_json(doc)

	return insert_doc(doc).as_dict()


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def insert_many(docs: str | list[dict[str, Any]] | None = None) -> list[str]:
	"""Insert multiple documents.

	:param docs: JSON or list of dict objects to be inserted in one request
	:return: Names of the inserted documents.
	"""
	docs = frappe.parse_json(docs)

	if len(docs) > 200:
		frappe.throw(_("Only 200 inserts allowed in one request"))

	return [insert_doc(doc).name for doc in docs]


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def save(doc: str | dict[str, Any]) -> dict[str, Any]:
	"""Update (save) an existing document.

	:param doc: JSON or dict object with the properties of the document to be updated
	:return: The saved document as a dict.
	"""
	doc = frappe.parse_json(doc)

	doc = frappe.get_doc(doc)
	doc.save()

	return doc.as_dict()


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def rename_doc(doctype: str, old_name: str | int, new_name: str | int, merge: bool = False) -> str:
	"""Rename a document.

	:param doctype: DocType of the document to be renamed
	:param old_name: Current `name` of the document to be renamed
	:param new_name: New `name` to be set
	:param merge: merge into an existing document of name `new_name`
	:return: The new name of the document.
	"""
	new_name = frappe.rename_doc(doctype, old_name, new_name, merge=merge)
	return new_name


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def submit(doc: str | dict[str, Any]) -> dict[str, Any]:
	"""Submit a document.

	:param doc: JSON or dict object to be submitted remotely
	:return: The submitted document as a dict.
	"""
	doc = frappe.parse_json(doc)

	doc = frappe.get_doc(doc)
	doc.submit()

	return doc.as_dict()


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def cancel(doctype: str, name: str | int) -> dict[str, Any]:
	"""Cancel a submitted document.

	:param doctype: DocType of the document to be cancelled
	:param name: name of the document to be cancelled
	:return: The cancelled document as a dict.
	"""
	wrapper = frappe.get_doc(doctype, name)
	wrapper.cancel()

	return wrapper.as_dict()


@public(group="Documents")
@frappe.whitelist(methods=["DELETE", "POST"])
def delete(doctype: str, name: str | int) -> None:
	"""Delete a document.

	:param doctype: DocType of the document to be deleted
	:param name: name of the document to be deleted
	"""
	delete_doc(doctype, name)


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def bulk_update(docs: str | list) -> dict[str, list]:
	"""Bulk update documents.

	:param docs: JSON list of documents to be updated remotely. Each document must have `docname` property
	:return: Dict with `failed_docs` — the documents that could not be updated, with tracebacks.
	"""
	docs = frappe.parse_json(docs)
	failed_docs = []
	for doc in docs:
		doc.pop("flags", None)
		try:
			existing_doc = frappe.get_doc(doc["doctype"], doc["docname"])
			existing_doc.update(doc)
			existing_doc.save()
		except Exception:
			failed_docs.append({"doc": doc, "exc": frappe.utils.get_traceback()})

	return {"failed_docs": failed_docs}


@public(group="Documents")
@frappe.whitelist()
def has_permission(doctype: str, docname: str | int, perm_type: str = "read") -> dict[str, bool]:
	"""Return a JSON with data whether the document has the requested permission.

	:param doctype: DocType of the document to be checked
	:param docname: `name` of the document to be checked
	:param perm_type: one of `read`, `write`, `create`, `submit`, `cancel`, `report`. Default is `read`
	:return: Dict with a single `has_permission` boolean.
	"""
	# perm_type can be one of read, write, create, submit, cancel, report
	return {"has_permission": frappe.has_permission(doctype, perm_type.lower(), docname)}


@public(group="Documents")
@frappe.whitelist()
def get_doc_permissions(doctype: str, docname: str | int) -> dict[str, dict]:
	"""Return an evaluated document permissions dict like `{"read":1, "write":1}`.

	:param doctype: DocType of the document to be evaluated
	:param docname: `name` of the document to be evaluated
	:return: Dict with a single `permissions` dict.
	"""
	doc = frappe.get_lazy_doc(doctype, docname)
	return {"permissions": frappe.permissions.get_doc_permissions(doc)}


@public(group="Documents")
@frappe.whitelist()
def get_password(doctype: str, name: str | int, fieldname: str) -> str | None:
	"""Return a password type property. Only applicable for System Managers.

	:param doctype: DocType of the document that holds the password
	:param name: `name` of the document that holds the password
	:param fieldname: `fieldname` of the password property
	:return: The decrypted password.
	"""
	frappe.only_for("System Manager")
	return frappe.get_lazy_doc(doctype, name).get_password(fieldname)


@public(group="Documents")
@frappe.whitelist(methods=["POST", "PUT"])
def attach_file(
	filename: str | None = None,
	filedata: str | None = None,
	doctype: str | None = None,
	docname: str | int | None = None,
	folder: str | None = None,
	decode_base64: int | bool = False,
	is_private: int | bool | None = None,
	docfield: str | None = None,
) -> "File":
	"""Attach a file to a document.

	:param filename: filename e.g. test-file.txt
	:param filedata: base64 encode filedata which must be urlencoded
	:param doctype: Reference DocType to attach file to
	:param docname: Reference DocName to attach file to
	:param folder: Folder to add File into
	:param decode_base64: decode filedata from base64 encode, default is False
	:param is_private: Attach file as private file (1 or 0)
	:param docfield: file to attach to (optional)
	:return: The created File document.
	"""

	doc = frappe.get_lazy_doc(doctype, docname, check_permission=True)

	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
			"attached_to_field": docfield,
			"folder": folder,
			"is_private": is_private,
			"content": filedata,
			"decode": decode_base64,
		}
	).save()

	if docfield and doctype:
		doc.set(docfield, file.file_url)
		doc.save()

	return file


@public(group="Documents")
@frappe.whitelist()
@http_cache(max_age=10 * 60)
def is_document_amended(doctype: str, docname: str | int) -> str | bool | None:
	"""Check whether an amended version of the given document exists.

	:param doctype: DocType of the document to be checked
	:param docname: `name` of the document to be checked
	:return: Name of the amending document if one exists, falsy otherwise.
	"""
	if frappe.permissions.has_permission(doctype):
		try:
			return frappe.db.exists(doctype, {"amended_from": docname})
		except frappe.db.InternalError:
			pass

	return False


@public(group="Documents")
@frappe.whitelist(methods=["GET", "POST"])
def validate_link_and_fetch(
	doctype: str,
	docname: str | int,
	fields_to_fetch: list[str] | str | None = None,
	# search_widget parameters
	query: str | None = None,
	filters: dict | list | str | None = None,
	**search_args: Any,
) -> dict[str, Any]:
	"""Validate that a link field value points to an accessible document and fetch fields from it.

	Respects link filters and custom link queries in addition to standard
	permission checks, so a value is only considered valid if it would also
	appear in the link field's search results.

	:param doctype: DocType the link points to
	:param docname: value of the link to be validated
	:param fields_to_fetch: fields to fetch from the linked document
	:param query: custom link query (`frappe.link_search` style) used by the link field
	:param filters: filters applied by the link field
	:param search_args: additional arguments forwarded to the link search
	:return: Dict with `name` and the fetched fields; empty if the link is invalid or inaccessible.
	"""
	if not docname:
		frappe.throw(_("Document Name must not be empty"))

	meta = frappe.get_meta(doctype)
	fields_to_fetch = frappe.parse_json(fields_to_fetch)

	# only cache is no fields to fetch and request is GET
	can_cache = not fields_to_fetch and frappe.request.method == "GET"

	# Use search_widget to validate - ensures filters/custom queries are respected
	# in addition to standard permission checks
	# we match the exact docname for non-custom queries and rely on txt for custom queries
	search_args.update(
		as_dict=False,
		# when relying on txt (custom queries), we want to match "A" with "A" only and not "A1", "BA" etc.
		# so we set page_length to a conservative value within which exact match is expected to appear
		page_length=PAGE_LENGTH_FOR_LINK_VALIDATION,
		# translated doctypes are expected to be searchable with translated values, even for custom queries
		# for non-custom queries, docname is always matched exactly so we don't translate it
		txt=_(docname) if (query and meta.translated_doctype) else docname,
		for_link_validation=True,
	)

	search_result = frappe.call(
		search_widget,
		doctype=doctype,
		query=query,
		filters=filters,
		**search_args,
	)

	if not search_result:
		return {}  # Either the record does not exist or was excluded by link_filters

	values = None
	is_virtual_dt = bool(meta.get("is_virtual"))
	if is_virtual_dt:
		try:
			doc = frappe.get_doc(doctype, docname)
			doc.check_permission("select")
			values = {"name": doc.name}

		except frappe.DoesNotExistError:
			frappe.clear_last_message()
	else:
		# get value in the right case and type (str | int)
		# for matching with search result
		columns_to_fetch = ["name"]
		if frappe.is_table(doctype):
			columns_to_fetch.append("parenttype")  # for child table permission check
		values = frappe.db.get_value(doctype, docname, columns_to_fetch, as_dict=True)

	if not values:
		return {}  # does not exist

	name_to_compare = values["name"]
	# this will be used to fetch fields later
	parent_doctype = values.pop("parenttype", None)

	# try to match name in search result
	# if search_result is large, assume valid link (result may not appear in some custom queries)
	if len(search_result) < PAGE_LENGTH_FOR_LINK_VALIDATION and not any(
		item[0] == name_to_compare for item in search_result
	):
		return {}  # no permission or filtered out

	# don't cache or fetch for virtual doctypes
	if is_virtual_dt:
		return values

	if not fields_to_fetch:
		if can_cache:
			frappe.local.response_headers.set(
				"Cache-Control", "private,max-age=1800,stale-while-revalidate=7200"
			)
		return values

	try:
		values.update(get_value(doctype, fields_to_fetch, docname, parent=parent_doctype))
	except frappe.PermissionError:
		frappe.clear_last_message()
		frappe.msgprint(
			_("You need {0} permission to fetch values from {1} {2}").format(
				frappe.bold(_("Read")), frappe.bold(doctype), frappe.bold(docname)
			),
			title=_("Cannot Fetch Values"),
			indicator="orange",
		)

	return values


@public(group="Documents")
@frappe.whitelist()
def unlock_document(doctype: str, name: str) -> None:
	"""Release the document lock held on the given document.

	:param doctype: DocType of the locked document
	:param name: `name` of the locked document
	"""
	frappe.get_lazy_doc(doctype, name).unlock()
	frappe.msgprint(frappe._("Document Unlocked"), alert=True)


@public(group="Documents")
@frappe.whitelist()
def update_document_title(
	*,
	doctype: str,
	docname: str,
	title: str | None = None,
	name: str | None = None,
	merge: bool = False,
	enqueue: bool = False,
	**kwargs: Any,
) -> str:
	"""Update the name or title of a document.

	:param doctype: DocType of the document
	:param docname: Name of the document
	:param title: New Title of the document
	:param name: New Name of the document
	:param merge: Merge the current Document with the existing one if exists
	:param enqueue: Enqueue the rename operation, title is updated in current process
	:return: `name` if document was renamed, `docname` if renaming operation was queued.
	"""

	# to maintain backwards API compatibility
	updated_title = kwargs.get("new_title") or title
	updated_name = kwargs.get("new_name") or name

	# TODO: omit this after runtime type checking (ref: https://github.com/frappe/frappe/pull/14927)
	for obj in [docname, updated_title, updated_name]:
		if not isinstance(obj, str | NoneType):
			frappe.throw(f"{obj=} must be of type str or None")

	# handle bad API usages
	merge = sbool(merge)
	enqueue = sbool(enqueue)
	action_enqueued = enqueue and not is_scheduler_inactive()

	doc = frappe.get_doc(doctype, docname)
	doc.check_permission(permtype="write")

	title_field = doc.meta.get_title_field()

	title_updated = updated_title and (title_field != "name") and (updated_title != doc.get(title_field))
	name_updated = updated_name and (updated_name != doc.name)

	queue = kwargs.get("queue") or "long"

	if name_updated:
		if action_enqueued:
			current_name = doc.name

			# before_name hook may have DocType specific validations or transformations
			transformed_name = doc.run_method("before_rename", current_name, updated_name, merge)
			if isinstance(transformed_name, dict):
				transformed_name = transformed_name.get("new")
			transformed_name = transformed_name or updated_name

			doc.queue_action("rename", name=transformed_name, merge=merge, queue=queue, timeout=36000)
		else:
			doc.rename(updated_name, merge=merge)

	if title_updated:
		if action_enqueued and name_updated:
			frappe.enqueue(
				"frappe.core.api.document.set_value",
				doctype=doc.doctype,
				name=updated_name,
				fieldname=title_field,
				value=updated_title,
			)
		else:
			try:
				setattr(doc, title_field, updated_title)
				doc.save()
				frappe.msgprint(_("Saved"), alert=True, indicator="green")
			except Exception as e:
				if frappe.db.is_duplicate_entry(e):
					frappe.throw(
						_("{0} {1} already exists").format(doctype, frappe.bold(docname)),
						title=_("Duplicate Name"),
						exc=frappe.DuplicateEntryError,
					)
				raise

	return doc.name


@public(group="Documents")
@frappe.whitelist()
def make_mapped_doc(
	method: str,
	source_name: str,
	selected_children: str | list | dict | None = None,
	args: str | dict | None = None,
) -> Document:
	"""Return a new mapped document made by calling the given mapper method.

	Sets `selected_children` as flags for the `get_mapped_doc` method.
	Called from `open_mapped_doc` in create_new.js.

	:param method: dotted path of a whitelisted mapper method
	:param source_name: name of the source document, passed to the mapper method
	:param selected_children: rows selected in the UI, mapped instead of full child tables
	:param args: args set as `frappe.flags.args` for the mapper method
	:return: The mapped document, not yet inserted.
	"""
	method = frappe.get_attr(frappe.override_whitelisted_method(method))

	frappe.is_whitelisted(method)

	if selected_children:
		selected_children = frappe.parse_json(selected_children)

	if args:
		frappe.flags.args = frappe._dict(frappe.parse_json(args))

	frappe.flags.selected_children = selected_children or None

	return method(source_name)


@public(group="Documents")
@frappe.whitelist()
def map_docs(
	method: str,
	source_names: str | list,
	target_doc: Document | dict | str,
	args: str | dict | None = None,
) -> Document:
	"""Return the mapped document made by calling the given mapper method with each source doc on the target doc.

	:param method: dotted path of a whitelisted mapper method
	:param source_names: names of the source documents, each passed to the mapper method
	:param target_doc: document (or dict/JSON) the sources are mapped onto
	:param args: args as JSON to pass to the mapper method, e.g. `"{ 'supplier': 'XYZ' }"`
	:return: The mapped target document.
	"""
	method = frappe.get_attr(frappe.override_whitelisted_method(method))

	frappe.is_whitelisted(method)

	for src in frappe.parse_json(source_names):
		_args = (src, target_doc, frappe.parse_json(args)) if args else (src, target_doc)
		target_doc = method(*_args)
	return target_doc


@public(group="Documents")
@frappe.whitelist()
def add_share(
	doctype: str,
	name: str | int,
	user: str | None = None,
	read: str | bool | int = 1,
	write: str | bool | int = 0,
	submit: str | bool | int = 0,
	share: str | bool | int = 0,
	everyone: str | bool | int = 0,
	notify: str | bool | int = 0,
	**kwargs: Any,
) -> Document:
	"""Share a document with a user.

	:param doctype: DocType of the document to be shared
	:param name: name of the document to be shared
	:param user: user the document is shared with, defaults to the session user
	:param read: grant read permission
	:param write: grant write permission
	:param submit: grant submit permission
	:param share: grant permission to share further
	:param everyone: share with everyone instead of a single user
	:param notify: notify the user about the share
	:param kwargs: custom permission types to grant
	:return: The DocShare document.
	"""
	from frappe.share import add_docshare

	return add_docshare(
		doctype,
		name,
		user=user,
		read=read,
		write=write,
		submit=submit,
		share=share,
		everyone=everyone,
		notify=notify,
		**kwargs,
	)


@public(group="Documents")
@frappe.whitelist()
def set_share_permission(
	doctype: str,
	name: str | int,
	user: str | None,
	permission_to: str,
	value: str | bool | int = 1,
	everyone: str | bool | int = 0,
) -> Document | None:
	"""Set or unset one permission on an existing share of a document.

	:param doctype: DocType of the shared document
	:param name: name of the shared document
	:param user: user the document is shared with
	:param permission_to: permission type to change, e.g. `read`, `write`, `share`
	:param value: 1 to grant the permission, 0 to revoke it
	:param everyone: target the share with everyone instead of a single user
	:return: The updated DocShare document, or None if the share was removed.
	"""
	from frappe.share import set_docshare_permission

	return set_docshare_permission(doctype, name, user, permission_to, value=value, everyone=everyone)


@public(group="Documents")
@frappe.whitelist()
def get_shared_users(doctype: str, name: str) -> list:
	"""Get the shares (DocShare records) of a document.

	:param doctype: DocType of the shared document
	:param name: name of the shared document
	:return: DocShare records of the document, one per user it is shared with.
	"""
	from frappe.share import _get_users

	doc = frappe.get_lazy_doc(doctype, name)
	return _get_users(doc)


def insert_doc(doc) -> "Document":
	"""Insert document and return parent document object with appended child document if `doc` is child document else return the inserted document object.

	:param doc: doc to insert (dict)"""

	doc = frappe._dict(doc)
	if frappe.is_table(doc.doctype):
		if not (doc.parenttype and doc.parent and doc.parentfield):
			frappe.throw(_("Parenttype, Parent and Parentfield are required to insert a child record"))

		# inserting a child record
		parent = frappe.get_doc(doc.parenttype, doc.parent)
		parent.append(doc.parentfield, doc)
		parent.save()
		return parent

	return frappe.get_doc(doc).insert()


def delete_doc(doctype, name):
	"""Deletes document
	if doctype is a child table, then deletes the child record using the parent doc
	so that the parent doc's `on_update` is called
	"""

	if frappe.is_table(doctype):
		values = frappe.db.get_value(doctype, name, ["parenttype", "parent", "parentfield"])
		if not values:
			raise frappe.DoesNotExistError(doctype=doctype)

		assert len(values) == 3, "expected parenttype, parent and parentfield for child table row"
		parenttype, parent, parentfield = values
		parent = frappe.get_doc(parenttype, parent)
		if not parent.has_permission("write"):
			raise frappe.DoesNotExistError(doctype=doctype)

		for row in parent.get(parentfield):
			if row.name == name:
				parent.remove(row)
				parent.save()
				break
	else:
		frappe.delete_doc(doctype, name, ignore_missing=False)
