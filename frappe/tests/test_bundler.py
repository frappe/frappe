# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner

import frappe
from frappe.bundler import (
	build_framework_islands,
	build_page_islands,
	framework_islands_built,
	remove_stale_island_toolchain,
)
from frappe.tests import UnitTestCase


class TestRemoveStaleIslandToolchain(UnitTestCase):
	def test_removes_toolchain_that_links_back_to_ui(self):
		with tempfile.TemporaryDirectory() as source:
			ui = os.path.join(source, "ui")
			os.makedirs(os.path.join(ui, "src"))
			marker = os.path.join(ui, "src", "index.ts")
			open(marker, "w").close()

			stale = os.path.join(ui, "vite", "island", "toolchain")
			scope = os.path.join(stale, "node_modules", "@framework")
			os.makedirs(scope)
			os.symlink("../../../../..", os.path.join(scope, "ui"))
			self.assertTrue(os.path.samefile(os.path.join(scope, "ui"), ui))

			with patch("frappe.get_app_source_path", return_value=source):
				remove_stale_island_toolchain()

			self.assertFalse(os.path.lexists(stale))
			self.assertTrue(os.path.exists(marker))

	def test_no_stale_toolchain(self):
		with tempfile.TemporaryDirectory() as source:
			with patch("frappe.get_app_source_path", return_value=source):
				remove_stale_island_toolchain()


@contextmanager
def failing_island_builds():
	"""A frappe source tree whose island build scripts fail."""
	with tempfile.TemporaryDirectory() as source:
		scripts = os.path.join(source, "ui", "vite", "island")
		os.makedirs(scripts)
		for script in ("build-framework.js", "build-pages.js"):
			with open(os.path.join(scripts, script), "w") as f:
				f.write("process.exit(1);\n")

		with patch("frappe.get_app_source_path", return_value=source):
			yield


class TestIslandBuilds(UnitTestCase):
	def test_unreadable_framework_manifest_is_not_built(self):
		with patch("frappe.read_file", return_value='{"frappe.chart":'):
			self.assertFalse(framework_islands_built())
		with patch("frappe.read_file", side_effect=OSError("Manifest unavailable")):
			self.assertFalse(framework_islands_built())

	def test_framework_islands_follow_build_app_selection(self):
		from frappe.commands.utils import build

		for app, assets_present, builds_framework in (
			("example_app", True, False),
			("frappe", True, True),
			("example_app", False, True),
		):
			with (
				self.subTest(app=app, assets_present=assets_present),
				tempfile.TemporaryDirectory() as sites,
				patch("frappe.init"),
				patch("frappe.local.conf", frappe._dict(developer_mode=0)),
				patch("frappe.local.sites_path", sites),
				patch("frappe.utils.synchronization.filelock", return_value=nullcontext()),
				patch("frappe.bundler.bundle"),
				patch("frappe.bundler.build_framework_islands") as framework_build,
				patch("frappe.gettext.translate.compile_translations"),
				patch("frappe.commands.utils.run_after_build_hook"),
			):
				assets = Path(sites) / "assets"
				assets.mkdir()
				manifest = {}
				for extension in ("js", "css"):
					manifest[f"frappe.chart.island.{extension}"] = f"/assets/chart.{extension}"
					if assets_present:
						(assets / f"chart.{extension}").touch()
				(assets / "assets.json").write_text(json.dumps(manifest))
				result = CliRunner().invoke(build, ["--app", app])
				self.assertEqual(result.exit_code, 0, result.output)
				self.assertEqual(framework_build.called, builds_framework)

	def test_failed_framework_island_build_fails_bench_build(self):
		with failing_island_builds():
			self.assertRaises(click.ClickException, build_framework_islands)

	def test_failed_page_island_build_does_not_fail_bench_build(self):
		with failing_island_builds():
			build_page_islands()
