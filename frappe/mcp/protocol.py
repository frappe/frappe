# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Constants and JSON-RPC envelope builders for the MCP endpoint.

Only the `2026-07-28` revision is implemented. That revision has no `initialize`
handshake and no protocol level session: every request carries its own protocol
version, identity and capabilities.
"""

from typing import Any

import frappe

PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = (PROTOCOL_VERSION,)

SERVER_NAME = "frappe"

# `_meta` keys reserved by the specification.
META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

# Result cache lifetimes, in milliseconds.
DISCOVER_TTL_MS = 60 * 60 * 1000
TOOLS_TTL_MS = 5 * 60 * 1000

# JSON-RPC 2.0 errors.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# MCP transport errors.
HEADER_MISMATCH = -32020
UNSUPPORTED_PROTOCOL_VERSION = -32022


class McpError(Exception):
	"""A protocol level error, returned as a JSON-RPC `error` object."""

	def __init__(
		self,
		code: int,
		message: str,
		http_status_code: int = 400,
		data: dict[str, Any] | None = None,
	):
		super().__init__(message)
		self.code = code
		self.message = message
		self.http_status_code = http_status_code
		self.data = data


def server_info() -> dict[str, str]:
	return {"name": SERVER_NAME, "version": frappe.__version__}


def result_envelope(id: Any, result: dict[str, Any]) -> dict[str, Any]:
	"""Wrap a result in a JSON-RPC response, with the fields every result carries."""
	result = {"resultType": "complete", **result}
	meta = dict(result.get("_meta") or {})
	meta[META_SERVER_INFO] = server_info()
	result["_meta"] = meta

	return {"jsonrpc": "2.0", "id": id, "result": result}


def error_envelope(id: Any, error: McpError) -> dict[str, Any]:
	body: dict[str, Any] = {"code": error.code, "message": error.message}
	if error.data is not None:
		body["data"] = error.data

	return {"jsonrpc": "2.0", "id": id, "error": body}
