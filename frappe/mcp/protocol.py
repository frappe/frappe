# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Supported revisions and JSON-RPC response envelopes."""

from typing import Any

import frappe

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
HEADER_MISMATCH = -32020
UNSUPPORTED_VERSION = -32022


class McpError(Exception):
	"""An error in the protocol, rather than a failed tool operation."""

	def __init__(self, code: int, message: str, status: int = 400, data: dict | None = None):
		super().__init__(message)
		self.code = code
		self.status = status
		self.data = data


def server_info() -> dict[str, str]:
	settings = frappe.get_cached_doc("MCP Settings")
	info = {"name": (settings.server_name or "").strip() or frappe.local.site, "version": frappe.__version__}
	if description := (settings.server_description or "").strip():
		info["description"] = description
	return info


def server_instructions() -> str:
	return (frappe.get_cached_doc("MCP Settings").agent_instructions or "").strip()


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
