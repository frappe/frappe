# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The primer returned in `DiscoverResult.instructions`.

Adapted from the `frappectl guide` command. It tells an agent how the four tools
relate to each other, and above all to orient with `discover` before it guesses a
DocType name, a field name or a method path.
"""

import frappe

INSTRUCTIONS = r"""This is the MCP server built into a Frappe site. Four tools cover the whole API.

Every call runs as the authenticated user. Frappe permissions, method
whitelisting and OAuth scopes decide what you can see and change. A denied call
returns an error you can read, not a silent empty result.

ORIENT YOURSELF (do this before you guess a DocType name, a field name or a method)
  discover                                   # site summary and the modules present
  discover {"query": "invoice"}              # search DocTypes and whitelisted methods
  discover {"doctype": "Sales Invoice"}      # fields, permissions and methods
  discover {"method": "frappe.client.get_count"}              # one RPC method
  discover {"doctype": "User", "method": "add_comment"}       # one DocType method

READ
  get_documents {"doctype": "ToDo", "name": "abc123"}         # one document
  get_documents {"doctype": "ToDo", "filters": {"status": "Open"},
                 "fields": ["name", "description"],
                 "order_by": "creation desc", "limit": 50}
  get_documents {"doctype": "ToDo", "filters": {"status": "Open"}, "count_only": true}

  Filters take a dict of equalities, or a list for other operators, such as
  [["status", "in", ["Open", "Closed"]]]. The result reports `has_next_page`;
  page with `start` and `limit`.

WRITE
  write_document {"action": "create", "doctype": "ToDo", "data": {"description": "Follow up"}}
  write_document {"action": "update", "doctype": "ToDo", "name": "abc123", "data": {"status": "Closed"}}
  write_document {"action": "delete", "doctype": "ToDo", "name": "abc123"}

  Lifecycle actions are DocType methods, not write actions. Submit, cancel and
  amend go through call_method.

EVERYTHING ELSE
  call_method is the escape hatch. It reaches every whitelisted method on the
  site, so it also covers reports, read-only SQL, file upload and app specific
  business logic.

  call_method {"method": "frappe.desk.query_report.run",
               "args": {"report_name": "Permitted Documents For User"}}
  call_method {"doctype": "Sales Invoice", "name": "SINV-0001", "method": "submit"}
  call_method {"method": "frappe.desk.doctype.system_console.system_console.execute_code",
               "args": {"doc": {"doctype": "System Console", "type": "SQL",
                                "console": "select count(*) from tabUser"}}}

  Use discover to read a method's parameters before you call it.
"""


def render() -> str:
	return f"Site: {frappe.local.site}\n\n{INSTRUCTIONS}"
