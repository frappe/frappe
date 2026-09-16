# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Who may use Flow. Three checks, each answering one question:

- Base access: Flow Users use Flow within their own records; System Managers administer all
  records. Deliberate Frappe shares may delegate an individual record.
- Doctype permissions: which agents and models. User Permissions narrow them per user; checked
  when a session starts and on every turn.
- Ownership: sessions and runs belong to whoever created them; System Managers see all.

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


def has_app_permission() -> bool:
	"""Whether the apps screen lists Flow: anyone who may read sessions."""
	return frappe.has_permission("Flow Session", "read")
