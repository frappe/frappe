# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Dispatch MCP operations independently of their HTTP delivery."""

from typing import Any

from frappe.mcp import protocol
from frappe.mcp.protocol import INVALID_PARAMS, METHOD_NOT_FOUND, McpError
from frappe.mcp.skills import SKILLS_EXTENSION, SkillCatalog


def dispatch(method: str, params: dict[str, Any], version: str) -> dict:
	if method == "initialize" and version == protocol.LEGACY_VERSION:
		return initialize(params)
	if method == "ping":
		return {}
	if method == "server/discover" and version == protocol.LATEST_VERSION:
		return {
			"supportedVersions": list(protocol.SUPPORTED_VERSIONS),
			"capabilities": capabilities(),
			**server_configuration(),
			"ttlMs": 3600000,
			"cacheScope": "private",
		}
	if method in ("tools/list", "tools/call"):
		from frappe.mcp import tools

		if method == "tools/list":
			return {"tools": tools.definitions(), "ttlMs": 3600000, "cacheScope": "private"}
		return tools.call(params)
	if method == "resources/list":
		return {"resources": []}
	if method in (
		"skills/list",
		"skills/get",
		"resources/read",
		"resources/directory/read",
	):
		catalog = SkillCatalog()
		if method == "skills/list":
			return catalog.list_skills(params.get("cursor"))
		if method == "skills/get":
			return catalog.get_skill(params.get("uri"))
		if method == "resources/read":
			return catalog.read_resource(params.get("uri"))
		return catalog.read_directory(params.get("uri"), params.get("cursor"))
	raise McpError(METHOD_NOT_FOUND, "Unknown MCP method: {0}".format(method), status=404)


def initialize(params: dict[str, Any]) -> dict:
	if (
		not isinstance(params.get("protocolVersion"), str)
		or not isinstance(params.get("capabilities"), dict)
		or not valid_identity(params.get("clientInfo"))
	):
		raise McpError(INVALID_PARAMS, "initialize requires protocolVersion, capabilities and clientInfo")

	# Modern revisions cannot be negotiated through the legacy handshake.
	return {
		"protocolVersion": protocol.LEGACY_VERSION,
		"capabilities": capabilities(),
		**server_configuration(),
	}


def server_configuration() -> dict:
	return {"serverInfo": protocol.server_info(), "instructions": protocol.server_instructions()}


def capabilities() -> dict:
	return {
		"tools": {"listChanged": False},
		"resources": {},
		"extensions": {SKILLS_EXTENSION: {"directoryRead": True}},
	}


def valid_identity(value: Any) -> bool:
	return isinstance(value, dict) and all(isinstance(value.get(key), str) for key in ("name", "version"))
