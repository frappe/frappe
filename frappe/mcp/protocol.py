# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Supported revisions and JSON-RPC response envelopes."""

import re
from typing import Any

import frappe
from frappe.utils import get_fullname, get_host_name

LATEST_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"
SUPPORTED_VERSIONS = (LATEST_VERSION, LEGACY_VERSION)
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_CLIENT = "io.modelcontextprotocol/clientInfo"
META_SERVER = "io.modelcontextprotocol/serverInfo"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
HEADER_MISMATCH = -32020
UNSUPPORTED_VERSION = -32022


class McpError(Exception):
	"""An error in the protocol, rather than a failed tool operation."""

	def __init__(self, code: int, message: str, status: int = 400, data: dict | None = None):
		super().__init__(message)
		self.code = code
		self.http_status_code = status
		self.data = data


def server_info() -> dict[str, str]:
	name = (frappe.get_system_settings("server_name") or "").strip()
	return {"name": name or default_server_name(), "version": frappe.__version__}


def default_server_name() -> str:
	return re.sub(r"[^a-z0-9]+", "_", get_host_name().lower()).strip("_")


def server_instructions() -> str:
	lines = [
		"This is a Frappe Framework site at {0}.".format(get_host_name()),
		"You are connected as {0} ({1}).".format(get_fullname(), frappe.session.user),
		"Tool arguments take the same values as the matching Frappe REST API v2 endpoints.",
		"For example, filters, fields and order_by work as in GET /api/v2/document/<doctype>.",
		"Installed apps:",
	]
	for app in frappe.get_installed_apps():
		title = (frappe.get_hooks("app_title", app_name=app) or [app])[0]
		lines.append(f"- {title} ({app})")

	instructions = "\n".join(lines)
	if site_instructions := (frappe.get_system_settings("agent_instructions") or "").strip():
		instructions += "\n\n" + site_instructions
	return instructions


def result_envelope(request_id: str | int, result: dict, version: str) -> dict[str, Any]:
	if version == LATEST_VERSION:
		result = {
			**result,
			"resultType": "complete",
			"_meta": {**result.get("_meta", {}), META_SERVER: server_info()},
		}
	else:
		result = {key: value for key, value in result.items() if key not in ("ttlMs", "cacheScope")}

	return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_envelope(request_id: str | int | None, error: McpError, version: str) -> dict[str, Any]:
	result = {"jsonrpc": "2.0", "error": {"code": error.code, "message": str(error)}}
	if request_id is not None or version == LEGACY_VERSION:
		result["id"] = request_id
	if error.data is not None:
		result["error"]["data"] = error.data
	return result
