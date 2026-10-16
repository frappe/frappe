# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class MCPSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent_instructions: DF.LongText | None
		enable_mcp: DF.Check
		server_name: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "MCP Settings"
