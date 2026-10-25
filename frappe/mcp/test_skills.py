# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from frappe.mcp import protocol
from frappe.mcp.skills import PAGE_SIZE, SkillCatalog
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
		self.enterContext(patch("frappe.get_installed_apps", return_value=["frappe", "other"]))
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

	def test_manifests_match_the_exact_bytes_returned_by_resource_reads(self):
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

	def test_unknown_and_noncanonical_uris_are_invalid_params(self):
		uris = (
			None,
			1,
			"https://frappe/billing/refunds/SKILL.md",
			"skill://uninstalled/refunds/SKILL.md",
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
		)
		for uri in uris:
			with self.subTest(uri=uri), self.assertRaises(protocol.McpError) as caught:
				self.catalog.read_resource(uri)
			self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)

	def test_symlinks_cannot_expose_files_or_directory_contents(self):
		skill = self.root / "frappe/skills/billing/refunds"
		(skill / "escape").symlink_to(self.root, target_is_directory=True)
		(skill / "linked.md").symlink_to(self.root / "frappe/skills/private.txt")
		for path in ("escape/frappe/skills/private.txt", "linked.md"):
			with self.subTest(path=path), self.assertRaises(protocol.McpError) as caught:
				self.catalog.read_resource("skill://frappe/billing/refunds/" + path)
			self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)
		entry = self.catalog.get_skill("skill://frappe/billing/refunds/SKILL.md")["skill"]
		self.assertEqual(len(entry["resources"]), 4)

	def test_updates_change_parent_and_nested_manifests(self):
		parent_uri = "skill://frappe/billing/refunds/SKILL.md"
		child_uri = "skill://frappe/billing/refunds/review/SKILL.md"
		before = self.catalog.get_skill(parent_uri)["skill"]
		self.write_file("frappe", "billing/refunds/review/check.md", b"New rules")
		after = self.catalog.get_skill(parent_uri)["skill"]
		child = self.catalog.get_skill(child_uri)["skill"]
		self.assertNotEqual(before["resources"], after["resources"])
		self.assertTrue(all(resource in after["resources"] for resource in child["resources"]))

	def test_pagination_keeps_skill_manifests_atomic(self):
		for index in range(PAGE_SIZE):
			self.write_skill("frappe", f"skill-{index}")
		first = self.catalog.list_skills()
		second = self.catalog.list_skills(first["nextCursor"])
		self.assertEqual(len(first["skills"]), PAGE_SIZE)
		self.assertEqual(len(second["skills"]), 3)
		self.assertNotIn("nextCursor", second)
		self.assertEqual(len({entry["uri"] for entry in first["skills"] + second["skills"]}), PAGE_SIZE + 3)
		for cursor in (1, "bad", "", first["nextCursor"]):
			with self.subTest(cursor=cursor), self.assertRaises(protocol.McpError) as caught:
				self.catalog.list_resources(cursor)
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

	def test_no_skills_are_exposed_from_uninstalled_apps(self):
		with patch("frappe.get_installed_apps", return_value=["other"]):
			catalog = SkillCatalog()
		self.assertEqual(len(catalog.list_skills()["skills"]), 1)
		with self.assertRaises(protocol.McpError) as caught:
			catalog.read_resource("skill://frappe/billing/refunds/SKILL.md")
		self.assertEqual(caught.exception.code, protocol.INVALID_PARAMS)

	def test_apps_without_a_skills_directory_have_empty_catalogs(self):
		with patch("frappe.get_installed_apps", return_value=["empty"]):
			catalog = SkillCatalog()
		self.assertEqual(catalog.list_skills()["skills"], [])
		self.assertEqual(catalog.list_resources()["resources"], [])
