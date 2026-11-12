"""The bulk actions API v2 routes through `frappe.api.bulk`: each is a record function and its route."""

import frappe
from frappe import _, cint
from frappe.api.bulk import (
	QUEUED,
	BulkAction,
	Record,
	Selection,
	check_cap,
	check_gate,
	get_limit,
	read_selection,
	run_bulk,
)
from frappe.api.utils import FrappeValueError
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from frappe.model.docstatus import DocStatus
from frappe.model.workflow import (
	WorkflowStateError,
	get_transitions,
	get_workflow_name,
	has_approval_access,
	run_workflow_transition,
)
from frappe.utils import add_to_date, now_datetime
from frappe.utils.print_format import (
	_enforce_multi_pdf_async_rate_limit,
	append_to_pdf,
	get_max_bulk_print_docs,
	get_max_concurrent_bulk_exports,
	save_pdf_file,
)
from frappe.utils.scheduler import is_scheduler_inactive
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


def bulk_print_docs(doctype: str):
	"""POST /document/<doctype>/bulk_print

	Body: `names`, or `filters` and `or_filters`; `print_format`, `letterhead`, `no_letterhead` and
	`page_size`. At most Print Settings `max_bulk_print_docs` records. Always `202 {task_id, job_id}`:
	the Background Task result adds `file_url` of the merged PDF to `{total, done, failed}`.
	"""
	form = frappe.form_dict
	for key in ("print_format", "letterhead", "page_size"):
		if form.get(key) is not None and not isinstance(form.get(key), str):
			raise FrappeValueError(f"'{key}' must be a string")

	params = {
		"print_format": form.get("print_format") or None,
		"letterhead": form.get("letterhead") or None,
		"no_letterhead": bool(cint(form.get("no_letterhead"))),
		"page_size": form.get("page_size") or None,
		"language": frappe.local.lang,
	}
	return run_bulk(PRINT, doctype, params=params, limit=get_max_bulk_print_docs())


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


def refuse_submit_cancel(doctype: str, params: dict):
	"""A workflow owns the docstatus of its records: its actions submit and cancel, not the bulk bar."""
	if not frappe.get_meta(doctype).is_submittable:
		frappe.throw(_("{0} is not submittable.").format(doctype))

	if get_workflow_name(doctype):
		frappe.throw(_("{0} has a workflow: apply its actions instead.").format(doctype))


def refuse_without_workflow(doctype: str, params: dict):
	if not get_workflow_name(doctype):
		frappe.throw(_("{0} has no workflow.").format(doctype))


def submit_one(doctype: str, name: str):
	return submit_or_cancel_one("submit", doctype, name)


def cancel_one(doctype: str, name: str):
	return submit_or_cancel_one("cancel", doctype, name)


def submit_or_cancel_one(action: str, doctype: str, name: str):
	"""Do it now, or through the Submission Queue when the DocType has `queue_in_background`."""
	doc = frappe.get_doc(doctype, name, for_update=True)
	doc.check_permission(action)

	from_docstatus = DocStatus.DRAFT if action == "submit" else DocStatus.SUBMITTED
	if doc.docstatus != from_docstatus:
		frappe.throw(
			_("Cannot {0} a document with docstatus {1}").format(action, doc.docstatus),
			frappe.DocstatusTransitionError,
		)

	if doc.meta.queue_in_background and not is_scheduler_inactive():
		queue_submission(doc, action.title(), alert=False)
		return QUEUED

	getattr(doc, action)()
	frappe.clear_messages()


def workflow_one(doctype: str, name: str, action: str):
	run_workflow_transition(frappe.get_doc(doctype, name, for_update=True), action)
	frappe.clear_messages()

	if frappe.db.exists(
		"Submission Queue", {"ref_doctype": doctype, "ref_docname": name, "status": "Queued"}
	):
		return QUEUED


def bulk_submit_docs(doctype: str):
	"""POST /document/<doctype>/bulk_submit

	Body: `names`, or `filters` and `or_filters`. Records of a `queue_in_background` DocType go to the
	Submission Queue and come back as `queued`. Refused for a workflow DocType.
	"""
	return run_bulk(SUBMIT, doctype)


def bulk_cancel_docs(doctype: str):
	"""POST /document/<doctype>/bulk_cancel: the same body and rules as `bulk_submit`."""
	return run_bulk(CANCEL, doctype)


def bulk_workflow_docs(doctype: str):
	"""POST /document/<doctype>/bulk_workflow

	Body: `action`, the name of a transition, and `names` or `filters` and `or_filters`. Refused for a
	DocType without a workflow. A record the transition does not apply to fails alone.
	"""
	action = frappe.form_dict.get("action")
	if not isinstance(action, str) or not action:
		raise FrappeValueError("'action' must be the name of a workflow action")

	return run_bulk(WORKFLOW, doctype, params={"action": action})


def bulk_workflow_actions(doctype: str):
	"""POST /document/<doctype>/bulk_workflow_actions

	Body: `names`, or `filters` and `or_filters`. Returns the workflow actions the user can apply to
	every selected record.
	"""
	check_gate()
	selection = read_selection(doctype)
	check_cap(len(selection.records) + len(selection.rejected), get_limit())
	if selection.rejected:
		raise FrappeValueError("'names' must hold strings or integers")
	refuse_without_workflow(doctype, {})

	common = None
	for record in selection.records:
		doc = frappe.get_doc(doctype, record.name)
		try:
			transitions = get_transitions(doc, raise_exception=True)
		except WorkflowStateError:
			return []

		actions = [t.action for t in transitions if has_approval_access(frappe.session.user, doc, t)]
		common = actions if common is None else [action for action in common if action in actions]
		if not common:
			return []

	return common or []


DELETE = BulkAction("Delete", delete_one, check=refuse_workflow_without_allow_edit)
UPDATE = BulkAction("Edit", update_one, check=refuse_workflow_without_allow_edit)
SUBMIT = BulkAction("Submit", submit_one, check=refuse_submit_cancel)
CANCEL = BulkAction("Cancel", cancel_one, check=refuse_submit_cancel)
WORKFLOW = BulkAction("Workflow", workflow_one, check=refuse_without_workflow)


def refuse_print_over_the_user_limits(doctype: str, params: dict):
	"""Print keeps v1's request pacing and its per-user cap on exports in progress."""
	_enforce_multi_pdf_async_rate_limit()

	running = frappe.db.count(
		"Background Task",
		{
			"user": frappe.session.user,
			"status": ["in", ("Queued", "Running")],
			"task_name": ["like", f"{PRINT.label} %"],
			# A lost worker leaves its row behind; it must not hold a slot for good.
			"creation": [">", add_to_date(now_datetime(), hours=-1)],
		},
	)
	if running >= get_max_concurrent_bulk_exports():
		frappe.throw(
			_(
				"You already have the maximum number of bulk PDF exports in progress. Please wait for one to finish."
			),
			frappe.RateLimitExceededError,
		)


def print_one(doctype: str, name: str, **params):
	"""Add one record's pages to the run's PDF, kept on `frappe.local` until `save_print`."""
	writer = getattr(frappe.local, "bulk_print_writer", None)
	if writer is None:
		from pypdf import PdfWriter

		writer = frappe.local.bulk_print_writer = PdfWriter()

	append_to_pdf(
		writer,
		doctype,
		name,
		params["print_format"],
		params["no_letterhead"],
		params["letterhead"],
		print_options(params),
		params["language"],
	)


def save_print(params: dict, result: dict) -> dict:
	writer = getattr(frappe.local, "bulk_print_writer", None)
	frappe.local.bulk_print_writer = None
	if writer is None or not writer.pages:
		return {}

	file = save_pdf_file(writer, print_options(params), f"{get_current_task().task_id}.pdf")
	return {"file_url": file.unique_url}


def print_options(params: dict) -> dict:
	return {"page-size": params["page_size"]} if params["page_size"] else {}


PRINT = BulkAction(
	"Print",
	print_one,
	check=refuse_print_over_the_user_limits,
	finish=save_print,
	background=True,
)
