# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Dispatch of the three RPC methods this server implements."""

from typing import Any

import frappe
from frappe.mcp import instructions, protocol, tools
from frappe.mcp.protocol import INVALID_PARAMS, METHOD_NOT_FOUND, McpError


def dispatch(method: str, params: dict[str, Any]) -> dict[str, Any]:
	handler = RPC_METHODS.get(method)
	if not handler:
		raise McpError(METHOD_NOT_FOUND, f"Unknown method {method}", http_status_code=404)

	return handler(params)


def discover(params: dict[str, Any]) -> dict[str, Any]:
	return {
		"supportedVersions": list(protocol.SUPPORTED_VERSIONS),
		"capabilities": {"tools": {}},
		"serverInfo": protocol.server_info(),
		"instructions": instructions.render(),
		"ttlMs": protocol.DISCOVER_TTL_MS,
		"cacheScope": "public",
	}


def list_tools(params: dict[str, Any]) -> dict[str, Any]:
	return {
		"tools": tools.definitions(),
		"ttlMs": protocol.TOOLS_TTL_MS,
		# The visible surface follows the caller's permissions and OAuth scopes.
		"cacheScope": "private",
	}


def call_tool(params: dict[str, Any]) -> dict[str, Any]:
	name = params.get("name")
	if not isinstance(name, str):
		raise McpError(INVALID_PARAMS, "params.name is required")

	arguments = params.get("arguments") or {}
	if not isinstance(arguments, dict):
		raise McpError(INVALID_PARAMS, "params.arguments must be an object")

	return tools.call(name, arguments)


RPC_METHODS = {
	"server/discover": discover,
	"tools/list": list_tools,
	"tools/call": call_tool,
}
