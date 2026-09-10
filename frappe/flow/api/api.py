# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

FEEDBACK_COMMENT_LIMIT = 500


@frappe.whitelist()
def submit_feedback(run_name: str, rating: str, comment: str | None = None) -> dict[str, Any]:
	"""Record thumbs feedback on a finished run, or clear it with rating "None". A
	thumbs-down comment is stored as shared agent memory when the agent has memory
	enabled (a no-op otherwise). Clearing the rating leaves any saved memory intact."""
	from flow.lib.session import assert_run_owner
	from flow.memory.memory import save_feedback_memory

	if not isinstance(run_name, str) or not run_name.strip():
		frappe.throw(_("Run is required."), title=_("Invalid Run"))
	if rating not in ("Up", "Down", "None"):
		frappe.throw(_("Rating must be Up, Down, or None."), title=_("Invalid Rating"))
	comment = (comment or "").strip()
	if len(comment) > FEEDBACK_COMMENT_LIMIT:
		frappe.throw(
			_("Keep feedback under {0} characters.").format(FEEDBACK_COMMENT_LIMIT),
			title=_("Feedback Too Long"),
		)

	run = frappe.get_doc("Flow Run", run_name.strip())
	assert_run_owner(run)
	if run.status not in ("Completed", "Denied", "Failed"):
		frappe.throw(
			_("Feedback applies to finished runs only (this run is {0}).").format(run.status),
			title=_("Run Not Finished"),
		)

	if rating == "None":
		run.db_set({"feedback_rating": "", "feedback_comment": None})
		return {"rating": None}

	memory = save_feedback_memory(run, comment) if rating == "Down" and comment else None
	run.db_set({"feedback_rating": rating, "feedback_comment": comment or None})

	result: dict[str, Any] = {"rating": rating}
	if memory:
		result["memory"] = memory
	return result


@frappe.whitelist()
def attach_file(file: str) -> dict[str, Any]:
	"""Validate and extract an uploaded File for use as a chat attachment. Errors
	(unsupported type, unreadable, not owned) surface here, at upload time. The
	extracted text is staged in cache; the attachment row is written on send."""
	if not isinstance(file, str) or not file.strip():
		frappe.throw(_("File is required."), title=_("Invalid Attachment"))

	from flow.flow.doctype.flow_session_attachment.flow_session_attachment import stage_attachment

	return stage_attachment(file.strip())
