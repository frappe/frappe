# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Streamable HTTP with final JSON responses and no protocol session store."""

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

import orjson
from werkzeug.wrappers import Request, Response

import frappe
from frappe.mcp import protocol, server
from frappe.mcp.protocol import McpError
from frappe.permissions import SYSTEM_USER_ROLE


@dataclass
class RequestContext:
	"""What `error_response` needs to answer in the same JSON-RPC envelope as the request."""

	id: str | int | None = None
	version: str = protocol.LEGACY_VERSION
	method: str | None = None


def handle_request(request: Request) -> Response:
	"""Errors propagate to `frappe.app`, which rolls back and responds with `error_response`."""
	context = frappe.local.mcp_request = RequestContext()
	if request.method != "POST":
		raise McpError(protocol.INVALID_REQUEST, "Only POST is supported", status=405)
	check_origin(request)
	if frappe.session.user == "Guest":
		raise McpError(protocol.INVALID_REQUEST, "Authentication required", status=401)
	if SYSTEM_USER_ROLE not in frappe.get_roles():
		raise McpError(protocol.INVALID_REQUEST, "MCP is only available to desk users", status=403)
	if not request.is_json:
		raise McpError(protocol.INVALID_REQUEST, "Content-Type must be application/json", status=415)
	if not request.accept_mimetypes["application/json"]:
		raise McpError(protocol.INVALID_REQUEST, "Accept must allow application/json", status=406)

	payload = parse_body(request)
	context.id = payload.get("id")
	params = payload.get("params", {})
	context.version = request_version(request, params)
	if context.version == protocol.LATEST_VERSION:
		check_headers(request, payload, params)
		check_metadata(params)

	if "id" not in payload:
		# Notifications never execute a tool and never receive a JSON-RPC response.
		return Response(status=202)

	context.method = payload["method"]
	result = server.dispatch(context.method, params, context.version)
	return json_response(protocol.result_envelope(context.id, result, context.version))


def error_response(error: Exception) -> Response:
	context: RequestContext = frappe.local.mcp_request
	if not isinstance(error, McpError):
		if context.method == "tools/call":
			# A failed tool is a tool result, so the model can read the error and recover.
			from frappe.mcp.tools import error_result

			result = error_result(str(error) or type(error).__name__)
			return json_response(protocol.result_envelope(context.id, result, context.version))

		status = getattr(error, "http_status_code", 500)
		message = str(error) if status < 500 and str(error) else "Internal error"
		error = McpError(protocol.INTERNAL_ERROR, message, status=status)

	response = json_response(
		protocol.error_envelope(context.id, error, context.version), error.http_status_code
	)
	if error.http_status_code == 405:
		response.headers["Allow"] = "POST"
	return response


def parse_body(request: Request) -> dict[str, Any]:
	try:
		payload = orjson.loads(request.get_data())
	except (ValueError, UnicodeDecodeError):
		raise McpError(protocol.PARSE_ERROR, "Body is not valid JSON") from None

	if (
		not isinstance(payload, dict)
		or payload.get("jsonrpc") != "2.0"
		or not isinstance(payload.get("method"), str)
		or not isinstance(payload.get("params", {}), dict)
		or "result" in payload
		or "error" in payload
	):
		raise McpError(protocol.INVALID_REQUEST, "Body must be one JSON-RPC request or notification")
	if "id" in payload and type(payload["id"]) not in (str, int):
		raise McpError(protocol.INVALID_REQUEST, "Request id must be a string or integer")
	return payload


def request_version(request: Request, params: dict) -> str:
	version = request.headers.get("MCP-Protocol-Version")
	meta = params.get("_meta", {})
	if not version:
		if isinstance(meta, dict) and meta.get(protocol.META_VERSION) == protocol.LATEST_VERSION:
			raise McpError(protocol.HEADER_MISMATCH, "MCP-Protocol-Version header is required")
		return protocol.LEGACY_VERSION
	if version not in protocol.SUPPORTED_VERSIONS:
		raise McpError(
			protocol.UNSUPPORTED_VERSION,
			"Unsupported MCP protocol version",
			data={"supported": list(protocol.SUPPORTED_VERSIONS), "requested": version},
		)
	return version


def check_headers(request: Request, payload: dict, params: dict) -> None:
	meta = params.get("_meta")
	if not isinstance(meta, dict) or request.headers["MCP-Protocol-Version"] != meta.get(
		protocol.META_VERSION
	):
		raise McpError(protocol.HEADER_MISMATCH, "Protocol version header must match request metadata")
	if request.headers.get("Mcp-Method") != payload["method"]:
		raise McpError(protocol.HEADER_MISMATCH, "Mcp-Method header must match method")
	if payload["method"] == "tools/call":
		if decode_name(request.headers.get("Mcp-Name")) != params.get("name") or "name" not in params:
			raise McpError(protocol.HEADER_MISMATCH, "Mcp-Name header must match the tool name")


def check_metadata(params: dict) -> None:
	meta = params["_meta"]
	if not isinstance(meta.get(protocol.META_CAPABILITIES), dict):
		raise McpError(protocol.INVALID_PARAMS, "Client capabilities must be provided as an object")
	if protocol.META_CLIENT in meta and not server.valid_identity(meta[protocol.META_CLIENT]):
		raise McpError(protocol.INVALID_PARAMS, "Client identity requires a name and version")


def check_origin(request: Request) -> None:
	origin = request.headers.get("Origin")
	if not origin or origin == request.host_url.rstrip("/"):
		return
	allowed = getattr(frappe.local, "allow_cors", None) or frappe.conf.get("allow_cors", [])
	if allowed == "*" or origin in (allowed if isinstance(allowed, list) else [allowed]):
		return
	raise McpError(protocol.INVALID_REQUEST, "Request origin is not allowed", status=403)


def decode_name(value: str | None) -> str | None:
	if value is None:
		return None
	if not value.isascii() or any(ord(char) < 32 or ord(char) == 127 for char in value):
		raise McpError(protocol.HEADER_MISMATCH, "Mcp-Name header contains invalid characters")
	if value.startswith("=?base64?") and value.endswith("?="):
		try:
			return base64.b64decode(value[9:-2], validate=True).decode("utf-8")
		except (binascii.Error, UnicodeDecodeError):
			raise McpError(protocol.HEADER_MISMATCH, "Mcp-Name header is not valid base64") from None
	return value


def json_response(body: dict, status: int = 200) -> Response:
	from frappe.utils.response import json_handler

	return Response(json.dumps(body, default=json_handler), status=status, mimetype="application/json")
