# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""HTTP concerns of the MCP endpoint.

Origin check, header validation, body parsing and the mapping from a protocol
error to an HTTP status code. Everything else is in `server.py`.
"""

import base64
import binascii
import json
from typing import Any

from werkzeug.wrappers import Request, Response

import frappe
from frappe.mcp import protocol, server
from frappe.mcp.protocol import (
	HEADER_MISMATCH,
	INVALID_REQUEST,
	PARSE_ERROR,
	SUPPORTED_VERSIONS,
	UNSUPPORTED_PROTOCOL_VERSION,
	McpError,
)

BASE64_SENTINEL_PREFIX = "=?base64?"
BASE64_SENTINEL_SUFFIX = "?="


def handle_request(request: Request) -> Response:
	request_id = None
	try:
		if request.method != "POST":
			# No GET SSE stream and no session to delete, so nothing else is answerable.
			raise McpError(INVALID_REQUEST, "Only POST is supported on this endpoint", http_status_code=405)

		_check_origin(request)
		_check_authentication()

		payload = _parse_body(request)
		if payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
			raise McpError(INVALID_REQUEST, "Body is not a JSON-RPC 2.0 request")

		if payload.get("id") is None:
			# A notification. Nothing to answer, but the request was accepted.
			return Response(status=202)

		request_id = payload["id"]
		version = _request_version(request, payload)
		if version in protocol.STRICT_VERSIONS:
			_check_headers(request, payload)

		result = server.dispatch(payload["method"], payload.get("params") or {})
		return _json_response(protocol.result_envelope(request_id, result, version))
	except McpError as e:
		return _json_response(protocol.error_envelope(request_id, e), status=e.http_status_code)


def _request_version(request: Request, payload: dict[str, Any]) -> str:
	"""The revision this request speaks.

	`initialize` is the one request that carries no version header: the client
	sends it to find out what the server supports. Its own version lives in the
	body and `server.initialize` negotiates against it, so the envelope for that
	response follows the handshake revision.

	Every later request carries the header. A request without one predates the
	revision that introduced the header, so it is answered on those terms.
	"""
	if payload["method"] in server.HANDSHAKE_METHODS:
		return protocol.HANDSHAKE_VERSION

	version = request.headers.get("MCP-Protocol-Version")
	if not version:
		return protocol.HANDSHAKE_VERSION

	if version not in SUPPORTED_VERSIONS:
		raise McpError(
			UNSUPPORTED_PROTOCOL_VERSION,
			f"Protocol version {version} is not supported",
			data={"supported": list(SUPPORTED_VERSIONS), "requested": version},
		)

	return version


def _check_origin(request: Request) -> None:
	"""Reject a cross origin browser request unless the site allows that origin.

	Without this a page in the user's browser could reach a local MCP server
	through DNS rebinding. Non browser clients send no `Origin` header.
	"""
	origin = request.headers.get("Origin")
	if not origin:
		return

	allowed = getattr(frappe.local, "allow_cors", None) or frappe.conf.allow_cors
	if allowed == "*":
		return

	if not isinstance(allowed, list):
		allowed = [allowed] if allowed else []

	if origin not in allowed:
		raise McpError(INVALID_REQUEST, f"Origin {origin} is not allowed", http_status_code=403)


def _check_authentication() -> None:
	if frappe.session.user == "Guest":
		# `process_response` adds the `WWW-Authenticate` challenge on a 401.
		raise McpError(INVALID_REQUEST, "Authentication required", http_status_code=401)


def _parse_body(request: Request) -> dict[str, Any]:
	try:
		payload = json.loads(request.get_data(as_text=True) or "")
	except ValueError:
		raise McpError(PARSE_ERROR, "Body is not valid JSON")

	if not isinstance(payload, dict):
		# Batching was removed from the protocol, so an array is not a valid body.
		raise McpError(INVALID_REQUEST, "Body must be a single JSON-RPC request")

	return payload


def _check_headers(request: Request, payload: dict[str, Any]) -> None:
	"""The transport headers must agree with the body they describe.

	They let a proxy route and a gateway authorize a call without parsing the
	body, so a disagreement between the two is a security relevant error.
	"""
	params = payload.get("params") or {}
	meta = params.get("_meta") or {} if isinstance(params, dict) else {}

	header_version = request.headers.get("MCP-Protocol-Version")
	body_version = meta.get(protocol.META_PROTOCOL_VERSION)
	if not header_version or header_version != body_version:
		raise McpError(
			HEADER_MISMATCH,
			"MCP-Protocol-Version header must match params._meta protocol version",
		)

	header_method = request.headers.get("Mcp-Method")
	if not header_method or header_method != payload["method"]:
		raise McpError(HEADER_MISMATCH, "Mcp-Method header must match the request method")

	if payload["method"] != "tools/call":
		return

	header_name = _decode_header_value(request.headers.get("Mcp-Name"))
	if not header_name or header_name != params.get("name"):
		raise McpError(HEADER_MISMATCH, "Mcp-Name header must match params.name")


def _decode_header_value(value: str | None) -> str | None:
	"""Decode the `=?base64?…?=` sentinel used for values outside US-ASCII."""
	if not value or not value.startswith(BASE64_SENTINEL_PREFIX):
		return value

	if not value.endswith(BASE64_SENTINEL_SUFFIX):
		return value

	encoded = value[len(BASE64_SENTINEL_PREFIX) : -len(BASE64_SENTINEL_SUFFIX)]
	try:
		return base64.b64decode(encoded, validate=True).decode("utf-8")
	except (binascii.Error, UnicodeDecodeError):
		raise McpError(HEADER_MISMATCH, "Mcp-Name header is not valid base64")


def _json_response(body: dict[str, Any], status: int = 200) -> Response:
	return Response(
		json.dumps(body, default=str),
		status=status,
		content_type="application/json",
	)
