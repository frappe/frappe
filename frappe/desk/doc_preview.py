# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.form.load import set_link_titles
from frappe.model import table_fields
from frappe.model.workflow import get_workflow_name

EXCLUDED_META_KEYS = ("permissions", "actions", "links", "row_format", "index_web_pages_for_search")


@frappe.whitelist(methods=["GET"])
def get_preview(doctype: str, name: str):
	"""Doc + trimmed metas for a read-only preview of a document.

	Deliberately not getdoc/getdoctype: those run onload, write a View Log, load docinfo, and ship
	(and execute) form/list/client scripts — none of which a preview should do.
	"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	set_link_titles(doc)

	return {
		"doc": doc.as_dict(),
		"metas": get_preview_metas(doctype),
		"permlevels": doc.get_permlevel_access("read"),
		"workflow": get_workflow_info(doctype),
	}


def get_preview_metas(doctype: str, metas: dict | None = None) -> dict:
	"""Meta for `doctype` and, recursively, its child tables.

	frappe.get_meta() returns the base Meta, so the FormMeta assets (__js, __list_js, __custom_js,
	print formats, workflow docs) are never built or sent.
	"""
	if metas is None:
		metas = {}
	if doctype in metas:
		return metas

	meta = frappe.get_meta(doctype)
	trimmed = meta.as_dict(no_nulls=True)
	for key in EXCLUDED_META_KEYS:
		trimmed.pop(key, None)
	metas[doctype] = trimmed

	for df in meta.fields:
		if df.fieldtype in table_fields and df.options:
			get_preview_metas(df.options, metas)

	return metas


def get_workflow_info(doctype: str) -> dict | None:
	"""Active workflow's state field and per-state styles, for the status indicator.

	Without it the indicator falls through to docstatus and shows "Draft" for a document the form
	shows as its workflow state.
	"""
	workflow_name = get_workflow_name(doctype)
	if not workflow_name:
		return None

	workflow = frappe.get_cached_doc("Workflow", workflow_name)
	styles = get_workflow_state_styles()

	return {
		"workflow_state_field": workflow.workflow_state_field,
		"override_status": workflow.override_status,
		"state_styles": {row.state: styles.get(row.state) for row in workflow.states},
	}


@frappe.request_cache
def get_workflow_state_styles() -> dict:
	"""{state: style} for every Workflow State — a small, rarely-changing table."""
	return dict(frappe.get_all("Workflow State", fields=["name", "style"], as_list=True, limit_page_length=0))
