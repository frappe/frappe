# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Constants and JSON-RPC envelope builders for the MCP endpoint.

Two revisions are implemented, because they differ in how a client announces
the protocol version:

- `2026-07-28` removes the `initialize` handshake and the protocol level
  session. Every request carries its own version, identity and capabilities, in
  transport headers that a proxy can route on without parsing the body.
- `2025-11-25` negotiates the version once, through `initialize`. The client
  cannot send the version header on that first request, because it does not yet
  know what the server supports.

Shipping clients speak the second one, so the server answers both and lets the
client choose.
"""

from typing import Any

import frappe

LATEST_VERSION = "2026-07-28"
HANDSHAKE_VERSION = "2025-11-25"

# Newest first: the version offered when a client asks for one we do not know.
SUPPORTED_VERSIONS = (LATEST_VERSION, HANDSHAKE_VERSION)

# Revisions that require the transport headers to agree with the body.
STRICT_VERSIONS = (LATEST_VERSION,)

PROTOCOL_VERSION = LATEST_VERSION

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


def result_envelope(id: Any, result: dict[str, Any], version: str = LATEST_VERSION) -> dict[str, Any]:
	"""Wrap a result in a JSON-RPC response.

	`resultType` and the `_meta` server info belong to the newer revision. An
	older client would ignore them, but it never asked for them either.
	"""
	if version in STRICT_VERSIONS:
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
