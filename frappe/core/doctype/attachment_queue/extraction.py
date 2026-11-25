# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Read a queued file with Flow, so the document written from it starts filled in.

Flow's harness has no structured output, so the values come back through the
`propose_extraction` tool rather than as a parsed reply. The tool is the contract
boundary: the model names fields and values, and this module decides which of them
the target DocType can actually hold.
"""

from __future__ import annotations

import json
import re
from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.attachment_queue.attachment_queue import publish_queue_update, queued_file
from frappe.flow import Agent, ToolContext, tool
from frappe.flow.lib.agent import with_app_prefix
from frappe.utils import cint, cstr, flt, get_datetime, get_time, getdate

QUEUE_DOCTYPE = "Attachment Queue"
AGENT_TITLE = "Document Extraction"
# An Agent namespaces itself by the app that defines it, so the row is not named the title.
AGENT_NAME = with_app_prefix("frappe", AGENT_TITLE)
MAX_ITERATIONS = 10

AGENT_INSTRUCTIONS = (
	"You read a business document — an invoice, a bill, a receipt, a purchase order — and "
	"report the field values it states, so a person can check them instead of typing them.\n\n"
	"The message names the DocType being filled in and lists every field you may report, with "
	"its fieldtype and options. Report a field only when the document states it. A field you "
	"are unsure about is left out: a blank field costs the user one entry, a wrong one costs "
	"them a correction they may not notice.\n\n"
	"Never compute a value the document does not state, and never carry a value over from "
	"another field because it looks similar.\n\n"
	"Call propose_extraction exactly once, then stop. Do not reply with the values as text."
)

# Fieldtypes a document can state a value for. Layout fields and child tables hold no
# scalar value; attachments, dynamic links and colors are not something a page states.
EXTRACTABLE_FIELDTYPES = frozenset(
	{
		"Data",
		"Select",
		"Link",
		"Small Text",
		"Text",
		"Long Text",
		"Text Editor",
		"Date",
		"Datetime",
		"Time",
		"Currency",
		"Float",
		"Int",
		"Percent",
		"Check",
	}
)
# The innermost "message" of a provider's own error payload, wrapped in whatever the
# layers above it added. Matched as a JSON string so escapes survive.
SERVICE_MESSAGE = re.compile(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"')
MAX_ERROR = 500

NUMERIC_FIELDTYPES = frozenset({"Currency", "Float", "Percent", "Int"})
NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)")
CHECK_WORDS = {"1": 1, "true": 1, "yes": 1, "y": 1, "0": 0, "false": 0, "no": 0, "n": 0}


def start(entry: str) -> None:
	"""Start reading the entry's file with Flow, and record the run so the on_complete callback can find it."""
	doc = frappe.get_doc(QUEUE_DOCTYPE, entry)
	if doc.extraction_status != "Started":
		return

	# Flow only sends files the session owner uploaded, and a coworker may have queued this read.
	frappe.set_user(doc.owner)  # nosemgrep: frappe-setuser
	try:
		# the agent carries its own approval mode, so the session takes it from there
		session = ensure_agent().new_session(title=_("Extraction for {0}").format(doc.name))
		run = session.chat(
			build_prompt(doc),
			attachments=[queued_file(doc)],
			reference_doctype=QUEUE_DOCTYPE,
			reference_name=doc.name,
			on_complete="frappe.core.doctype.attachment_queue.extraction.extraction_complete",
		)
	except Exception as exc:
		frappe.log_error(
			title="Attachment Queue extraction failed",
			reference_doctype=QUEUE_DOCTYPE,
			reference_name=doc.name,
		)
		fail(doc, str(exc))
		return

	doc.db_set("extraction_run", run.name, update_modified=False)


def enqueue_extraction(entry: str) -> None:
	"""Read the entry's file in the background, once the request that queued it has committed."""
	frappe.enqueue(
		"frappe.core.doctype.attachment_queue.extraction.start",
		queue="long",
		enqueue_after_commit=True,
		entry=entry,
	)


@frappe.whitelist()
def read_now(entry: str) -> str:
	"""Read the entry's file now, and return the status to wait on.

	Two entries arrive here. One was never offered to Flow, because it was uploaded before
	its DocType asked for extraction. The other was read and failed, usually for a reason
	outside the file — no credit on the provider, an unreachable flow server, a model that
	has since been corrected. An entry already read, or being read, is left alone.

	Returns an empty string when the DocType does not ask for extraction, so the review
	knows there is nothing to wait for.
	"""
	doc = frappe.get_doc(QUEUE_DOCTYPE, entry)
	frappe.has_permission(doc.document_type, "create", throw=True)

	if doc.extraction_status in ("Started", "Completed"):
		return doc.extraction_status
	# after_insert checks this for a new entry; an older one is only checked here
	if not frappe.get_meta(doc.document_type).get("enable_flow_extraction"):
		return ""

	# last read's outcome goes too, so the review never mixes it with this read's
	doc.db_set(
		{
			"extraction_status": "Started",
			"extraction_error": None,
			"extracted_values": None,
			"skipped_values": None,
		},
		update_modified=False,
	)
	enqueue_extraction(doc.name)
	return "Started"


def build_prompt(doc) -> str:
	"""The one message the agent gets: what is being filled in, and the fields it may fill."""
	fields = field_schema(doc.document_type)
	if not fields:
		frappe.throw(
			_("{0} has no fields that can be read out of a file.").format(_(doc.document_type)),
			title=_("Nothing to Extract"),
		)

	return "\n\n".join(
		[
			_("Read the attached file and report the values it states for a new {0}.").format(
				_(doc.document_type)
			),
			_("Fields you may report:") + "\n" + json.dumps(fields, indent=1, default=str),
			_(
				"Write a date as YYYY-MM-DD, a time as HH:MM:SS, and an amount as a plain number "
				"with no currency symbol or thousands separator. For a Select field use one of its "
				"options exactly as written. For a Link field use the name of an existing record. "
				"Write every other field as plain text."
			),
		]
	)


def extractable_fields(doctype: str) -> list[Any]:
	"""The DocFields of `doctype` a file can state a value for."""
	return [
		df
		for df in frappe.get_meta(doctype).fields
		if df.fieldtype in EXTRACTABLE_FIELDTYPES and not (df.read_only or df.hidden or df.is_virtual)
	]


def field_schema(doctype: str) -> list[dict[str, Any]]:
	"""Those fields as the agent sees them."""
	fields = []
	for df in extractable_fields(doctype):
		entry: dict[str, Any] = {
			"fieldname": df.fieldname,
			"label": _(df.label or df.fieldname),
			"fieldtype": df.fieldtype,
		}
		if df.reqd:
			entry["required"] = True
		if df.description:
			entry["description"] = _(df.description)
		if df.fieldtype == "Select":
			entry["options"] = select_options(df)
		elif df.fieldtype == "Link":
			entry["links_to"] = df.options
		fields.append(entry)
	return fields


@tool
def propose_extraction(values: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
	"""Report the field values the attached file states, keyed by fieldname.

	Values the target DocType cannot hold — an unknown fieldname, a Select option that does
	not exist, a Link to a missing record, an unparseable date — are skipped, and reported
	to the reader rather than discarded. Returns the fieldnames that were kept and, for
	each one skipped, why the field could not hold it.
	"""
	doc = frappe.get_doc(QUEUE_DOCTYPE, entry_of_session(ctx.session_id))
	frappe.has_permission(doc.document_type, "create", throw=True)

	kept, skipped = coerce_values(doc.document_type, values)
	doc.db_set(
		{
			"extracted_values": json.dumps(kept, default=str),
			"skipped_values": json.dumps(skipped, default=str),
		},
		update_modified=False,
	)
	return {
		"kept": sorted(kept),
		"skipped": {name: entry["reason"] for name, entry in sorted(skipped.items())},
	}


def entry_of_session(session: str) -> str:
	"""The entry the session was started for. Read from the run rather than from an argument,
	so the model cannot report values against another entry."""
	entry = frappe.db.get_value(
		"Flow Run",
		{"session": session, "reference_doctype": QUEUE_DOCTYPE},
		"reference_name",
		order_by="creation desc",
	)
	if not entry:
		frappe.throw(_("This session is not reading a queued file."), title=_("No Queue Entry"))
	return entry


def coerce_values(doctype: str, values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict]]:
	"""Split `values` into the ones `doctype` can hold, coerced to its field types, and the
	ones it cannot, each with the value the file stated and why the field cannot hold it.

	A field the file left blank is in neither: there is nothing to fill in and nothing to
	report. The rest are worth reporting, since the reader is the only one who can act on
	them — usually by creating the record a Link names.
	"""
	extractable = {df.fieldname: df for df in extractable_fields(doctype)}

	kept: dict[str, Any] = {}
	skipped: dict[str, dict[str, Any]] = {}
	for fieldname, value in (values or {}).items():
		if value is None or (isinstance(value, str) and not value.strip()):
			continue

		df = extractable.get(fieldname)
		if df is None:
			skipped[cstr(fieldname)] = {
				"value": cstr(value),
				"reason": _("{0} has no such field").format(_(doctype)),
			}
			continue

		coerced = coerce(df, value)
		if coerced is None:
			skipped[df.fieldname] = {
				"label": _(df.label or df.fieldname),
				"value": cstr(value),
				"reason": skip_reason(df),
			}
		else:
			kept[fieldname] = coerced
	return kept, skipped


def skip_reason(df) -> str:
	"""Why `df` cannot hold what the file stated, in the reader's own terms."""
	if df.fieldtype == "Link":
		return _("there is no {0} by this name").format(_(df.options))
	if df.fieldtype == "Select":
		return _("this field does not offer that option")
	if df.fieldtype in NUMERIC_FIELDTYPES:
		return _("this field holds a number")
	if df.fieldtype in ("Date", "Datetime", "Time"):
		return _("this is not a date the field can read")
	if df.fieldtype == "Check":
		return _("this field holds a yes or a no")
	return _("the field cannot hold this value")


def coerce(df, value: Any) -> Any:
	"""`value` as `df` can hold it, or None when it cannot hold it at all.

	The model is an untrusted client here: anything it sends that the field would reject is
	turned away, so the form is never filled with a value that blocks saving it.
	"""
	if df.fieldtype in NUMERIC_FIELDTYPES:
		return parse_number(df.fieldtype, value)
	if df.fieldtype == "Check":
		return CHECK_WORDS.get(cstr(value).strip().lower())
	if df.fieldtype == "Select":
		options = select_options(df)
		return cstr(value) if cstr(value) in options else None
	if df.fieldtype == "Link":
		return cstr(value) if frappe.db.exists(df.options, cstr(value)) else None
	if df.fieldtype in ("Date", "Datetime", "Time"):
		return parse_moment(df.fieldtype, value)
	return cstr(value)


def parse_number(fieldtype: str, value: Any) -> float | int | None:
	"""`value` as a number the field can hold, or None when it is not one.

	A non-numeric string is turned away rather than read as zero: a zero the file never
	stated reads as a real amount on the form.
	"""
	if isinstance(value, bool):
		return None
	if not isinstance(value, int | float):
		text = cstr(value).strip().replace(",", "")
		if not NUMBER.fullmatch(text):
			return None
		value = text
	return cint(value) if fieldtype == "Int" else flt(value)


def parse_moment(fieldtype: str, value: Any) -> str | None:
	"""A date, datetime or time the field can hold, or None when the value is not one.

	The parsers throw on an unparseable string, and the string came from the model.
	"""
	parse = {"Date": getdate, "Datetime": get_datetime, "Time": get_time}[fieldtype]
	try:
		parsed = parse(value)
	except Exception:
		return None
	return cstr(parsed) if parsed is not None else None


def select_options(df) -> list[str]:
	return [option for option in (df.options or "").split("\n") if option.strip()]


def extraction_complete(run) -> None:
	"""Flow Run on_complete: the entry is done being read, one way or the other."""
	if run.reference_doctype != QUEUE_DOCTYPE or not run.reference_name:
		return

	doc = frappe.get_doc(QUEUE_DOCTYPE, run.reference_name)
	if run.status == "Completed" and doc.extracted_values:
		doc.db_set({"extraction_status": "Completed", "extraction_error": None}, update_modified=False)
		publish_queue_update(doc.document_type)
	else:
		fail(doc, run.error or _("Flow did not report any field values for this file."))


def fail(doc, error: str) -> None:
	doc.db_set(
		{"extraction_status": "Failed", "extraction_error": readable_error(error)},
		update_modified=False,
	)
	publish_queue_update(doc.document_type)


def readable_error(error: str | None) -> str:
	"""The part of a Flow failure worth showing the person filling in the document.

	A provider failure arrives as a stack of wrappers around the service's own JSON, whose
	`message` is the only part that says what went wrong. The whole text stays on the Flow
	Run, which `extraction_run` links to.
	"""
	text = (error or "").strip()
	if not text:
		return _("Flow did not say why.")

	match = SERVICE_MESSAGE.search(text)
	if match:
		try:
			return json.loads(f'"{match.group(1)}"')[:MAX_ERROR]
		except ValueError:
			pass
	return text.split("\n", 1)[0][:MAX_ERROR]


def ensure_agent() -> Agent:
	"""The extraction agent, written to the site if it is not there yet, or if its model is gone."""
	model = frappe.db.get_value("Flow Agent", AGENT_NAME, "model")
	if model and frappe.db.exists("Flow Model", model):
		return extraction_agent(model)

	agents = flow_agents()
	if not agents:
		frappe.throw(
			_("Add an enabled Flow Model before reading files with Flow."),
			title=_("No Flow Model"),
		)
	agents[0].sync()
	return agents[0]


def flow_agents() -> list[Agent]:
	"""flow_agents hook: the extraction agent, once the site has a model to run it on. Its model
	is set once; switching it afterwards is the site's choice, the same as for the Assistant."""
	model = frappe.db.get_value("Flow Model", {"enabled": 1}, "name")
	return [extraction_agent(model)] if model else []


def extraction_agent(model: str) -> Agent:
	return Agent(
		name=AGENT_TITLE,
		model=model,
		description=_("Reads a queued file and reports the field values it states."),
		instructions=AGENT_INSTRUCTIONS,
		tools=[propose_extraction],
		max_iterations=MAX_ITERATIONS,
		auto_approve=True,
	)
