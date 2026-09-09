# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Runs an agent's tools for the flow server: every client tool call in a daemon session
comes back here and runs on this site as the Flow Session's owner."""

from __future__ import annotations

import json
from hmac import compare_digest
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

from flow.daemon import session_config

if TYPE_CHECKING:
	from flow.lib.tool import Tool

ERROR_LIMIT = 500
SAVEPOINT = "flow_tool"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def tool_callback(
	session_id: str,
	tool: str,
	args: dict | None = None,
	mode: str = "execute",
) -> dict:
	"""`execute` → {content, is_error}; `confirm` → {prompt}. The user is the session's
	owner, never the daemon's user_context; failures are content for the model, not a 500."""
	_authenticate()
	session = frappe.db.get_value("Flow Session", session_id, ["owner", "agent"], as_dict=True)
	if not session:
		return _error(_("Unknown session {0}.").format(session_id))
	if not frappe.db.get_value("User", session.owner, "enabled"):
		return _error(_("The session's owner is disabled."))
	user = frappe.session.user
	frappe.set_user(session.owner)
	frappe.flags.flow_run = frappe.db.get_value("Flow Run", {"session": session_id, "status": "Running"})
	frappe.db.savepoint(SAVEPOINT)
	try:
		return _dispatch(session.agent, tool, args or {}, mode)
	except Exception as exc:
		frappe.db.rollback(save_point=SAVEPOINT)
		return _error(str(exc).strip() or type(exc).__name__)
	finally:
		frappe.flags.flow_run = None
		frappe.set_user(user)


def _authenticate() -> None:
	secret = frappe.conf.flow_server_secret or ""
	given = frappe.request.headers.get("X-Harness-Token", "")
	if not secret or not compare_digest(given.encode(), secret.encode()):
		raise frappe.AuthenticationError


def _dispatch(agent: str, name: str, args: dict, mode: str) -> dict:
	agent_doc = frappe.get_doc("Flow Agent", agent)
	if not agent_doc.enabled:
		return _error(_("The session's agent is disabled."))
	tools = session_config.client_tools(agent_doc)
	tool = next((tool for tool in tools if tool.name == name), None)
	if tool is None:
		return _error(_("Unknown tool {0}.").format(name))
	if mode == "confirm":
		return {"prompt": confirm_prompt(tool, args)}
	return {"content": _text(tool(**args)), "is_error": False}


def _error(message: str) -> dict:
	return {"content": message[:ERROR_LIMIT], "is_error": True}


def _text(result: Any) -> str:
	if isinstance(result, str):
		return result
	if result is None:
		return ""
	return json.dumps(result, default=str)


def confirm_prompt(tool: Tool, args: dict) -> str:
	"""First line: what is being approved, in plain English. Then the tool's own summary,
	else its arguments."""
	body = tool.confirm_prompt(args) if tool.confirm_prompt else json.dumps(args, indent=2, default=str)
	return f"{confirm_title(tool.name, args)}\n{body}"


def confirm_title(name: str, args: dict) -> str:
	doctype = args.get("doctype") if isinstance(args.get("doctype"), str) else ""
	action = args.get("action") if isinstance(args.get("action"), str) else ""
	if name == "create" and doctype:
		return _count("Create 1 {0} record", "Create {0} {1} records", args.get("records"), doctype)
	if name == "update" and doctype:
		return _count("Update 1 {0} record", "Update {0} {1} records", args.get("names"), doctype)
	if name == "delete" and doctype:
		return _count("Delete 1 {0} record", "Delete {0} {1} records", args.get("names"), doctype)
	if name == "run_action" and action:
		target = f"{_list_count_or_one(args.get('names'))} {doctype}" if doctype else _("records")
		return _('Run "{0}" on {1}').format(_humanize(action), target)
	if name == "execute":
		description = args.get("description")
		return (description.strip() if isinstance(description, str) else "") or _("Run Python code")
	return _humanize(name)


def _count(one: str, many: str, value: Any, doctype: str) -> str:
	n = _list_count_or_one(value)
	return _(one).format(doctype) if n == 1 else _(many).format(n, doctype)


def _list_count_or_one(value: Any) -> int:
	return len(value) if isinstance(value, list) else 1


def _humanize(name: str) -> str:
	name = name.replace("_", " ")
	return name[:1].upper() + name[1:]
