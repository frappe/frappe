# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager, nullcontext
from unittest.mock import patch

import click
from click.testing import CliRunner

from frappe.bundler import (
	build_framework_islands,
	build_page_islands,
	build_shell,
	remove_stale_island_toolchain,
)
from frappe.commands.utils import build
from frappe.shell.manifest import frontend_dir, package_name, shaping_apps
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
				patch("frappe.get_app_path", return_value=os.path.join(source, "frappe")),
				patch("frappe.utils.synchronization.filelock", lambda *a, **kw: nullcontext()),
				patch("frappe.shell.manifest.write", lambda *a: steps.append("shell") or ([], [], False)),
				patch("frappe.bundler.refresh_lockfile", return_value=False),
				patch("frappe.shell.manifest.cost_report", return_value=[]),
				patch("frappe.bundler.swap_shell_assets") as swap,
			):
				result = CliRunner().invoke(build, ["--app", "frappe"])

			self.assertNotEqual(result.exit_code, 0)
			self.assertIsInstance(result.exception, subprocess.CalledProcessError)
			self.assertTrue(result.exception.cmd.startswith("yarn build"))
			self.assertEqual(steps, ["esbuild", "islands", "translations", "after_build", "shell"])
			self.assertTrue(os.path.exists(v1_asset))
			swap.assert_not_called()


def shell_build_commands(production: bool, installed_flags: list[str] | None = None) -> list[str]:
	"""The commands `build_shell` runs, with yarn stubbed; `installed_flags` stands for an installed tree."""
	with tempfile.TemporaryDirectory() as source:
		frontend = os.path.join(source, "frontend")
		os.makedirs(frontend)
		open(os.path.join(frontend, "package.base.json"), "w").close()
		if installed_flags is not None:
			os.makedirs(os.path.join(frontend, "node_modules"))
			with open(os.path.join(frontend, "node_modules", ".yarn-integrity"), "w") as f:
				json.dump({"flags": installed_flags}, f)
		with (
			patch("frappe.get_app_path", return_value=os.path.join(source, "frappe")),
			stubbed_yarn(os.path.join(source, "frappe")) as commands,
		):
			build_shell(source, production=production)
		return commands


@contextmanager
def stubbed_yarn(frappe_path: str, stub_manifest: bool = True, fail_build: bool = False):
	"""Record the commands a shell build runs; `yarn build` leaves a built tree as vite would."""
	staging = os.path.join(frappe_path, "public", "frontend.staging")
	commands = []

	def popen(command, **kwargs):
		commands.append(command)
		if command.startswith("yarn build"):
			if fail_build:
				raise subprocess.CalledProcessError(1, command)
			os.makedirs(staging)
			open(os.path.join(staging, "index.html"), "w").close()

	with (
		patch("frappe.shell.manifest.write", return_value=([], [], False))
		if stub_manifest
		else nullcontext(),
		patch("frappe.bundler.refresh_lockfile", return_value=False),
		patch("frappe.shell.manifest.cost_report", return_value=[]),
		patch("frappe.commands.popen", popen),
		patch("frappe.bundler.swap_shell_assets"),
	):
		yield commands


class TestShellBuildWeight(UnitTestCase):
	def test_production_build_skips_test_tools_and_source_maps(self):
		install, build = shell_build_commands(production=True)
		self.assertEqual(install, "yarn install --production")
		self.assertTrue(build.endswith(" --mode production --sourcemap false"))

	def test_development_build_keeps_test_tools_and_source_maps(self):
		install, build = shell_build_commands(production=False)
		self.assertEqual(install, "yarn install --production=false")
		self.assertNotIn("--sourcemap", build)

	def test_development_build_reinstalls_a_tree_installed_without_test_tools(self):
		install, _build = shell_build_commands(production=False, installed_flags=["production"])
		self.assertEqual(install, "yarn install --production=false")

	def test_unchanged_tree_is_not_reinstalled(self):
		self.assertEqual(len(shell_build_commands(production=False, installed_flags=[])), 1)
		self.assertEqual(len(shell_build_commands(production=True, installed_flags=["production"])), 1)

	def test_build_files_import_no_dev_dependency(self):
		frontend = frontend_dir()
		with open(os.path.join(frontend, "package.base.json")) as f:
			dev_dependencies = set(json.load(f)["devDependencies"])

		for path in build_files(frontend):
			with self.subTest(path=os.path.relpath(path, frontend)):
				imported = {package_name(specifier) for specifier in bare_imports(path)}
				self.assertFalse(imported & dev_dependencies)


class TestShellBuildForListedApps(UnitTestCase):
	PLAIN = ("plain_module/doctype/thing/thing.json",)
	CRM = ("crm_module/doctype/deal/frontend/record.js",)

	def test_app_run_adding_nothing_skips_the_shell(self):
		commands, recorded = listed_run(["plain"], last_shaping=["frappe", "crm"])
		self.assertEqual(commands, [])
		self.assertEqual(recorded, ["frappe", "crm"])

	def test_app_run_adding_to_the_shell_builds_and_records_it(self):
		commands, recorded = listed_run(["plain", "crm"], last_shaping=["frappe"])
		self.assertTrue(commands[-1].startswith("yarn build"))
		self.assertEqual(recorded, ["frappe", "crm"])

	def test_app_run_whose_app_shaped_the_last_build_builds_it(self):
		commands, recorded = listed_run(["plain"], last_shaping=["frappe", "plain"])
		self.assertTrue(commands)
		self.assertEqual(recorded, ["frappe", "crm"])

	def test_failed_build_keeps_the_record_of_the_published_shell(self):
		commands, recorded = listed_run(["crm"], last_shaping=["frappe", "plain"], fail_build=True)
		self.assertTrue(commands[-1].startswith("yarn build"))
		self.assertEqual(recorded, ["frappe", "plain"])

	def test_app_run_with_no_record_of_the_last_build_builds_it(self):
		self.assertTrue(listed_run(["plain"], last_shaping=None)[0])

	def test_app_run_builds_a_shell_never_published(self):
		self.assertTrue(listed_run(["plain"], last_shaping=["frappe"], published=False)[0])

	def test_full_build_builds_the_shell(self):
		self.assertTrue(shell_build_commands(production=True)[-1].startswith("yarn build"))

	def test_build_command_passes_only_the_listed_apps(self):
		self.assertEqual(listed_apps_given_to_shell(["--apps", "crm,plain"]), ["crm", "plain"])
		self.assertIsNone(listed_apps_given_to_shell([]))


def listed_run(
	listed: list[str], last_shaping: list[str] | None, published: bool = True, fail_build: bool = False
) -> tuple[list[str], list[str] | None]:
	"""A `--apps` shell build on a bench of frappe, `plain` and a contributing `crm`: its commands and record."""
	apps = {
		"frappe": ["public/frontend/index.html"] if published else [],
		"plain": TestShellBuildForListedApps.PLAIN,
		"crm": TestShellBuildForListedApps.CRM,
	}
	with tempfile.TemporaryDirectory() as source, bench_of(apps) as bench:
		frontend = os.path.join(source, "frontend")
		os.makedirs(frontend)
		with open(os.path.join(frontend, "package.base.json"), "w") as f:
			f.write("{}")
		open(os.path.join(frontend, "yarn.lock.base"), "w").close()
		record = os.path.join(frontend, "published.json")
		if last_shaping is not None:
			with open(record, "w") as f:
				json.dump({"shaping_apps": last_shaping}, f)

		try:
			with stubbed_yarn(
				os.path.join(bench, "frappe"), stub_manifest=False, fail_build=fail_build
			) as commands:
				build_shell(source, production=True, listed_apps=listed)
		except subprocess.CalledProcessError:
			if not fail_build:
				raise
		if not os.path.exists(record):
			return commands, None
		with open(record) as f:
			return commands, json.load(f)["shaping_apps"]


def listed_apps_given_to_shell(cli_args: list[str]) -> list[str] | None:
	with (
		patch("frappe.init"),
		patch("frappe.get_all_apps", return_value=["frappe", "crm", "plain"]),
		patch("frappe.get_app_source_path", return_value="/nowhere"),
		patch("frappe.utils.synchronization.filelock", lambda *a, **kw: nullcontext()),
		patch("frappe.bundler.bundle"),
		patch("frappe.bundler.build_framework_islands"),
		patch("frappe.gettext.translate.compile_translations"),
		patch("frappe.commands.utils.run_after_build_hook"),
		patch("frappe.bundler.build_shell") as build_shell,
	):
		result = CliRunner().invoke(build, cli_args)
	if result.exception:
		raise result.exception
	return build_shell.call_args.kwargs["listed_apps"]


@contextmanager
def bench_of(apps: dict[str, tuple[str, ...] | list[str]]):
	"""A bench whose apps hold the given files, each path relative to the app's source dir; yields its root."""
	with tempfile.TemporaryDirectory() as bench:
		for app, files in apps.items():
			for path in files:
				path = os.path.join(bench, app, path)
				os.makedirs(os.path.dirname(path), exist_ok=True)
				open(path, "w").close()

		with (
			patch("frappe.get_all_apps", return_value=list(apps)),
			patch("frappe.get_app_path", side_effect=lambda app, *rest: os.path.join(bench, app, *rest)),
			patch("frappe.shell.manifest.app_import_map", return_value={}),
			patch("frappe.shell.manifest.declared_prefix", return_value=None),
			patch("frappe.shell.manifest.is_modular", return_value=False),
			patch("frappe.shell.manifest.read_declaration", return_value={}),
		):
			yield bench


class TestShapingApps(UnitTestCase):
	PLAIN = TestShellBuildForListedApps.PLAIN

	def test_app_with_no_contribution_does_not_shape_the_shell(self):
		with bench_of({"frappe": [], "plain": self.PLAIN}):
			self.assertEqual(shaping_apps(["plain"]), [])

	def test_frappe_always_shapes_the_shell(self):
		with bench_of({"frappe": [], "plain": self.PLAIN}):
			self.assertEqual(shaping_apps(["frappe", "plain"]), ["frappe"])

	def test_contributing_app_shapes_the_shell(self):
		with bench_of({"frappe": [], "plain": self.PLAIN, "crm": TestShellBuildForListedApps.CRM}):
			self.assertEqual(shaping_apps(["plain", "crm"]), ["crm"])

	def test_app_shipping_a_preset_shapes_the_shell(self):
		with bench_of({"frappe": [], "themed": ["frontend/tailwind.preset.js"]}):
			self.assertEqual(shaping_apps(["themed"]), ["themed"])

	def test_app_owning_a_doctype_another_app_customises_shapes_the_shell(self):
		with bench_of({"frappe": [], "plain": self.PLAIN, "other": ["other_module/custom/thing/record.js"]}):
			self.assertEqual(shaping_apps(["plain"]), ["plain"])


IMPORT = re.compile(r"""(?:from|import)\s*\(?\s*["']([^"']+)["']""")
# postcss loads each plugin by its key's package name.
POSTCSS_PLUGIN = re.compile(r"^\s*([\w@/-]+): \{[^{}]*\}", re.MULTILINE)


def build_files(frontend: str) -> set[str]:
	"""The build configs and every local module they load, followed through relative imports."""
	pending = [
		os.path.join(frontend, name) for name in ("vite.config.js", "postcss.config.js", "tailwind.config.js")
	]
	seen = set()
	while pending:
		path = pending.pop()
		if path in seen:
			continue
		seen.add(path)
		with open(path) as f:
			for specifier in IMPORT.findall(f.read()):
				if specifier.startswith("."):
					target = os.path.normpath(os.path.join(os.path.dirname(path), specifier))
					if target.endswith((".js", ".mjs")):
						pending.append(target)
	return seen


def bare_imports(path: str) -> list[str]:
	with open(path) as f:
		source = f.read()
	imported = [s for s in IMPORT.findall(source) if not s.startswith((".", "/", "node:"))]
	if os.path.basename(path) == "postcss.config.js":
		imported += POSTCSS_PLUGIN.findall(source)
	return imported
