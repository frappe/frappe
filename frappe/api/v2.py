"""REST API v2

This file defines routes and implementation for REST API.

Note:
	- All functions in this file should be treated as "whitelisted" as they are exposed via routes
	- None of the functions present here should be called from python code, their location and
	  internal implementation can change without treating it as "breaking change".
"""

import json
from typing import Any

from werkzeug.routing import Rule

import frappe
import frappe.client
from frappe import _, cint, cstr, get_newargs, is_whitelisted
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.handler import is_valid_http_method, run_server_script, upload_file

PERMISSION_MAP = {
	"GET": "read",
	"POST": "write",
}


def get_bulk_operation_async_threshold(doctype: str | None = None) -> int:
	conf = frappe.conf.get("bulk_operation_async_threshold", 20)

	if isinstance(conf, dict):
		value = conf.get(doctype, 20) if doctype else conf.get("*", 20)
	else:
		value = conf

	return cint(value)


class FrappeValueError(ValueError):
	http_status_code = 417


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

	try:
		method = frappe.get_attr(method)
	except Exception as e:
		frappe.throw(_("Failed to get method {0} with {1}").format(method, e))

	is_whitelisted(method)
	is_valid_http_method(method)

	return frappe.call(method, **frappe.form_dict)


def login():
	"""Login happens implicitly, this function doesn't do anything."""
	pass


def logout():
	frappe.local.login_manager.logout()
	frappe.db.commit()


def read_doc(doctype: str, name: str):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	_doc = doc.as_dict()

	for key in _doc:
		df = doc.meta.get_field(key)
		if df and df.fieldtype == "Link" and isinstance(_doc.get(key), int):
			_doc[key] = cstr(_doc.get(key))

	return _doc


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

	Response:
		frappe.response["data"]: List of document records as dicts
		frappe.response["has_next_page"]: Indicates if more pages are available

	Controller Customization:
		Doctype controllers can customize queries by implementing a static get_list(query) method
		that receives a QueryBuilder object and returns a modified QueryBuilder.

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
	from frappe.model.base_document import get_controller

	args = frappe.form_dict
	fields: list | None = frappe.parse_json(args.get("fields", None))
	filters: dict | None = frappe.parse_json(args.get("filters", None))
	order_by: str | None = args.get("order_by", None)
	start: int = cint(args.get("start", 0))
	limit: int = cint(args.get("limit", 20))
	group_by: str | None = args.get("group_by", None)
	debug: bool = bool(args.get("debug", False))
	as_dict: bool = bool(args.get("as_dict", True))

	if fields and not isinstance(fields, list):
		raise FrappeValueError("'fields' must be a list")
	if filters and not isinstance(filters, (list, dict)):
		raise FrappeValueError("'filters' must be a list or dictionary")
	if order_by and not isinstance(order_by, str):
		raise FrappeValueError("'order_by' must be a string")
	if group_by and not isinstance(group_by, str):
		raise FrappeValueError("'group_by' must be a string")

	query = frappe.qb.get_query(
		table=doctype,
		fields=fields,
		filters=filters,
		order_by=order_by,
		offset=start,
		limit=limit + 1,  # Fetch one extra to check if there's a next page
		group_by=group_by,
		ignore_permissions=False,
	)

	# Check if the doctype controller has a static get_list method
	controller = get_controller(doctype)
	if hasattr(controller, "get_list"):
		try:
			return_value = controller.get_list(query)

			if return_value is not None:
				# Validate that the returned value has a run method (is a QueryBuilder-like object)
				if not hasattr(return_value, "run"):
					frappe.throw(
						_(
							"Custom get_list method for {0} must return a QueryBuilder object or None, got {1}"
						).format(doctype, type(return_value).__name__)
					)

				query = return_value

		except Exception as e:
			frappe.throw(_("Error in {0}.get_list: {1}").format(doctype, str(e)))

	data = query.run(as_dict=as_dict, debug=debug)
	frappe.response["has_next_page"] = len(data) > limit
	return data[:limit]


def count(doctype: str) -> int:
	from frappe.desk.reportview import get_count

	frappe.form_dict.doctype = doctype

	return get_count()


def create_doc(doctype: str):
	data = frappe.form_dict
	data.pop("doctype", None)

	doc = frappe.new_doc(doctype, **data)

	if (name := data.get("name")) and isinstance(name, str | int):
		doc.flags.name_set = True

	return doc.insert().as_dict()


def copy_doc(doctype: str, name: str, ignore_no_copy: bool = True):
	"""Return a clean copy of the given document that can be modified and posted as a new document."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()

	copy = frappe.copy_doc(doc, ignore_no_copy=ignore_no_copy)

	return copy.as_dict(no_private_properties=True, no_nulls=True)


def update_doc(doctype: str, name: str):
	data = frappe.form_dict

	doc = frappe.get_doc(doctype, name, for_update=True)
	data.pop("flags", None)
	doc.update(data)
	doc.save()
	doc.apply_fieldlevel_read_permissions()

	# check for child table doctype
	if doc.get("parenttype"):
		frappe.get_doc(doc.parenttype, doc.parent).save()

	return doc.as_dict()


def delete_doc(doctype: str, name: str):
	frappe.client.delete_doc(doctype, name)
	frappe.response.http_status_code = 202
	return "ok"


def get_meta(doctype: str):
	frappe.only_for("All")
	return frappe.get_meta(doctype)


def execute_doc_method(doctype: str, name: str, method: str | None = None):
	"""Get a document from DB and execute method on it.

	Use cases:
	- Submitting/cancelling document
	- Triggering some kind of update on a document
	"""
	method = method or frappe.form_dict.pop("run_method")
	doc = frappe.get_doc(doctype, name)
	doc.is_whitelisted(method)

	doc.check_permission(PERMISSION_MAP[frappe.request.method])
	result = doc.run_method(method, **frappe.form_dict)
	frappe.response.docs.append(doc.as_dict())
	return result


def bulk_delete_docs(doctype: str):
	"""Bulk delete multiple documents of the same doctype.

	Request body should contain:
		names: List of document names to delete

	Returns:
		deleted: List of successfully deleted document names
		failed: List of failed deletions with error messages
		total: Total number of documents attempted
		success_count: Number of successful deletions
		failure_count: Number of failed deletions
	"""
	names = frappe.form_dict.get("names")

	if not isinstance(names, list):
		raise FrappeValueError("'names' must be a list")

	if len(names) > get_bulk_operation_async_threshold(doctype):
		job = frappe.enqueue(
			"frappe.api.v2.execute_bulk_delete_docs",
			doctype=doctype,
			names=names,
		)
		frappe.response.http_status_code = 202
		return {"job_id": job.id}

	return execute_bulk_delete_docs(doctype, names)


def execute_bulk_delete_docs(doctype: str, names: list[str | int]):
	deleted = []
	failed = []

	for name in names:
		if not isinstance(name, str | int):
			failed.append({"name": name, "error": "'name' must be a string or integer"})
			continue

		if isinstance(name, int):
			name = str(name)

		savepoint = "bulk_delete_docs"
		frappe.db.savepoint(savepoint)

		try:
			frappe.delete_doc(doctype, name, ignore_missing=False)
			deleted.append(name)
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			failed.append({"name": name, "error": str(e)})

	return {
		"deleted": deleted,
		"failed": failed,
		"total": len(names),
		"success_count": len(deleted),
		"failure_count": len(failed),
	}


def bulk_delete():
	"""Bulk delete documents across multiple doctypes.

	Request body should contain:
		docs: List of {"doctype": str, "name": str} objects

	Returns:
		deleted: List of successfully deleted documents
		failed: List of failed deletions with error messages
		total: Total number of documents attempted
		success_count: Number of successful deletions
		failure_count: Number of failed deletions
	"""
	docs = frappe.form_dict.get("docs", [])

	if not isinstance(docs, list):
		raise FrappeValueError("'docs' must be a list")

	if len(docs) > get_bulk_operation_async_threshold():
		job = frappe.enqueue(
			"frappe.api.v2.execute_bulk_delete",
			docs=docs,
		)
		frappe.response.http_status_code = 202
		return {"job_id": job.id}

	return execute_bulk_delete(docs)


def execute_bulk_delete(docs: list):
	deleted = []
	failed = []

	for item in docs:
		doctype = None
		name = None
		savepoint = "bulk_delete"
		frappe.db.savepoint(savepoint)

		try:
			if not isinstance(item, dict):
				raise FrappeValueError("Each document must be a dictionary with 'doctype' and 'name' keys")

			doctype = item.get("doctype")
			name = item.get("name")

			if not isinstance(doctype, str):
				raise FrappeValueError("'doctype' must be a string")

			if not isinstance(name, str | int):
				raise FrappeValueError("'name' must be a string or integer")

			if isinstance(name, int):
				name = str(name)

			frappe.delete_doc(doctype, name, ignore_missing=False)
			deleted.append({"doctype": doctype, "name": name})
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			failed.append({"doctype": doctype, "name": name, "error": str(e)})

	return {
		"deleted": deleted,
		"failed": failed,
		"total": len(docs),
		"success_count": len(deleted),
		"failure_count": len(failed),
	}


def bulk_update_docs(doctype: str):
	"""Bulk update multiple documents of the same doctype.

	Request body should contain:
		docs: List of {"name": str, ...fields} objects where each object contains
		      the document name and the fields to update

	Returns:
		updated: List of successfully updated document names
		failed: List of failed updates with error messages
		total: Total number of documents attempted
		success_count: Number of successful updates
		failure_count: Number of failed updates
	"""
	docs = frappe.form_dict.get("docs")

	if not isinstance(docs, list):
		raise FrappeValueError("'docs' must be a list")

	if len(docs) > get_bulk_operation_async_threshold(doctype):
		job = frappe.enqueue(
			"frappe.api.v2.execute_bulk_update_docs",
			doctype=doctype,
			docs=docs,
		)
		frappe.response.http_status_code = 202
		return {"job_id": job.id}

	return execute_bulk_update_docs(doctype, docs)


def execute_bulk_update_docs(doctype: str, docs: list):
	updated = []
	failed = []

	for item in docs:
		name = None
		savepoint = "bulk_update_docs"
		frappe.db.savepoint(savepoint)

		try:
			if not isinstance(item, dict):
				raise FrappeValueError("Each update must be a dictionary with 'name' and field values")

			name = item.get("name")
			if not isinstance(name, str | int):
				raise FrappeValueError("'name' must be a string or integer")

			if isinstance(name, int):
				name = str(name)

			doc = frappe.get_doc(doctype, name, for_update=True)
			item_copy = item.copy()
			item_copy.pop("name")
			item_copy.pop("flags", None)

			doc.update(item_copy)
			doc.save()
			doc.apply_fieldlevel_read_permissions()

			updated.append(name)
			frappe.response.docs.append(doc.as_dict())
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			failed.append({"name": name, "error": str(e)})

	return {
		"updated": updated,
		"failed": failed,
		"total": len(docs),
		"success_count": len(updated),
		"failure_count": len(failed),
	}


def bulk_update():
	"""Bulk update documents across multiple doctypes.

	Request body should contain:
		docs: List of {"doctype": str, "name": str, ...fields} objects

	Returns:
		updated: List of successfully updated documents
		failed: List of failed updates with error messages
		total: Total number of documents attempted
		success_count: Number of successful updates
		failure_count: Number of failed updates
	"""
	docs = frappe.form_dict.get("docs")

	if not isinstance(docs, list):
		raise FrappeValueError("'docs' must be a list")

	if len(docs) > get_bulk_operation_async_threshold():
		job = frappe.enqueue(
			"frappe.api.v2.execute_bulk_update",
			docs=docs,
		)
		frappe.response.http_status_code = 202
		return {"job_id": job.id}

	return execute_bulk_update(docs)


def execute_bulk_update(docs: list):
	updated = []
	failed = []

	for item in docs:
		doctype = None
		name = None
		savepoint = "bulk_update"
		frappe.db.savepoint(savepoint)

		try:
			if not isinstance(item, dict):
				raise FrappeValueError(
					"Each document must be a dictionary with 'doctype', 'name', and field values"
				)

			doctype = item.get("doctype")
			name = item.get("name")

			if not isinstance(doctype, str):
				raise FrappeValueError("'doctype' must be a string")

			if not isinstance(name, str | int):
				raise FrappeValueError("'name' must be a string or integer")

			if isinstance(name, int):
				name = str(name)

			doc = frappe.get_doc(doctype, name, for_update=True)
			item_copy = item.copy()
			item_copy.pop("doctype")
			item_copy.pop("name")
			item_copy.pop("flags", None)

			doc.update(item_copy)
			doc.save()
			doc.apply_fieldlevel_read_permissions()

			updated.append({"doctype": doctype, "name": name})
			frappe.response.docs.append(doc.as_dict())
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			failed.append({"doctype": doctype, "name": name, "error": str(e)})

	return {
		"updated": updated,
		"failed": failed,
		"total": len(docs),
		"success_count": len(updated),
		"failure_count": len(failed),
	}


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

	doc = frappe.get_doc(document, check_permission=PERMISSION_MAP[frappe.request.method])
	doc._original_modified = doc.modified
	doc.check_if_latest()

	method_obj = getattr(doc, method)
	fn = getattr(method_obj, "__func__", method_obj)
	is_whitelisted(fn)
	is_valid_http_method(fn)

	new_kwargs = get_newargs(fn, kwargs)
	response = doc.run_method(method, **new_kwargs)
	frappe.response.docs.append(doc)  # send modified document and result both.
	return response


url_rules = [
	# RPC calls
	Rule("/method/login", endpoint=login),
	Rule("/method/logout", endpoint=logout, methods=["POST"]),
	Rule("/method/ping", endpoint=frappe.ping),
	Rule("/method/upload_file", endpoint=upload_file, methods=["POST"]),
	Rule("/method/bulk_delete", endpoint=bulk_delete, methods=["POST"]),
	Rule("/method/bulk_update", endpoint=bulk_update, methods=["POST"]),
	Rule("/method/<method>", endpoint=handle_rpc_call),
	Rule(
		"/method/run_doc_method",
		methods=["GET", "POST"],
		endpoint=lambda: frappe.call(run_doc_method, **frappe.form_dict),
	),
	Rule("/method/<doctype>/<method>", endpoint=handle_rpc_call),
	# Document level APIs
	Rule("/document/<doctype>", methods=["GET"], endpoint=document_list),
	Rule("/document/<doctype>", methods=["POST"], endpoint=create_doc),
	Rule("/document/<doctype>/bulk_delete", methods=["POST"], endpoint=bulk_delete_docs),
	Rule("/document/<doctype>/bulk_update", methods=["POST"], endpoint=bulk_update_docs),
	Rule("/document/<doctype>/<path:name>/", methods=["GET"], endpoint=read_doc),
	Rule("/document/<doctype>/<path:name>/copy", methods=["GET"], endpoint=copy_doc),
	Rule("/document/<doctype>/<path:name>/", methods=["PATCH", "PUT"], endpoint=update_doc),
	Rule("/document/<doctype>/<path:name>/", methods=["DELETE"], endpoint=delete_doc),
	Rule(
		"/document/<doctype>/<path:name>/method/<method>/",
		methods=["GET", "POST"],
		endpoint=execute_doc_method,
	),
	# Collection level APIs
	Rule("/doctype/<doctype>/meta", methods=["GET"], endpoint=get_meta),
	Rule("/doctype/<doctype>/count", methods=["GET"], endpoint=count),
]
