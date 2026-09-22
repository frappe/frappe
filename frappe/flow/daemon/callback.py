# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Authenticated callbacks from the flow server."""

from __future__ import annotations

import json
from hmac import compare_digest
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

if TYPE_CHECKING:
	from flow.lib.tool import Tool

ERROR_LIMIT = 500
SAVEPOINT = "flow_tool"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def callback(callback_type: str, **payload) -> dict:
	"""Authenticate once, then hand the payload to its focused callback."""
	_authenticate()
	payload.pop("cmd", None)  # frappe adds the method's name to every API call's arguments
	if callback_type == "tool":
		return tool_callback(**payload)
	if callback_type == "run_ended":
		return run_ended_callback(**payload)
	frappe.throw(_("Unknown callback type {0}.").format(callback_type))


def tool_callback(
	session_id: str,
	tool: str,
	args: dict | None = None,
	mode: str = "execute",
	user_context: dict | None = None,
) -> dict:
	"""Execute a client tool, or build its confirmation prompt, as the session owner."""
	if mode not in ("execute", "confirm"):
		frappe.throw(_("Unknown callback mode {0}.").format(mode))
	session = frappe.db.get_value("Flow Session", session_id, ["owner", "agent"], as_dict=True)
	if not session:
		return _error(_("Unknown session {0}.").format(session_id))
	# a sub-agent's call names it; it must be one of the session agent's sub-agents
	agent = (user_context or {}).get("agent") or session.agent
	if agent != session.agent and not frappe.db.exists(
		"Flow Agent Sub Agent", {"parent": session.agent, "agent": agent}
	):
		return _error(_("{0} is not a sub-agent of {1}.").format(agent, session.agent))
	if not frappe.db.get_value("User", session.owner, "enabled"):
		return _error(_("The session's owner is disabled."))
	user = frappe.session.user
	frappe.set_user(session.owner)
	frappe.db.savepoint(SAVEPOINT)
	try:
		return _dispatch(session_id, agent, tool, args or {}, mode)
	except Exception as exc:
		frappe.db.rollback(save_point=SAVEPOINT)
		return _error(str(exc).strip() or type(exc).__name__)
	finally:
		frappe.set_user(user)


def run_ended_callback(session_id: str, terminal_seq: int) -> dict:
	"""Synchronize a durable run terminal into Flow. Duplicate delivery is safe."""
	try:
		terminal_seq = int(terminal_seq)
	except (TypeError, ValueError):
		terminal_seq = 0
	if terminal_seq < 1:
		frappe.throw(_("Terminal sequence is required."))
	try:
		session = frappe.get_doc("Flow Session", session_id)
	except frappe.DoesNotExistError:
		frappe.throw(_("Unknown session {0}.").format(session_id))
	user = frappe.session.user
	frappe.set_user(session.owner)
	try:
		session.sync()
		if session.last_synced_seq < terminal_seq:
			frappe.throw(
				_("The flow server did not expose terminal sequence {0}.").format(terminal_seq),
				title=_("Flow Server"),
			)
		return {"synced_through": session.last_synced_seq}
	finally:
		frappe.set_user(user)


def _authenticate() -> None:
	secret = frappe.conf.flow_server_secret or ""
	given = frappe.request.headers.get("X-Harness-Token", "")
	if not secret or not compare_digest(given.encode(), secret.encode()):
		raise frappe.AuthenticationError


def _dispatch(session_id: str, agent: str, name: str, args: dict, mode: str) -> dict:
	agent_doc = frappe.get_doc("Flow Agent", agent)
	if not agent_doc.enabled:
		return _error(_("The session's agent is disabled."))
	tools = agent_doc.client_tools(session_id)
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
