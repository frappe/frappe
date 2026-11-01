# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import errno
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from frappe.mcp import protocol
from frappe.mcp.skills import SkillCatalog
from frappe.tests import UnitTestCase


class SkillFixtures:
	def setup_skills(self):
		self.directory = TemporaryDirectory()
		self.addCleanup(self.directory.cleanup)
		self.root = Path(self.directory.name)
		self.write_skill("frappe", "billing/refunds")
		self.write_skill("frappe", "billing/refunds/review")
		self.write_file("frappe", "billing/refunds/references/rules one.md", "Refund café.\r\n".encode())
		self.write_file("frappe", "billing/refunds/assets/sample.bin", b"\x00\xff\x80")
		self.write_file("frappe", "private.txt", b"Outside any skill")
		self.write_file("frappe", "billing/refunds/.env", b"SECRET=fixture-only")
		self.write_skill("frappe", "billing/refunds/.cache/hidden")

	def write_skill(self, app, path, frontmatter=""):
		name = Path(path).name
		return self.write_file(
			app,
			f"{path}/SKILL.md",
			f"---\nname: {name}\ndescription: Use {name}.\n{frontmatter}---\n\nRead references as needed.\n".encode(),
		)

	def write_file(self, app, path, content):
		file = self.root / app / "skills" / path
		file.parent.mkdir(parents=True, exist_ok=True)
		file.write_bytes(content)
		return file


class TestSkillCatalog(SkillFixtures, UnitTestCase):
	def setUp(self):
		self.setup_skills()
		self.write_skill("other", "billing/refunds")
		self.write_skill("uninstalled", "private")
		self.enterContext(patch("frappe.get_installed_apps", return_value=["frappe", "other", "empty"]))
		self.enterContext(
			patch(
				"frappe.get_app_source_path",
				side_effect=lambda app, *parts: str(self.root / app / Path(*parts)),
			)
		)
		self.catalog = SkillCatalog()

	def test_nested_skills_have_flat_entries_and_overlapping_manifests(self):
		entries = {entry["uri"]: entry for entry in self.catalog.list_skills()["skills"]}
		self.assertEqual(
			set(entries),
			{
				"skill://frappe/billing/refunds/SKILL.md",
				"skill://frappe/billing/refunds/review/SKILL.md",
				"skill://other/billing/refunds/SKILL.md",
			},
		)
		parent = entries["skill://frappe/billing/refunds/SKILL.md"]
		child = entries["skill://frappe/billing/refunds/review/SKILL.md"]
		self.assertIn(child["resources"][0], parent["resources"])
		self.assertEqual(self.catalog.get_skill(child["uri"])["skill"], child)
		self.assertEqual(len(parent["resources"]), 4)
		self.write_file("frappe", "billing/refunds/review/check.md", b"New rules")
		updated_parent = self.catalog.get_skill(parent["uri"])["skill"]
		updated_child = self.catalog.get_skill(child["uri"])["skill"]
		self.assertEqual(len(updated_parent["resources"]), 5)
		self.assertEqual(len(updated_child["resources"]), 2)
		self.assertTrue(
			all(resource in updated_parent["resources"] for resource in updated_child["resources"])
		)

	def test_manifests_match_the_exact_bytes_returned_by_resource_reads(self):
		self.write_file("frappe", "billing/refunds/references/price#1%.txt", b"Price")
		entry = self.catalog.get_skill("skill://frappe/billing/refunds/SKILL.md")["skill"]
		for resource in entry["resources"]:
			with self.subTest(uri=resource["uri"]):
				content = self.catalog.read_resource(resource["uri"])["contents"][0]
				raw = content["text"].encode() if "text" in content else base64.b64decode(content["blob"])
				self.assertEqual(resource["size"], len(raw))
				self.assertEqual(resource["digest"], "sha256:" + hashlib.sha256(raw).hexdigest())
				self.assertEqual(content["uri"], resource["uri"])
		text = self.catalog.read_resource("skill://frappe/billing/refunds/references/rules%20one.md")
		self.assertEqual(text["contents"][0]["text"], "Refund café.\r\n")
		uri = "skill://frappe/billing/refunds/references/price%231%25.txt"
		self.assertIn(uri, {resource["uri"] for resource in entry["resources"]})
		self.assertEqual(self.catalog.read_resource(uri)["contents"][0]["text"], "Price")
		binary = self.catalog.read_resource("skill://frappe/billing/refunds/assets/sample.bin")
		self.assertEqual(base64.b64decode(binary["contents"][0]["blob"]), b"\x00\xff\x80")

	def test_all_frontmatter_fields_are_preserved(self):
		self.write_skill(
			"frappe",
			"example",
			"license: MIT\nallowed-tools: read\nmetadata:\n  version: '1.0'\nfuture: [a, b]\n",
		)
		metadata = self.catalog.get_skill("skill://frappe/example/SKILL.md")["skill"]["frontmatter"]
		self.assertEqual(metadata["metadata"], {"version": "1.0"})
		self.assertEqual(metadata["future"], ["a", "b"])
		self.assertEqual(metadata["allowed-tools"], "read")
		self.assertEqual(metadata["license"], "MIT")

	def test_directories_include_only_direct_children(self):
		(self.root / "frappe/skills/billing/refunds/assets/empty").mkdir()
		for uri, expected in (
			("skill://frappe", {"billing"}),
			("skill://frappe/billing", {"refunds"}),
			("skill://frappe/billing/refunds", {"refunds", "review", "assets", "references"}),
			("skill://frappe/billing/refunds/references", {"rules one.md"}),
			("skill://frappe/billing/refunds/assets/empty", set()),
		):
			with self.subTest(uri=uri):
				resources = self.catalog.read_directory(uri)["resources"]
				self.assertEqual({item["name"] for item in resources}, expected)
				self.assertTrue(all(item["uri"].rsplit("/", 1)[0] == uri for item in resources))
		resources = self.catalog.read_directory("skill://frappe/billing/refunds")["resources"]
		self.assertEqual(
			next(item for item in resources if item["name"] == "review")["mimeType"], "inode/directory"
		)

	def test_unknown_and_noncanonical_uris_are_invalid_params(self):
		uris = (
			None,
			1,
			"https://frappe/billing/refunds/SKILL.md",
			"skill://uninstalled/private/SKILL.md",
			"skill://frappe/billing/refunds/../private.txt",
			"skill://frappe/billing/refunds/%2e%2e/private.txt",
			"skill://frappe/billing/refunds%2fSKILL.md",
			"skill://frappe//billing/refunds/SKILL.md",
			"skill://frappe/billing/refunds/SKILL.md?x=1",
			"skill://frappe/billing/refunds/SKILL.md#section",
			"skill://frappe/billing/refunds/",
			"skill://frappe/billing/refunds/%00",
			"skill://frappe/billing/refunds/missing.md",
			"skill://frappe/private.txt",
			"skill://frappe/billing/refunds/.env",
			"skill://frappe/billing/refunds/.cache/hidden/SKILL.md",
		)
		for uri in uris:
			with self.subTest(uri=uri), self.assertRaises(protocol.McpError) as caught:
				self.catalog.read_resource(uri)
			self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)
		for operation, uri in (
			(self.catalog.get_skill, "skill://frappe/billing/refunds/.cache/hidden/SKILL.md"),
			(self.catalog.read_directory, "skill://frappe/billing/refunds/.cache"),
		):
			with self.subTest(uri=uri), self.assertRaises(protocol.McpError) as caught:
				operation(uri)
			self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)

	def test_symlinks_cannot_expose_files_or_directory_contents(self):
		skill = self.root / "frappe/skills/billing/refunds"
		(skill / "escape").symlink_to(self.root, target_is_directory=True)
		(skill / "linked.md").symlink_to(self.root / "frappe/skills/private.txt")
		for path in ("escape/frappe/skills/private.txt", "linked.md"):
			with self.subTest(path=path), self.assertRaises(protocol.McpError) as caught:
				self.catalog.read_resource("skill://frappe/billing/refunds/" + path)
			self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)
		with self.assertRaises(protocol.McpError):
			self.catalog.read_directory("skill://frappe/billing/refunds/escape/frappe")
		entry = self.catalog.get_skill("skill://frappe/billing/refunds/SKILL.md")["skill"]
		self.assertEqual(len(entry["resources"]), 4)

	def test_pagination_returns_complete_entries_and_rejects_foreign_cursors(self):
		operations = (
			(self.catalog.list_skills, "skills"),
			(self.catalog.list_resources, "resources"),
			(
				lambda cursor=None: self.catalog.read_directory("skill://frappe/billing/refunds", cursor),
				"resources",
			),
		)
		cursors = []
		for operation, field in operations:
			with self.subTest(operation=operation):
				expected = operation()[field]
				with patch("frappe.mcp.skills.PAGE_SIZE", 2):
					first = operation()
					second = operation(first["nextCursor"])
				cursors.append(first["nextCursor"])
				self.assertEqual(len(first[field]), 2)
				self.assertEqual(first[field] + second[field], expected)
				self.assertNotIn("nextCursor", second)
		for (operation, _), cursor in zip(operations, cursors[1:] + cursors[:1], strict=True):
			with self.subTest(cursor=cursor), self.assertRaises(protocol.McpError) as caught:
				operation(cursor)
			self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)
		for cursor in (1, "bad", "", cursors[2]):
			with self.subTest(cursor=cursor), self.assertRaises(protocol.McpError) as caught:
				self.catalog.read_directory("skill://frappe", cursor)
			self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)

	def test_invalid_skill_frontmatter_is_rejected(self):
		for frontmatter in (
			"name: other\ndescription: Example",
			"name: BAD\ndescription: Example",
			"name: bad--name\ndescription: Example",
			"name: invalid\ndescription: ''",
			"name: invalid\ndescription: 42",
			"name: invalid\ndescription: [bad]",
			"name: invalid\ndescription: Example\nmetadata: {version: 1}",
			"name: invalid\ndescription: Example\nfuture: {1: value}",
			"[invalid",
			"- invalid",
		):
			self.write_file("frappe", "invalid/SKILL.md", f"---\n{frontmatter}\n---\n".encode())
			with self.subTest(frontmatter=frontmatter), self.assertRaises(protocol.McpError) as caught:
				self.catalog.get_skill("skill://frappe/invalid/SKILL.md")
			self.assertEqual(caught.exception.code, protocol.INTERNAL_ERROR)

	def test_skill_size_and_file_count_limits(self):
		file = self.write_skill("frappe", "limits")
		for index in range(511):
			self.write_file("frappe", f"limits/{index}.txt", b"")
		uri = "skill://frappe/limits/SKILL.md"
		self.assertEqual(len(self.catalog.get_skill(uri)["skill"]["resources"]), 512)
		self.write_file("frappe", "limits/extra.txt", b"")
		with self.assertRaises(protocol.McpError) as caught:
			self.catalog.get_skill(uri)
		self.assertEqual(caught.exception.code, protocol.INTERNAL_ERROR)
		(self.root / "frappe/skills/limits/extra.txt").unlink()
		with (file.parent / "0.txt").open("wb") as content:
			content.truncate(16 * 1024 * 1024 - file.stat().st_size)
		self.assertEqual(
			sum(item["size"] for item in self.catalog.get_skill(uri)["skill"]["resources"]), 16 * 1024 * 1024
		)
		with (file.parent / "0.txt").open("ab") as content:
			content.write(b"x")
		with self.assertRaises(protocol.McpError) as caught:
			self.catalog.get_skill(uri)
		self.assertEqual(caught.exception.code, protocol.INTERNAL_ERROR)

	def test_apps_without_a_skills_directory_have_empty_catalogs(self):
		with patch("frappe.get_installed_apps", return_value=["empty"]):
			catalog = SkillCatalog()
		self.assertEqual(catalog.list_skills()["skills"], [])
		self.assertEqual(catalog.list_resources()["resources"], [])

	def test_filesystem_failures_propagate(self):
		uri = "skill://frappe/billing/refunds/SKILL.md"
		for operation in (self.catalog.list_skills, lambda: self.catalog.get_skill(uri)):
			failure = PermissionError(errno.EACCES, "Cannot scan skill directory")
			with (
				self.subTest(operation=operation),
				patch("os.scandir", side_effect=failure),
				self.assertRaises(PermissionError) as caught,
			):
				operation()
			self.assertIs(caught.exception, failure)
