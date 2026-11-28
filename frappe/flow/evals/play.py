# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""`flow-eval check`: play each case's PATH through Flow's tool callback as its user, with no model."""

from typing import Any

import frappe
from frappe.flow.evals.case import Case, as_user, last_line, run_setup


def play(case: Case) -> dict[str, Any]:
	"""The steps of one case's PATH, each {step, ok, word, bytes, detail}; a failed step ends it."""
	from frappe.flow.daemon.callback import tool_callback

	result = {"case": case.name, "status": "pass", "steps": [], "detail": None}
	if case.path is None:
		return {**result, "status": "no PATH"}
	try:
		value = run_setup(case)
		steps = case.path(value) if callable(case.path) else case.path
		session = _session(case)
	except Exception as exc:
		return {**result, "status": "error", "detail": last_line(exc)}
	for n, step in enumerate(steps, 1):
		tool, args, expect = str(step), {}, ()
		try:
			tool, args, *expect = step
			if len(expect) > 1 or not isinstance(args, dict):
				raise ValueError(f"step {n} is not (tool, args) or (tool, args, expect)")
			out = tool_callback(session, tool, args)
			frappe.db.commit()  # as the web request that runs a model's tool call does; nosemgrep: frappe-manual-commit
			content = out.get("content") or ""
			ok, why = _judge(expect[0] if expect else None, content, out.get("is_error"))
		except Exception as exc:
			frappe.db.rollback()
			out, content, ok, why = {}, "", None, last_line(exc)
		word = "error" if ok is None else "fail" if not ok else "ok"
		if ok and out.get("is_error"):
			word = "ok (refused, as expected)"
		if ok and _over_cap(content):
			word = "ok, over the cap"
		step = {"step": f"{n} {tool} {_target(args)}", "word": word, "bytes": len(content.encode())}
		result["steps"].append({**step, "detail": why})
		if not ok:
			result["status"] = "error" if ok is None else "fail"
			break
	return result


def _session(case: Case) -> str:
	"""A chat row owned by the case's user, for the tool callback to act as; no flow server is contacted."""
	from frappe.flow.assistant import ASSISTANT_AGENT_NAME

	with as_user(case.user):
		title = f"flow-eval check {case.name}"
		doc = frappe.get_doc(
			doctype="Flow Session", agent=ASSISTANT_AGENT_NAME, title=title, approval_mode="Auto-approve"
		).insert()
	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	return doc.name


def _judge(expect: Any, content: str, is_error: bool) -> tuple[bool, str | None]:
	shown = " ".join(content[:300].split())
	if expect is None:
		return (True, None) if not is_error else (False, f"error: {shown}")
	if callable(expect):
		return (True, None) if expect(content) else (False, f"expect returned false for: {shown}")
	return (True, None) if expect in content else (False, f'expected "{expect}" in: {shown}')


def _over_cap(content: str) -> bool:
	from flow_harness.tools.builtins.common import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES

	return len(content.encode()) > DEFAULT_MAX_BYTES or content.count("\n") >= DEFAULT_MAX_LINES


def _target(call_args: dict) -> str:
	if method := call_args.get("method"):
		return str(method).rsplit(".", 1)[-1]
	return str(call_args.get("doctype") or "")
