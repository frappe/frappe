"""The bulk actions API v2 routes through `frappe.api.bulk`: each is a record function and its route."""

import frappe
from frappe import _
from frappe.api.bulk import BulkAction, Record, Selection, read_selection, run_bulk
from frappe.api.utils import FrappeValueError
from frappe.model.workflow import get_workflow_name
from frappe.utils.task_queue import get_current_task

# The body keys an update may not set: they would change which record it is.
RESERVED_KEYS = ("doctype", "name", "flags")
ROW_RESERVED_KEYS = (*RESERVED_KEYS, "parent", "parenttype", "parentfield", "idx")


def bulk_delete_docs(doctype: str):
	"""POST /document/<doctype>/bulk_delete

	Body: `names`, or `filters` and `or_filters` for every record the list shows.
	Returns `{total, done, failed: [{name, error}]}`, or `202 {task_id, job_id}` above the threshold.
	"""
	return run_bulk(DELETE, doctype)


def bulk_delete():
	"""POST /method/bulk_delete: the same across doctypes. Body: `docs`, a list of `{doctype, name}`."""
	return run_bulk(DELETE, selection=selection_from_docs(frappe.form_dict.get("docs"), with_values=False))


def bulk_update_docs(doctype: str):
	"""POST /document/<doctype>/bulk_update

	Body: one `values` (and `child_values`: `{table_field: {field: value}}`, set on every row of the
	table) for the selected records, or `docs`, a list of `{name, ...fields}` with its own values each.
	"""
	form = frappe.form_dict

	if "docs" in form:
		if "values" in form or "child_values" in form:
			raise FrappeValueError("Send either 'docs' or 'values', not both")
		return run_bulk(UPDATE, doctype, selection=selection_from_docs(form.get("docs"), doctype))

	values, child_values = form.get("values"), form.get("child_values")
	for key, value in (("values", values), ("child_values", child_values)):
		if value is not None and not isinstance(value, dict):
			raise FrappeValueError(f"'{key}' must be a dictionary")
	if not (values or child_values):
		raise FrappeValueError("'values' or 'docs' is required")

	return run_bulk(
		UPDATE,
		doctype,
		selection=read_selection(doctype),
		params={"values": values, "child_values": child_values},
	)


def bulk_update():
	"""POST /method/bulk_update: `docs` across doctypes, a list of `{doctype, name, ...fields}`."""
	return run_bulk(UPDATE, selection=selection_from_docs(frappe.form_dict.get("docs")))


def selection_from_docs(docs, doctype: str | None = None, with_values: bool = True) -> Selection:
	"""Records from a list of `{name, ...fields}` (`{doctype, name, ...fields}` when `doctype` is None)."""
	if not isinstance(docs, list):
		raise FrappeValueError("'docs' must be a list")

	records, rejected = [], []
	for item in docs:
		name = item.get("name") if isinstance(item, dict) else None
		item_doctype = doctype or (item.get("doctype") if isinstance(item, dict) else None)
		try:
			records.append(record_from_doc(item, item_doctype, doctype is None, with_values))
		except FrappeValueError as e:
			identity = {"name": name} if doctype else {"doctype": item_doctype, "name": name}
			rejected.append({**identity, "error": str(e)})

	return Selection(records, rejected)


def record_from_doc(item, doctype: str | None, with_doctype: bool, with_values: bool) -> Record:
	if not isinstance(item, dict):
		keys = "'doctype' and 'name' keys" if with_doctype else "'name' and field values"
		raise FrappeValueError(f"Each document must be a dictionary with {keys}")

	if not isinstance(doctype, str):
		raise FrappeValueError("'doctype' must be a string")

	if not isinstance(item.get("name"), str | int):
		raise FrappeValueError("'name' must be a string or integer")

	if not with_values:
		return Record(doctype, str(item["name"]))

	values = {key: value for key, value in item.items() if key not in RESERVED_KEYS}
	return Record(doctype, str(item["name"]), {"values": values})


def delete_one(doctype: str, name: str):
	frappe.delete_doc(doctype, name, ignore_missing=False)


def update_one(doctype: str, name: str, values: dict | None = None, child_values: dict | None = None):
	doc = frappe.get_doc(doctype, name, for_update=True)
	doc.update({key: value for key, value in (values or {}).items() if key not in RESERVED_KEYS})

	tables = {df.fieldname for df in doc.meta.get_table_fields()}
	for table_field, fields in (child_values or {}).items():
		if table_field not in tables:
			raise FrappeValueError(f"'{table_field}' is not a table field of {doctype}")
		for row in doc.get(table_field):
			row.update({key: value for key, value in fields.items() if key not in ROW_RESERVED_KEYS})

	doc.save()

	# A background run has no response to carry them.
	if not get_current_task():
		frappe.response.docs.append(doc.copy_with_fieldlevel_read_permissions().as_dict())


def refuse_workflow_without_allow_edit(doctype: str, params: dict):
	"""A workflow owns the states of its records, so Edit and Delete need List View Settings to allow it."""
	if get_workflow_name(doctype) and not frappe.db.get_value("List View Settings", doctype, "allow_edit"):
		frappe.throw(
			_("{0} has a workflow: allow bulk edit in its List View Settings first.").format(doctype)
		)


DELETE = BulkAction("Delete", delete_one, check=refuse_workflow_without_allow_edit)
UPDATE = BulkAction("Edit", update_one, check=refuse_workflow_without_allow_edit)
