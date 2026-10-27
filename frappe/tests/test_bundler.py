# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import subprocess
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

import click
from click.testing import CliRunner

from frappe.bundler import build_framework_islands, build_page_islands, remove_stale_island_toolchain
from frappe.commands.utils import build
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
	def test_failed_framework_island_build_fails_bench_build(self):
		with failing_island_builds():
			self.assertRaises(click.ClickException, build_framework_islands)

	def test_failed_page_island_build_does_not_fail_bench_build(self):
		with failing_island_builds():
			build_page_islands()


class TestBuildOrder(UnitTestCase):
	def test_failed_shell_build_fails_after_v1_is_built(self):
		with tempfile.TemporaryDirectory() as source:
			frontend = os.path.join(source, "frontend")
			os.makedirs(os.path.join(frontend, "node_modules"))
			open(os.path.join(frontend, "package.base.json"), "w").close()
			with open(os.path.join(frontend, "package.json"), "w") as f:
				f.write('{"scripts": {"build": "node vite.js"}}')
			with open(os.path.join(frontend, "vite.js"), "w") as f:
				f.write("process.exit(1);\n")

			v1_asset = os.path.join(source, "v1-bundle.js")
			steps = []

			def bundle(*args, **kwargs):
				steps.append("esbuild")
				open(v1_asset, "w").close()

			with (
				patch("frappe.get_app_source_path", return_value=source),
				patch("frappe.init"),
				patch("frappe.bundler.bundle", bundle),
				patch("frappe.bundler.build_framework_islands", lambda **kw: steps.append("islands")),
				patch(
					"frappe.gettext.translate.compile_translations",
					lambda *a, **kw: steps.append("translations"),
				),
				patch("frappe.commands.utils.run_after_build_hook", lambda apps: steps.append("after_build")),
				patch("frappe.shell.manifest.write", return_value=({}, [], False)),
				patch("frappe.bundler.refresh_lockfile", return_value=False),
				patch("frappe.shell.manifest.cost_report", return_value=[]),
				patch("frappe.bundler.swap_shell_assets") as swap,
			):
				result = CliRunner().invoke(build, ["--app", "frappe"])

			self.assertNotEqual(result.exit_code, 0)
			self.assertIsInstance(result.exception, subprocess.CalledProcessError)
			self.assertTrue(result.exception.cmd.startswith("yarn build"))
			self.assertEqual(steps, ["esbuild", "islands", "translations", "after_build"])
			self.assertTrue(os.path.exists(v1_asset))
			swap.assert_not_called()
