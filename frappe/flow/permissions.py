# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Who may use Flow. Three checks, each answering one question:

- Base access: Flow Users use Flow within their own records; System Managers administer its
  setup. An owner may share a session, to view only.
- Doctype permissions: which agents and models. An agent or model with roles is only for users
  holding one, and User Permissions narrow both per user; checked when a session starts and on
  every turn. A user who may not use an agent's model picks another. A sub-agent comes with the
  agent that has it, model included, like its tools and knowledge bases. Flow Users read the
  skills of the agents open to them.
- Ownership: sessions, runs and personal memories are private to their owner, since a session's
  tools run as them. System Managers also see Trigger sessions, and an owner may open a session
  to view by every Flow user.

Triggers run as their run_as account or owner, which must be able to read the agent. The flow
server's callbacks act as the session owner."""

from __future__ import annotations

import frappe

FLOW_USER_ROLE = "Flow User"


def ensure_flow_role() -> None:
	"""Create the role on install and migrate."""
	if frappe.db.exists("Role", FLOW_USER_ROLE):
		return
	frappe.get_doc({"doctype": "Role", "role_name": FLOW_USER_ROLE, "desk_access": 1}).insert(
		ignore_permissions=True, ignore_if_duplicate=True
	)


def has_session_permission(doc, ptype: str, user: str) -> bool:
	"""Allows the owner, anyone reading a chat open to everyone, and System Managers on Trigger chats."""
	if user in (doc.owner, "Administrator"):
		return True
	if ptype == "read" and doc.get("general_access") == "Everyone":
		return True
	return doc.source == "Trigger" and "System Manager" in frappe.get_roles(user)


def session_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	"""Limits lists to your own chats, plus Trigger chats for System Managers."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	owned = f"`tab{doctype}`.`owner` = {frappe.db.escape(user)}"
	if "System Manager" in frappe.get_roles(user):
		return f"({owned} or `tab{doctype}`.`source` = 'Trigger')"
	return f"({owned})"


def has_memory_permission(doc, user: str) -> bool:
	"""A personal memory is private to its user."""
	return doc.scope != "User" or user in (doc.user, "Administrator")


def memory_query_conditions(user: str | None = None) -> str:
	"""The list side of has_memory_permission."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	user = frappe.db.escape(user)
	return f"(`tabFlow Agent Memory`.`scope` != 'User' or `tabFlow Agent Memory`.`user` = {user})"


def has_role_permission(doc, user: str) -> bool:
	"""An agent or model with roles is only for users holding one; System Managers see all."""
	roles = frappe.get_roles(user)
	return "System Manager" in roles or not doc.roles or any(row.role in roles for row in doc.roles)


def role_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	"""The list side of has_role_permission."""
	roles = frappe.get_roles(user or frappe.session.user)
	if "System Manager" in roles:
		return ""
	with_roles = f"select `parent` from `tabHas Role` where `parenttype` = {frappe.db.escape(doctype)}"
	user_roles = ", ".join(frappe.db.escape(role) for role in roles)
	record = f"`tab{doctype}`.`name`"
	return f"({record} not in ({with_roles}) or {record} in ({with_roles} and `role` in ({user_roles})))"


def has_skill_permission(doc, user: str) -> bool:
	"""Flow Users read the enabled skills that are global or bound to an agent open to them."""
	if "System Manager" in frappe.get_roles(user):
		return True
	if not doc.enabled:
		return False
	agents = frappe.get_all("Flow Agent Skill", filters={"skill": doc.name}, pluck="parent")
	return bool(doc.is_global) or any(
		frappe.has_permission("Flow Agent", "read", agent, user=user) for agent in agents
	)


def skill_query_conditions(user: str | None = None) -> str:
	"""The list side of has_skill_permission."""
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""
	readable = frappe.get_list("Flow Agent", pluck="name", user=user)
	agents = ", ".join(frappe.db.escape(name) for name in readable) or "''"
	bound = f"select `skill` from `tabFlow Agent Skill` where `parent` in ({agents})"
	skill = "`tabFlow Skill`"
	return f"({skill}.`enabled` = 1 and ({skill}.`is_global` = 1 or {skill}.`name` in ({bound})))"
