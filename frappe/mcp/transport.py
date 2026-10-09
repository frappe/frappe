# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Streamable HTTP with final JSON responses and no protocol session store."""

import base64
import binascii
import json
from typing import Any

import orjson
from werkzeug.wrappers import Request, Response

import frappe
from frappe import _
from frappe.mcp import protocol, server
from frappe.mcp.protocol import McpError


def handle_request(request: Request) -> Response:
	request_id = None
	version = protocol.LEGACY_VERSION
	try:
		if request.method != "POST":
			raise McpError(protocol.INVALID_REQUEST, _("Only POST is supported"), status=405)
		check_origin(request)
		if frappe.session.user == "Guest":
			raise McpError(protocol.INVALID_REQUEST, _("Authentication required"), status=401)
		if not request.is_json:
			raise McpError(protocol.INVALID_REQUEST, _("Content-Type must be application/json"), status=415)
		if not request.accept_mimetypes["application/json"]:
			raise McpError(protocol.INVALID_REQUEST, _("Accept must allow application/json"), status=406)

		payload = parse_body(request)
		request_id = payload.get("id")
		params = payload.get("params", {})
		version = request_version(request, params)
		if version == protocol.LATEST_VERSION:
			check_headers(request, payload, params)
			check_metadata(params)

		if "id" not in payload:
			# Notifications never execute a tool and never receive a JSON-RPC response.
			return Response(status=202)

		result = server.dispatch(payload["method"], params, version)
		return json_response(protocol.result_envelope(request_id, result, version))
	except McpError as error:
		response = json_response(protocol.error_envelope(request_id, error, version), error.status)
		if error.status == 405:
			response.headers["Allow"] = "POST"
		return response


def parse_body(request: Request) -> dict[str, Any]:
	try:
		payload = orjson.loads(request.get_data())
	except (ValueError, UnicodeDecodeError):
		raise McpError(protocol.PARSE_ERROR, _("Body is not valid JSON")) from None

	if (
		not isinstance(payload, dict)
		or payload.get("jsonrpc") != "2.0"
		or not isinstance(payload.get("method"), str)
		or not isinstance(payload.get("params", {}), dict)
		or "result" in payload
		or "error" in payload
	):
		raise McpError(protocol.INVALID_REQUEST, _("Body must be one JSON-RPC request or notification"))
	if "id" in payload and type(payload["id"]) not in (str, int):
		raise McpError(protocol.INVALID_REQUEST, _("Request id must be a string or integer"))
	return payload


def request_version(request: Request, params: dict) -> str:
	version = request.headers.get("MCP-Protocol-Version")
	meta = params.get("_meta", {})
	if not version:
		if isinstance(meta, dict) and meta.get(protocol.META_VERSION) == protocol.LATEST_VERSION:
			raise McpError(protocol.HEADER_MISMATCH, _("MCP-Protocol-Version header is required"))
		return protocol.LEGACY_VERSION
	if version not in protocol.SUPPORTED_VERSIONS:
		raise McpError(
			protocol.UNSUPPORTED_VERSION,
			_("Unsupported MCP protocol version"),
			data={"supported": list(protocol.SUPPORTED_VERSIONS), "requested": version},
		)
	return version


def check_headers(request: Request, payload: dict, params: dict) -> None:
	meta = params.get("_meta")
	if not isinstance(meta, dict) or request.headers["MCP-Protocol-Version"] != meta.get(
		protocol.META_VERSION
	):
		raise McpError(protocol.HEADER_MISMATCH, _("Protocol version header must match request metadata"))
	if request.headers.get("Mcp-Method") != payload["method"]:
		raise McpError(protocol.HEADER_MISMATCH, _("Mcp-Method header must match method"))
	if payload["method"] == "tools/call":
		if decode_name(request.headers.get("Mcp-Name")) != params.get("name") or "name" not in params:
			raise McpError(protocol.HEADER_MISMATCH, _("Mcp-Name header must match the tool name"))


def check_metadata(params: dict) -> None:
	meta = params["_meta"]
	if not isinstance(meta.get(protocol.META_CAPABILITIES), dict):
		raise McpError(protocol.INVALID_PARAMS, _("Client capabilities must be provided as an object"))
	if protocol.META_CLIENT in meta and not server.valid_identity(meta[protocol.META_CLIENT]):
		raise McpError(protocol.INVALID_PARAMS, _("Client identity requires a name and version"))


def check_origin(request: Request) -> None:
	origin = request.headers.get("Origin")
	if not origin or origin == request.host_url.rstrip("/"):
		return
	allowed = getattr(frappe.local, "allow_cors", None) or frappe.conf.get("allow_cors", [])
	if allowed == "*" or origin in (allowed if isinstance(allowed, list) else [allowed]):
		return
	raise McpError(protocol.INVALID_REQUEST, _("Request origin is not allowed"), status=403)


def decode_name(value: str | None) -> str | None:
	if value is None:
		return None
	if not value.isascii() or any(ord(char) < 32 or ord(char) == 127 for char in value):
		raise McpError(protocol.HEADER_MISMATCH, _("Mcp-Name header contains invalid characters"))
	if value.startswith("=?base64?") and value.endswith("?="):
		try:
			return base64.b64decode(value[9:-2], validate=True).decode("utf-8")
		except (binascii.Error, UnicodeDecodeError):
			raise McpError(protocol.HEADER_MISMATCH, _("Mcp-Name header is not valid base64")) from None
	return value


def json_response(body: dict, status: int = 200) -> Response:
	from frappe.utils.response import json_handler

	return Response(json.dumps(body, default=json_handler), status=status, mimetype="application/json")
