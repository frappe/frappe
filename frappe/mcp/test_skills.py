# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import errno
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import frappe
from frappe.mcp import protocol
from frappe.mcp.skills import SKILLS_EXTENSION
from frappe.mcp.test_utils import McpTestCase


class TestSkills(McpTestCase):
	uri = "skill://frappe/refunds"

	def setUp(self):
		super().setUp()
		self.root = Path(self.enterContext(TemporaryDirectory()))
		self.skill = self.root / "refunds"
		self.skill.mkdir()
		(self.skill / "SKILL.md").write_text("---\nname: refunds\ndescription: Example\n---\n")
		self.enterContext(self.change_settings("System Settings", enable_mcp=1, commit=True))
		get_path = frappe.get_app_source_path
		self.enterContext(
			patch(
				"frappe.get_app_source_path",
				side_effect=lambda app, *parts: (
					str(self.root) if app == "frappe" and parts == ("skills",) else get_path(app, *parts)
				),
			)
		)

	def rpc(self, method, params=None):
		params = dict(params or {})
		params["_meta"] = {
			protocol.META_VERSION: protocol.LATEST_VERSION,
			protocol.META_CAPABILITIES: {"extensions": {SKILLS_EXTENSION: {}}},
		}
		headers = {"MCP-Protocol-Version": protocol.LATEST_VERSION, "Mcp-Method": method}
		if method == "resources/read":
			headers["Mcp-Name"] = params["uri"]
		return self.request({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)

	def test_discovery_manifests_and_file_reads(self):
		(self.skill / "sample.bin").write_bytes(b"\x00\xff")
		self.assertEqual(self.rpc("resources/list").json["result"]["resources"], [])
		capabilities = self.rpc("server/discover").json["result"]["capabilities"]
		self.assertIn("resources", capabilities)
		self.assertEqual(capabilities["extensions"][SKILLS_EXTENSION], {"directoryRead": True})
		(entry,) = self.rpc("skills/list").json["result"]["skills"]
		self.assertEqual(self.rpc("skills/get", {"uri": entry["uri"]}).json["result"]["skill"], entry)
		for record in entry["resources"]:
			content = self.rpc("resources/read", {"uri": record["uri"]}).json["result"]["contents"][0]
			raw = content["text"].encode() if "text" in content else base64.b64decode(content["blob"])
			self.assertEqual(
				(record["size"], record["digest"]), (len(raw), "sha256:" + hashlib.sha256(raw).hexdigest())
			)
		directory = self.rpc("resources/directory/read", {"uri": self.uri}).json["result"]["resources"]
		self.assertEqual({item["uri"] for item in directory}, {item["uri"] for item in entry["resources"]})

	def test_hidden_files_and_unsafe_paths_are_rejected(self):
		(self.skill / ".env").write_text("private")
		(self.skill / ".hidden").mkdir()
		(self.skill / ".hidden/SKILL.md").write_text("---\nname: invalid\n---\n")
		(self.root / "private.txt").write_text("outside any skill")
		(self.skill / "escape").symlink_to(self.root, target_is_directory=True)
		(entry,) = self.rpc("skills/list").json["result"]["skills"]
		self.assertEqual([item["uri"] for item in entry["resources"]], [self.uri + "/SKILL.md"])
		directory = self.rpc("resources/directory/read", {"uri": self.uri}).json["result"]["resources"]
		self.assertEqual([item["uri"] for item in directory], [self.uri + "/SKILL.md"])
		for uri in (self.uri + "/.env", self.uri + "/../private.txt", self.uri + "/escape/private.txt"):
			with self.subTest(uri=uri):
				response = self.rpc("resources/read", {"uri": uri})
				self.assertEqual(response.status_code, 400)
				self.assertEqual(response.json["error"]["code"], protocol.INVALID_PARAMS)

	def test_nested_skill_is_independent_of_parent_frontmatter(self):
		child = self.skill / "review"
		child.mkdir()
		(child / "SKILL.md").write_text("---\nname: review\ndescription: Example\n---\n")
		entries = self.rpc("skills/list").json["result"]["skills"]
		self.assertEqual(len(entries), 2)
		self.assertTrue(all(record in entries[0]["resources"] for record in entries[1]["resources"]))
		(self.skill / "SKILL.md").write_text("invalid frontmatter")
		uri = self.uri + "/review/SKILL.md"
		self.assertEqual(self.rpc("skills/get", {"uri": self.uri + "/SKILL.md"}).status_code, 500)
		self.assertEqual(self.rpc("skills/get", {"uri": uri}).json["result"]["skill"], entries[1])
		self.assertIn(
			"name: review", self.rpc("resources/read", {"uri": uri}).json["result"]["contents"][0]["text"]
		)

	def test_filesystem_failures_are_server_errors(self):
		for target, method, params in (
			("os.scandir", "skills/list", {}),
			("frappe.mcp.skill_files.os.open", "resources/read", {"uri": self.uri + "/SKILL.md"}),
		):
			with self.subTest(method=method), patch(target, side_effect=OSError(errno.EIO, "disk failure")):
				response = self.rpc(method, params)
			self.assertEqual(response.status_code, 500)
			self.assertEqual(
				response.json["error"], {"code": protocol.INTERNAL_ERROR, "message": "Internal error"}
			)
