# The desk v2 shell: routing, the prefix contract, and the two guards.

import errno
import json
import os
import re
import shutil
import tempfile
from contextlib import ExitStack, contextmanager
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.bundler import swap_shell_assets
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.shell import SHELL_ROOT
from frappe.shell.address_clash import page_files
from frappe.shell.doctypes import build_address_table, clear_doctype_owners
from frappe.shell.install import PrefixCollisionError, before_app_install
from frappe.shell.manifest import (
	FRAMEWORK_NAMES,
	DeclarationError,
	ImportMapConflict,
	SingletonConflict,
	app_deps,
	app_runtime_deps,
	assemble,
	compose_package_json,
	cost_report,
	enforce_import_map,
	enforce_singletons,
	import_map_problems,
	shipped_versions,
)
from frappe.shell.registry import (
	clear_prefix_registry,
	declared_prefix,
	default_prefix,
	shell_base,
	split_shell_path,
)
from frappe.shell.route_guard import ReservedRouteError, is_reserved
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.page_renderers.not_found_page import NotFoundPage
from frappe.website.page_renderers.shell_page import ShellPage
from frappe.website.path_resolver import PathResolver
from frappe.website.serve import get_response


def hooks_declaring(hook_name: str, values: dict[str, str]):
	"""Patch `get_hooks` for one hook on named apps, delegating everything else."""
	# Delegating, because `log_error` reads hooks of its own.
	real = frappe.get_hooks

	def fake(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if hook == hook_name and app_name in values:
			return [values[app_name]]
		return real(hook, default, app_name)

	return patch.object(frappe, "get_hooks", side_effect=fake)


def hooks_returning(app_prefixes: dict[str, str]):
	return hooks_declaring("app_prefix", app_prefixes)


#: A second app, invented here and not borrowed from the bench.
SECOND_APP = "shell_probe"
SECOND_PREFIX = "shell-probe"


@contextmanager
def a_second_app(app: str = SECOND_APP, prefix: str | None = SECOND_PREFIX, active: bool = True):
	"""Present a second app to the shell, faking every seam it is read through; `active=False` means disabled."""
	# The app exists nowhere on disk: never route a path it does not claim while it is active, or
	# `StaticPage` raises `ModuleNotFoundError` on it.
	real_hooks = frappe.get_hooks
	real_active = frappe.get_active_apps
	real_installed = frappe.get_installed_apps

	def fake_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if app_name == app:
			# A declared prefix if one was asked for; otherwise `default_prefix` runs.
			if hook == "app_prefix" and prefix:
				return [prefix]
			return []
		return real_hooks(hook, default, app_name)

	def with_app(real):
		def fake(*args, **kwargs):
			apps = list(real(*args, **kwargs))
			return apps if app in apps else [*apps, app]

		return fake

	def clear():
		clear_prefix_registry()
		clear_doctype_owners()

	clear()
	with ExitStack() as stack:
		stack.callback(clear)
		stack.enter_context(patch.object(frappe, "get_hooks", side_effect=fake_hooks))
		if active:
			stack.enter_context(patch.object(frappe, "get_active_apps", side_effect=with_app(real_active)))
		stack.enter_context(patch.object(frappe, "get_installed_apps", side_effect=with_app(real_installed)))
		yield app, prefix


def strip_html_comments(html: bytes) -> bytes:
	"""Comments are commentary, not content: the document's own comment names the absent payloads."""
	return re.sub(rb"<!--.*?-->", b"", html, flags=re.DOTALL)


def strip_comments(source: str) -> str:
	"""Blank out comments, keeping line numbers, so a guard reads code only."""

	def blank(match: re.Match) -> str:
		return "\n" * match.group().count("\n")

	source = re.sub(r"<!--.*?-->", blank, source, flags=re.DOTALL)
	source = re.sub(r"/\*.*?\*/", blank, source, flags=re.DOTALL)
	return re.sub(r"^\s*(//|\*).*$", "", source, flags=re.MULTILINE)


class TestShellPrefixes(IntegrationTestCase):
	def test_default_derivation_when_an_app_declares_nothing(self):
		self.assertEqual(default_prefix("crm"), "crm")
		self.assertEqual(default_prefix("frappe_whatsapp"), "whatsapp")
		# Underscores are preserved.
		self.assertEqual(default_prefix("hr_management"), "hr_management")
		# An app named exactly `frappe_` must not claim the empty prefix.
		self.assertEqual(default_prefix("frappe_"), "frappe_")

	def test_an_app_that_declares_nothing_gets_its_own_name(self):
		# `prefix=None`: the derivation runs for real, not a hook answering.
		with a_second_app(prefix=None) as (app, _):
			self.assertEqual(declared_prefix(app), app)

	def test_the_framework_declares_its_own_prefix(self):
		"""No privileged path: the desk uses the door it is building."""
		self.assertEqual(declared_prefix("frappe"), "desk")
		self.assertEqual(shell_base("desk"), "/apps/desk")

	def test_split_shell_path(self):
		self.assertEqual(split_shell_path("apps/crm"), ("crm", ""))
		self.assertEqual(split_shell_path("apps/crm/crm-deal/CRM-001"), ("crm", "crm-deal/CRM-001"))
		# The index belongs to no app, so it is not a prefix.
		self.assertIsNone(split_shell_path("apps"))
		# v1's address space is untouched.
		self.assertIsNone(split_shell_path("crm"))
		self.assertIsNone(split_shell_path("desk"))


class TestShellRouting(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		self._clear_request()

	def _clear_request(self):
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def renderer_for(self, path):
		return PathResolver(path).resolve()[1]

	def test_a_bare_prefix_resolves(self):
		"""A `<path:>` rule would not match a bare `/apps/<prefix>`, so the bare case needs its own test."""
		self.assertIsInstance(self.renderer_for("apps/desk"), ShellPage)
		with a_second_app() as (_, prefix):
			self.assertIsInstance(self.renderer_for(f"apps/{prefix}"), ShellPage)

	def test_a_doctype_route_resolves_under_a_prefix(self):
		with a_second_app() as (_, prefix):
			self.assertIsInstance(self.renderer_for(f"apps/{prefix}/some-doctype/SOME-001"), ShellPage)

	def test_the_index_resolves(self):
		self.assertIsInstance(self.renderer_for(SHELL_ROOT), ShellPage)

	def test_an_unclaimed_prefix_is_a_website_404(self):
		"""The shell owns error states only inside a prefix it serves."""
		self.assertIsInstance(self.renderer_for("apps/no-such-app"), NotFoundPage)

	def test_desk_v1_is_untouched(self):
		"""`/desk` is v1's and stays v1's, even though the framework claims `/apps/desk`."""
		self.assertNotIsInstance(self.renderer_for("desk"), ShellPage)

	def test_a_route_miss_inside_a_prefix_serves_the_shell_at_200(self):
		"""A client-side route miss, not a server 404: a 404 would cost the page its asset preloads."""
		with a_second_app() as (_, prefix):
			set_request(method="GET", path=f"/apps/{prefix}/nothing-is-here")
			response = get_response()
		self.assertEqual(response.status_code, 200)

	def test_the_shell_serves_the_built_document(self):
		set_request(method="GET", path="/apps/desk")
		response = get_response()
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'<div id="app">', response.data)

		# The document carries no per-request content: no boot island, no CSRF token, no route.
		markup = strip_html_comments(response.data)
		self.assertNotIn(b"window.boot", markup)
		self.assertNotIn(b"__FRONTEND_ROUTE__", markup)
		self.assertNotIn(b"__SOCKETIO_PORT__", markup)
		self.assertNotIn(b"csrf_token", markup)

	def test_the_document_is_byte_identical_for_two_different_users(self):
		"""If this fails the shell has become user-varying, and caching it would be a cross-user leak."""
		other = frappe.get_doc(
			doctype="User",
			email="shell-second-user@example.com",
			first_name="Shell",
			user_type="System User",
		).insert(ignore_if_duplicate=True)
		other.add_roles("System Manager")
		self.addCleanup(frappe.set_user, "Administrator")

		set_request(method="GET", path="/apps/desk")
		as_admin = get_response().data

		frappe.set_user(other.name)
		set_request(method="GET", path="/apps/desk")
		as_other = get_response().data

		self.assertEqual(as_admin, as_other)


class TestShellIsNeverCached(IntegrationTestCase):
	"""`can_cache()` ignores the session user, so a cached shell would hand one user's document to the next."""

	# `can_cache()` is False under `developer_mode`, so the test forces the flag.

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.flags.force_website_cache = True

	#: The framework's own prefix, claimed on every bench there is.
	CACHE_KEY = "website_page::apps/desk"

	def tearDown(self):
		frappe.flags.force_website_cache = False
		frappe.cache.delete_value(self.CACHE_KEY)
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def test_the_shell_writes_no_page_cache_even_when_caching_is_forced(self):
		from frappe.website.utils import can_cache

		# The flag really is on, or the test passes because caching was off anyway.
		self.assertTrue(can_cache())

		frappe.cache.delete_value(self.CACHE_KEY)
		set_request(method="GET", path="/apps/desk")
		response = get_response()

		self.assertEqual(response.status_code, 200)
		self.assertIsNone(frappe.cache.get_value(self.CACHE_KEY))

	def test_rendering_the_shell_turns_local_caching_off(self):
		set_request(method="GET", path="/apps/desk")
		get_response()
		self.assertTrue(getattr(frappe.local, "no_cache", False))


class TestPrefixCollisionGuard(IntegrationTestCase):
	"""Collisions fail hard at install, naming every claimant."""

	def test_a_colliding_prefix_is_refused_naming_both_claimants(self):
		"""Collide with the framework's own `desk`, which every bench has."""
		with hooks_returning({"newapp": "desk"}):
			with self.assertRaises(PrefixCollisionError) as caught:
				before_app_install("newapp")

		message = str(caught.exception)
		self.assertIn("newapp", message)
		self.assertIn("desk", message)
		self.assertIn("frappe", message)

	def test_a_malformed_prefix_is_refused(self):
		for bad in ["Apps", "with space", "9lives", "trailing/slash", ""]:
			with self.subTest(prefix=bad), hooks_returning({"newapp": bad}):
				with self.assertRaises(PrefixCollisionError):
					before_app_install("newapp")

	def test_a_free_prefix_installs(self):
		with hooks_returning({"newapp": "totally-free-prefix"}):
			before_app_install("newapp")  # must not raise

	def test_a_disabled_app_still_holds_its_prefix(self):
		"""A disabled app is not serving, but it has not given the prefix up."""
		with a_second_app(prefix="shop", active=False) as (disabled, prefix):
			self.assertNotIn(disabled, frappe.get_active_apps(_ensure_on_bench=True))
			self.assertIn(disabled, frappe.get_installed_apps(_ensure_on_bench=True))

			with hooks_returning({"newapp": prefix}):
				with self.assertRaises(PrefixCollisionError) as caught:
					before_app_install("newapp")

		# Both claimants named, the disabled one included.
		message = str(caught.exception)
		self.assertIn("newapp", message)
		self.assertIn(prefix, message)
		self.assertIn(disabled, message)

	def test_a_v1_route_does_not_collide_with_the_same_name_under_apps(self):
		"""v1 holds `/crm`, v2 holds `/apps/crm`, and they no longer compete."""
		with a_second_app() as (app, prefix):
			self.assertEqual(shell_base(declared_prefix(app)), f"/apps/{prefix}")
			# The bare name stays v1's, whoever holds it.
			self.assertIsNone(split_shell_path(prefix))


class TestReservedRouteGuard(IntegrationTestCase):
	"""The runtime half of the claim surface: a Web Page titled "Apps"."""

	def test_apps_is_reserved(self):
		self.assertTrue(is_reserved("apps"))
		self.assertTrue(is_reserved("/apps"))
		self.assertTrue(is_reserved("apps/crm"))
		self.assertFalse(is_reserved("applications"))
		self.assertFalse(is_reserved("my/apps"))
		self.assertFalse(is_reserved(""))

	def test_a_web_page_cannot_claim_a_route_inside_apps(self):
		page = frappe.get_doc(doctype="Web Page", title="Apps", route="apps", published=1)
		with self.assertRaises(ReservedRouteError):
			page.insert()

	def test_a_web_page_elsewhere_is_unaffected(self):
		page = frappe.get_doc(
			doctype="Web Page", title="Shell Guard Test", route="shell-guard-test", published=1
		)
		page.insert()
		self.addCleanup(lambda: frappe.delete_doc("Web Page", page.name, force=True))
		self.assertEqual(page.route, "shell-guard-test")


class TestSingletonEnforcement(IntegrationTestCase):
	"""One module graph admits one version of each shared library: the one the framework ships."""

	PINNED: ClassVar[dict[str, str]] = {
		"vue": "^3.5.13",
		"vue-router": "^4.5.0",
		"frappe-ui": "1.0.0-beta.63",
		"@framework/ui": "link:../ui",
	}
	LOCKFILE = (
		'frappe-ui@1.0.0-beta.63:\n  version "1.0.0-beta.63"\n  resolved "https://x/frappe-ui.tgz"\n\n'
		'"@framework/ui@link:../ui":\n  version "0.0.0"\n  uid ""\n\n'
		'vue@^3.5.13, vue@^3.5.20:\n  version "3.5.41"\n  resolved "https://x/vue.tgz"\n\n'
		'vue-router@^4.0.0:\n  version "4.0.0"\n  resolved "https://x/vue-router-4.0.0.tgz"\n\n'
		'vue-router@^4.5.0:\n  version "4.6.4"\n  resolved "https://x/vue-router.tgz"\n'
	)

	def setUp(self):
		self.frontend = tempfile.mkdtemp(prefix="frontend")
		self.addCleanup(shutil.rmtree, self.frontend)
		with open(os.path.join(self.frontend, "package.base.json"), "w") as f:
			json.dump({"dependencies": self.PINNED}, f)
		with open(os.path.join(self.frontend, "yarn.lock.base"), "w") as f:
			f.write(self.LOCKFILE)

	def enforce(self, app: str, deps: dict):
		enforce_singletons([{"app": "frappe", "deps": {}}, {"app": app, "deps": deps}], self.frontend)

	def refusal(self, app: str, deps: dict) -> str:
		with self.assertRaises(SingletonConflict) as caught:
			self.enforce(app, deps)
		return str(caught.exception)

	def test_the_shipped_version_is_the_lockfile_resolution_for_the_base_range(self):
		"""Not the range floor, and not the first block that names the package."""
		self.assertEqual(
			shipped_versions(self.frontend),
			{"frappe-ui": "1.0.0-beta.63", "vue": "3.5.41", "vue-router": "4.6.4"},
		)

	def test_a_missing_base_lockfile_is_named(self):
		os.remove(os.path.join(self.frontend, "yarn.lock.base"))
		with self.assertRaises(SingletonConflict) as caught:
			self.enforce("crm", {"vue": "*"})
		self.assertIn("yarn.lock.base is missing", str(caught.exception))

	def test_a_range_that_includes_the_shipped_version_passes(self):
		self.enforce("crm", {"vue": "^3.5.13", "vue-router": ">=4.5", "frappe-ui": "1.0.0-beta.63"})

	def test_a_range_that_excludes_it_is_refused_naming_both_sides(self):
		message = self.refusal("gameplan", {"vue": "^3.5.13", "frappe-ui": ">=1.0.0-beta.70"})
		self.assertIn("frappe-ui: the framework ships 1.0.0-beta.63; gameplan needs >=1.0.0-beta.70", message)
		self.assertIn("Keep frappe-ui current", message)
		# `vue` is satisfied, so it must not be reported.
		self.assertNotIn("  vue:", message)

	def test_a_prerelease_floor_admits_a_later_prerelease(self):
		self.enforce("crm", {"frappe-ui": ">=1.0.0-beta.60"})
		self.enforce("crm", {"frappe-ui": "^1.0.0-beta.60"})

	def test_a_release_floor_excludes_a_prerelease_as_npm_does(self):
		self.assertIn(
			"frappe-ui: the framework ships 1.0.0-beta.63", self.refusal("crm", {"frappe-ui": ">=1.0.0"})
		)

	def test_framework_ui_is_declared_as_any_version(self):
		self.enforce("crm", {"@framework/ui": "*"})
		message = self.refusal("crm", {"@framework/ui": "^1.0.0"})
		self.assertIn(
			"@framework/ui: ships with the framework and has no version to pin; crm needs ^1.0.0", message
		)

	def test_a_range_that_does_not_parse_is_refused_as_not_a_range(self):
		message = self.refusal("crm", {"frappe-ui": "latest"})
		self.assertIn(
			"frappe-ui: `latest` is not a semver range; crm needs a range that includes 1.0.0-beta.63",
			message,
		)

	def test_a_singleton_missing_from_the_lockfile_is_refused(self):
		self.assertIn(
			"reka-ui: the base lockfile has no entry; crm needs *", self.refusal("crm", {"reka-ui": "*"})
		)

	def test_a_non_singleton_may_differ_freely(self):
		"""The list is closed. An app pins its own libraries without asking."""
		enforce_singletons(
			[
				{"app": "crm", "deps": {"date-fns": "^4.1.0"}},
				{"app": "gameplan", "deps": {"date-fns": "^2.0.0"}},
			],
			self.frontend,
		)

	def test_the_ranges_come_from_the_declaration_file(self):
		repo = tempfile.mkdtemp(prefix="gameplan")
		self.addCleanup(shutil.rmtree, repo)
		source_dir = os.path.join(repo, "gameplan")
		pages = os.path.join(source_dir, "gameplan", "frontend", "pages")
		os.makedirs(pages)
		with open(os.path.join(source_dir, "desk.package.json"), "w") as f:
			json.dump({"dependencies": {"frappe-ui": ">=1.0.0-beta.70"}}, f)
		with open(os.path.join(pages, "home.js"), "w") as f:
			f.write("export default {}")

		with (
			patch.object(frappe, "get_all_apps", return_value=["frappe", "gameplan"]),
			patch.object(frappe, "get_app_path", side_effect=lambda app: source_dir),
			patch.object(frappe, "get_hooks", return_value={}),
			patch("frappe.shell.manifest.declared_prefix", return_value="gameplan"),
		):
			with self.assertRaises(SingletonConflict) as caught:
				enforce_singletons(assemble(), self.frontend)
		self.assertIn("gameplan needs >=1.0.0-beta.70", str(caught.exception))


class TestAppDeclaration(IntegrationTestCase):
	"""An app declares its desk v2 packages in `<app>/<app>/desk.package.json`, `dependencies` only."""

	def setUp(self):
		self.repo = tempfile.mkdtemp(prefix="crm")
		self.source_dir = os.path.join(self.repo, "crm")
		os.makedirs(self.source_dir)
		self.addCleanup(shutil.rmtree, self.repo)

	def declare(self, content: dict):
		with open(os.path.join(self.source_dir, "desk.package.json"), "w") as f:
			json.dump(content, f)

	def test_dependencies_are_read_from_the_declaration_file(self):
		self.declare({"dependencies": {"vue": "^3.5.13", "@frappe/crm-ui": "^1.2.0"}})
		with patch.object(frappe, "get_app_path", return_value=self.source_dir):
			self.assertEqual(app_runtime_deps("crm"), {"vue": "^3.5.13", "@frappe/crm-ui": "^1.2.0"})
			self.assertEqual(app_deps("crm"), {"vue": "^3.5.13", "@frappe/crm-ui": "^1.2.0"})

	def test_the_repo_root_package_json_is_not_read(self):
		with open(os.path.join(self.repo, "package.json"), "w") as f:
			json.dump({"dependencies": {"onscan.js": "^1.5.2"}}, f)
		with patch.object(frappe, "get_app_path", return_value=self.source_dir):
			self.assertEqual(app_runtime_deps("crm"), {})

	def test_no_file_means_no_packages(self):
		with patch.object(frappe, "get_app_path", return_value=self.source_dir):
			self.assertEqual(app_deps("crm"), {})
			self.assertEqual(app_runtime_deps("crm"), {})

	def test_any_other_key_is_refused_naming_the_app_and_the_key(self):
		self.declare({"dependencies": {}, "devDependencies": {"vitest": "^4"}, "scripts": {}})
		with patch.object(frappe, "get_app_path", return_value=self.source_dir):
			with self.assertRaises(DeclarationError) as caught:
				app_runtime_deps("crm")
		message = str(caught.exception)
		self.assertTrue(message.startswith("crm declares `devDependencies`, `scripts` in "))
		self.assertIn("desk.package.json holds `dependencies` and nothing else", message)

	def test_the_framework_reads_its_base_file_with_dev_dependencies(self):
		self.assertIn("vite", app_deps("frappe"))
		self.assertNotIn("vite", app_runtime_deps("frappe"))

	def test_the_import_map_refusal_names_the_declaration_file(self):
		entry = {
			"app": "crm",
			"source_dir": self.source_dir,
			"runtime_deps": {},
			"import_map": {"crm/ui": "x"},
		}
		(problem,) = import_map_problems(entry)
		self.assertIn("desk.package.json does not declare under dependencies", problem)


class TestCostReport(IntegrationTestCase):
	"""One line per app after install: what its declaration added to the tree and what it weighs."""

	def setUp(self):
		self.frontend = tempfile.mkdtemp(prefix="frontend")
		self.addCleanup(shutil.rmtree, self.frontend)
		with open(os.path.join(self.frontend, "package.base.json"), "w") as f:
			json.dump({"dependencies": {"vue": "^3.5.13", "@vueuse/core": "^11.3.0"}}, f)
		os.makedirs(os.path.join(self.frontend, "node_modules", "onscan.js"))
		with open(os.path.join(self.frontend, "node_modules", "onscan.js", "index.js"), "w") as f:
			f.write("x" * 2500)

	def test_an_app_that_adds_nothing_says_so(self):
		manifest = [
			{"app": "frappe", "runtime_deps": {"vue": "^3.5.13"}},
			{"app": "crm", "runtime_deps": {"vue": "^3.5.13", "@vueuse/core": "^11.3.0"}},
		]
		self.assertEqual(
			cost_report(manifest, self.frontend, ["frappe", "crm"]),
			["apps: frappe, crm", "crm: no packages added"],
		)

	def test_every_app_read_is_named_in_file_order_not_only_contributors(self):
		manifest = [{"app": "frappe", "runtime_deps": {}}, {"app": "crm", "runtime_deps": {}}]
		report = cost_report(manifest, self.frontend, ["frappe", "erpnext", "crm"])
		self.assertEqual(report[0], "apps: frappe, erpnext, crm")

	def test_an_added_package_is_named_with_its_installed_size(self):
		manifest = [{"app": "erpnext", "runtime_deps": {"onscan.js": "^1.5.2", "vue": "^3.5.13"}}]
		self.assertEqual(
			cost_report(manifest, self.frontend, ["erpnext"]), ["apps: erpnext", "erpnext: onscan.js 2.5 kB"]
		)

	def test_a_package_an_earlier_app_added_is_not_counted_twice(self):
		manifest = [
			{"app": "erpnext", "runtime_deps": {"onscan.js": "^1.5.2"}},
			{"app": "crm", "runtime_deps": {"onscan.js": "^1.5.2"}},
		]
		self.assertEqual(
			cost_report(manifest, self.frontend, ["erpnext", "crm"]),
			["apps: erpnext, crm", "erpnext: onscan.js 2.5 kB", "crm: no packages added"],
		)

	def test_a_singleton_never_counts_as_added(self):
		manifest = [{"app": "crm", "runtime_deps": {"frappe-ui": "1.0.0-beta.63"}}]
		self.assertEqual(
			cost_report(manifest, self.frontend, ["crm"]), ["apps: crm", "crm: no packages added"]
		)

	def test_the_composed_file_holds_only_what_the_apps_add(self):
		manifest = [
			{"app": "frappe", "runtime_deps": {}},
			{"app": "erpnext", "runtime_deps": {"onscan.js": "^1.5.2", "vue": "^9.0.0"}},
		]
		compose_package_json(manifest, self.frontend)
		with open(os.path.join(self.frontend, "package.json")) as f:
			composed = json.load(f)["dependencies"]
		self.assertEqual(composed, {"vue": "^3.5.13", "@vueuse/core": "^11.3.0", "onscan.js": "^1.5.2"})


class TestImportMapEnforcement(IntegrationTestCase):
	"""A published name is a promise to script authors, checked before vite starts."""

	def setUp(self):
		self.source_dir = tempfile.mkdtemp(prefix="crm")
		os.makedirs(os.path.join(self.source_dir, "frontend", "lib"))
		with open(os.path.join(self.source_dir, "frontend", "lib", "index.js"), "w") as f:
			f.write("export const formatDeal = (doc) => doc;\n")
		self.addCleanup(shutil.rmtree, self.source_dir)

	def entry(self, import_map, runtime_deps=None):
		return {
			"app": "crm",
			"source_dir": self.source_dir,
			"runtime_deps": runtime_deps if runtime_deps is not None else {"@frappe/crm-ui": "^1.2.0"},
			"import_map": import_map,
		}

	def test_the_framework_publishes_its_four_bare_names_and_i18n(self):
		frappe_entry = next(entry for entry in assemble() if entry["app"] == "frappe")
		bare = {
			name: value
			for name, value in frappe_entry["import_map"].items()
			if not name.startswith("frappe/")
		}
		self.assertEqual(bare, {name: name for name in FRAMEWORK_NAMES})
		self.assertEqual(frappe_entry["import_map"]["frappe/i18n"], "./frontend/i18n.js")
		self.assertEqual(import_map_problems(frappe_entry), [])

	def test_the_framework_publishes_a_scoped_name_by_the_app_rule(self):
		# A fifth framework name is not a bare name: `frappe/` passes the same rule as `crm/`.
		self.assertNotIn("frappe/i18n", FRAMEWORK_NAMES)
		entry = {
			"app": "frappe",
			"source_dir": self.source_dir,
			"runtime_deps": {},
			"import_map": {"frappe/i18n": "./frontend/lib/index.js"},
		}
		self.assertEqual(import_map_problems(entry), [])

	def test_a_declared_package_and_a_file_of_the_apps_own_source_pass(self):
		entry = self.entry({"crm/ui": "@frappe/crm-ui", "crm/lib": "./frontend/lib/index.js"})
		self.assertEqual(import_map_problems(entry), [])

	def test_a_file_value_is_rooted_at_the_source_dir_with_either_prefix(self):
		self.assertEqual(import_map_problems(self.entry({"crm/lib": "/frontend/lib/index.js"})), [])

	def test_a_deep_import_of_a_declared_package_passes(self):
		entry = self.entry({"crm/icons": "@frappe/crm-ui/icons"})
		self.assertEqual(import_map_problems(entry), [])

	def test_a_name_outside_the_apps_scope_is_refused(self):
		entry = self.entry({"deals": "@frappe/crm-ui", "gameplan/x": "@frappe/crm-ui"})
		self.assertEqual(
			import_map_problems(entry),
			[
				"crm publishes `deals`: a published name must start with `crm/`",
				"crm publishes `gameplan/x`: a published name must start with `crm/`",
			],
		)

	def test_a_framework_name_is_refused_to_every_other_app(self):
		self.assertEqual(
			import_map_problems(self.entry({"vue": "@frappe/crm-ui"})),
			["crm publishes `vue`, which is a framework name"],
		)

	def test_an_undeclared_package_is_refused(self):
		(problem,) = import_map_problems(self.entry({"crm/ui": "@frappe/crm-ui"}, runtime_deps={}))
		self.assertTrue(problem.startswith("crm publishes `crm/ui` from `@frappe/crm-ui`, which "))
		self.assertTrue(problem.endswith("desk.package.json does not declare under dependencies"))

	def test_a_file_outside_the_source_dir_is_refused(self):
		(problem,) = import_map_problems(self.entry({"crm/lib": "../../frontend/lib/index.js"}))
		self.assertTrue(
			problem.startswith(
				"crm publishes `crm/lib` from `../../frontend/lib/index.js`, which resolves outside "
			)
		)

	def test_a_missing_file_is_refused(self):
		self.assertEqual(
			import_map_problems(self.entry({"crm/lib": "./frontend/lib/missing.js"})),
			["crm publishes `crm/lib` from `./frontend/lib/missing.js`, which is not a file"],
		)

	def test_a_directory_is_not_a_file(self):
		(problem,) = import_map_problems(self.entry({"crm/lib": "./frontend/lib"}))
		self.assertTrue(problem.endswith("which is not a file"))

	def test_a_symlink_out_of_the_source_dir_is_refused(self):
		outside = tempfile.mkdtemp(prefix="elsewhere")
		self.addCleanup(shutil.rmtree, outside)
		with open(os.path.join(outside, "index.js"), "w") as f:
			f.write("export const x = 1;\n")
		os.symlink(
			os.path.join(outside, "index.js"), os.path.join(self.source_dir, "frontend", "lib", "link.js")
		)
		(problem,) = import_map_problems(self.entry({"crm/lib": "./frontend/lib/link.js"}))
		self.assertIn("resolves outside", problem)

	def test_publishing_alone_puts_an_app_in_the_bundle(self):
		"""An app that contributes no file but publishes one is bundled; one that does neither is not."""
		# CI installs frappe alone, so the second app is the invented one, located at the temp dir.
		real_path = frappe.get_app_path
		with (
			a_second_app() as (app, _),
			patch.object(frappe, "get_all_apps", return_value=["frappe", app]),
			patch.object(
				frappe,
				"get_app_path",
				side_effect=lambda name, *rest: self.source_dir if name == app else real_path(name, *rest),
			),
		):
			with patch("frappe.shell.manifest.app_import_map", side_effect=lambda a: {}):
				self.assertNotIn(app, [entry["app"] for entry in assemble()])
			published = {f"{app}/lib": "./frontend/lib/index.js"}
			with patch(
				"frappe.shell.manifest.app_import_map", side_effect=lambda a: published if a == app else {}
			):
				entry = next(entry for entry in assemble() if entry["app"] == app)
				self.assertEqual(entry["import_map"], published)
				self.assertEqual(import_map_problems(entry), [])

	def test_every_problem_is_reported_in_one_failure(self):
		manifest = [
			self.entry({"vue": "@frappe/crm-ui", "crm/lib": "./frontend/lib/missing.js"}),
			{**self.entry({"crm/ui": "@frappe/crm-ui"}, runtime_deps={}), "app": "gameplan"},
		]

		with self.assertRaises(ImportMapConflict) as caught:
			enforce_import_map(manifest)

		lines = str(caught.exception).splitlines()
		self.assertEqual(lines[0], "")
		self.assertEqual(len(lines), 4)
		self.assertTrue(all(line.startswith("  ") for line in lines[1:]))
		self.assertIn("gameplan publishes `crm/ui`", lines[3])

	def test_an_app_with_nothing_to_publish_passes(self):
		enforce_import_map([{"app": "crm", "source_dir": self.source_dir, "runtime_deps": {}}])


class TestShellBoot(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		set_request(method="GET", path="/apps/desk")

	def tearDown(self):
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def test_boot_is_core_plus_the_declaring_app(self):
		from frappe.shell.boot import get_boot

		contributed = {"default_route": "/deals"}
		with a_second_app() as (app, prefix):
			with patch("frappe.shell.boot.app_boot", return_value=contributed):
				boot = get_boot(f"/apps/{prefix}")

		self.assertEqual(boot["shell_base"], f"/apps/{prefix}")
		self.assertEqual(boot["app"], app)
		# Core.
		self.assertIn("csrf_token", boot)
		self.assertIn("timezone", boot["session"])
		# The declaring app's contribution, merged under core.
		self.assertEqual(boot["default_route"], "/deals")

	def test_boot_carries_the_session_and_the_upload_limits(self):
		"""The signed-in person is one nested object, and the limits the uploader reads are top-level."""
		from frappe.core.api.file import get_file_chunk_size, get_max_file_size
		from frappe.shell.boot import get_boot

		boot = get_boot("/apps/desk")

		session = boot["session"]
		self.assertEqual(session["user"]["name"], "Administrator")
		self.assertIn("System Manager", session["roles"])
		self.assertTrue(session["lang"])
		self.assertTrue(session["timezone"])
		self.assertIsInstance(session["defaults"], dict)

		self.assertEqual(boot["max_file_size"], get_max_file_size())
		self.assertEqual(boot["file_chunk_size"], get_file_chunk_size())

		for moved in ("user", "lang", "sysdefaults", "timezone"):
			self.assertNotIn(moved, boot)

	def test_boot_names_the_app_tile(self):
		"""The rail's tile reads the app's own screen entry, and falls back to the app's name."""
		from frappe.shell.boot import get_boot

		boot = get_boot("/apps/desk")
		self.assertEqual(boot["app_title"], "Framework")
		self.assertTrue(boot["app_logo"])

		with a_second_app() as (app, prefix):
			boot = get_boot(f"/apps/{prefix}")
		self.assertEqual(boot["app_title"], app.replace("_", " ").title())
		self.assertIsNone(boot["app_logo"])

	def test_boot_is_small(self):
		"""A total, tighter than the per-key budget: fails loudly if v1's furniture creeps back in."""
		import json

		from frappe.shell.boot import get_boot

		with a_second_app() as (_, prefix):
			payload = get_boot(f"/apps/{prefix}")
		self.assertLess(len(json.dumps(payload, default=str)), 40_000)

	def test_the_address_table_is_permission_independent(self):
		"""An address space cannot change shape per user; access is still refused at the record."""
		from frappe.shell.doctypes import get_address_table

		# Guest is the most thoroughly refused reader, so a permission-keyed shape would show here.
		as_admin = get_address_table()

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		as_guest = get_address_table()

		self.assertEqual(as_admin, as_guest)
		# Two modules, so the module half of the address is shown to be per-doctype.
		self.assertEqual(as_admin["doctypes"]["User"], ["user", "core"])
		self.assertEqual(as_admin["doctypes"]["ToDo"], ["todo", "desk"])

	def test_the_address_table_is_full_bench_and_the_same_under_every_prefix(self):
		"""The prefix is a lens: every doctype is addressable under every prefix, so the table is cacheable."""
		from frappe.shell.doctypes import get_address_table

		doctypes = get_address_table()["doctypes"]

		# Asserted as a set equality, not by naming a second app's doctype: there is no second app on CI.
		self.assertEqual(
			set(doctypes),
			set(frappe.get_all("DocType", filters={"istable": 0}, pluck="name")),
		)

		# Child tables have no page and no address, so they are the one exclusion.
		self.assertNotIn("DocField", doctypes)

		# The table takes no prefix and cannot: there is nothing to vary by.
		self.assertNotIn("app", get_address_table())

	def test_the_address_table_names_the_singles(self):
		"""A single has no list, so the client must know which addresses open the document itself."""
		from frappe.shell.doctypes import get_address_table

		table = get_address_table()

		self.assertEqual(
			set(table["singles"]),
			set(frappe.get_all("DocType", filters={"istable": 0, "issingle": 1}, pluck="name")),
		)
		self.assertIn("System Settings", table["singles"])
		self.assertNotIn("User", table["singles"])
		# Every single is still addressed like any other doctype.
		self.assertEqual(table["doctypes"]["System Settings"], ["system-settings", "core"])

	def test_the_contents_list_is_filtered_where_addressing_is_not(self):
		"""Addressability is full-bench and permission-independent; contents are per app and filtered."""
		from frappe.shell.doctypes import contents_for_app, get_address_table

		self.assertIn("User", get_address_table()["doctypes"])
		self.assertIn("User", {entry["doctype"] for entry in contents_for_app("frappe")})

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		# Still addressable...
		self.assertIn("User", get_address_table()["doctypes"])
		# ...and not offered.
		self.assertNotIn("User", {entry["doctype"] for entry in contents_for_app("frappe")})

	def test_the_slug_table_tracks_doctypes_being_added_and_removed(self):
		"""A new doctype must be addressable, and a deleted one must stop being so."""
		# Keyed on `metadata_version`: `frappe.delete_doc("DocType", ...)` never reaches a `doc_events` handler.
		from frappe.shell.doctypes import get_address_table

		def slugs():
			return {slug for slug, _module in get_address_table()["doctypes"].values()}

		name = "Shell Slug Probe"
		# Start from a known state: an aborted run can leave the doctype behind.
		if frappe.db.exists("DocType", name):
			frappe.delete_doc("DocType", name, force=True)
		self.assertNotIn("shell-slug-probe", slugs())

		frappe.get_doc(
			doctype="DocType",
			name=name,
			module="Core",
			custom=1,
			fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title"}],
			permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
		).insert()
		self.addCleanup(lambda: frappe.delete_doc("DocType", name, force=True, ignore_missing=True))

		self.assertEqual(get_address_table()["doctypes"].get(name), ["shell-slug-probe", "core"])

		frappe.delete_doc("DocType", name, force=True)
		self.assertNotIn("shell-slug-probe", slugs())

	def test_a_contributed_boot_key_cannot_overwrite_core(self):
		"""Core is spread last, or an app could break every save at its own prefix with a bare 400."""
		from frappe.shell.boot import get_boot

		poison = {"csrf_token": "stolen", "session": {"user": {"name": "nobody"}}, "shell_base": "/elsewhere"}
		with patch("frappe.shell.boot.app_boot", return_value=poison):
			boot = get_boot("/apps/desk")

		self.assertNotEqual(boot["csrf_token"], "stolen")
		self.assertNotEqual(boot["session"]["user"]["name"], "nobody")
		self.assertEqual(boot["shell_base"], "/apps/desk")

	def test_the_desk_prefix_boot_is_small_too(self):
		"""The framework's own prefix is the biggest one; a total, tighter than `boot.KEY_BUDGET`."""
		import json

		from frappe.shell.boot import get_boot
		from frappe.shell.doctypes import get_address_table

		boot = get_boot("/apps/desk")
		self.assertLess(len(json.dumps(boot, default=str)), 40_000)
		self.assertNotIn("doctype_slugs", boot)
		self.assertNotIn("DocField", get_address_table()["doctypes"])

	def test_a_doctype_in_a_db_only_module_resolves_to_its_real_owner(self):
		"""A Module Def created from the UI is in no modules.txt, and must not fall to the `frappe` floor."""
		from frappe.shell.doctypes import get_doctype_owners

		with (
			a_second_app() as (owner, _),
			# The invented app has no source dir, so it has no pages for the DocType to be checked against.
			patch("frappe.shell.address_clash.page_files", return_value={}),
		):
			# `custom=1` keeps this off the disk: `on_update` would otherwise rewrite the owning app's modules.txt.
			module = frappe.get_doc(
				doctype="Module Def",
				module_name="Shell DB Only Module",
				app_name=owner,
				custom=1,
			).insert()
			self.addCleanup(lambda: frappe.delete_doc("Module Def", module.name, force=True))

			doctype = frappe.get_doc(
				doctype="DocType",
				name="Shell Module Probe",
				module=module.name,
				custom=1,
				fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title"}],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			).insert()
			self.addCleanup(lambda: frappe.delete_doc("DocType", doctype.name, force=True))

			# The guarded case is a process whose `module_app` was built before the Module Def existed;
			# inserting it rebuilds the map here, so the pre-existing state is restored explicitly.
			stale = dict(frappe.local.module_app)
			stale.pop(frappe.scrub(module.name), None)

			with patch.object(frappe.local, "module_app", stale):
				self.assertNotIn(frappe.scrub(module.name), frappe.local.module_app)
				clear_doctype_owners()
				self.assertEqual(get_doctype_owners().get("Shell Module Probe"), owner)

	def test_the_index_lists_installed_apps(self):
		from frappe.shell.boot import get_boot

		with a_second_app() as (app, prefix):
			boot = get_boot(f"/{SHELL_ROOT}")

		self.assertIsNone(boot["app"])
		self.assertEqual(boot["shell_base"], "/apps")
		routes = {entry["app"]: entry["route"] for entry in boot["apps"]}
		# The framework is on the index by construction.
		self.assertEqual(routes["frappe"], "/apps/desk")
		# And so is anyone else who claims a prefix, with no declaration needed beyond it.
		self.assertEqual(routes[app], f"/apps/{prefix}")


class TestAppPermission(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guest_is_refused_by_default(self):
		from frappe.shell.permissions import has_app_permission

		frappe.set_user("Guest")
		self.assertFalse(has_app_permission("frappe"))

	def test_a_system_user_is_admitted_by_default(self):
		"""The default reproduces `www/desk.py:20-27`, so frappe declares nothing."""
		from frappe.shell.permissions import has_app_permission

		frappe.set_user("Administrator")
		self.assertTrue(has_app_permission("frappe"))

	def test_a_website_user_cannot_read_the_index_boot(self):
		"""`@frappe.whitelist()` excludes Guest and nobody else; a portal login must not read core boot."""
		from frappe.shell.boot import get_boot

		website_user = frappe.db.get_value("User", {"user_type": "Website User", "enabled": 1}, "name")
		if not website_user:
			self.skipTest("no enabled Website User on this site")

		frappe.set_user(website_user)
		with self.assertRaises(frappe.PermissionError):
			get_boot("/apps")

	def test_a_raising_gate_denies_rather_than_degrades(self):
		"""A broken gate costs the door, unlike a broken `app_boot`, which costs its keys."""
		from frappe.shell.permissions import has_app_permission

		with hooks_declaring("app_permission", {"crm": "frappe.shell.nonexistent.handler"}):
			self.assertFalse(has_app_permission("crm"))


class TestModularAddresses(IntegrationTestCase):
	"""The three-segment shape an app opts into with `app_modular`."""

	# Asserted against `frappe` alone with the hook patched: CI installs no other app, and
	# `get_hooks(app_name=)` raises for one that is not on the bench.

	def test_an_app_that_declares_nothing_is_not_modular(self):
		from frappe.shell.registry import is_modular

		self.assertFalse(is_modular("frappe"))

	def test_the_boolean_rides_the_prefix_registry_into_boot(self):
		from frappe.shell.boot import get_boot

		prefixes = get_boot("/apps/desk")["prefixes"]

		self.assertEqual(prefixes["desk"], {"app": "frappe", "modular": False})
		# Every active app, not only the one serving this prefix.
		self.assertEqual(
			{entry["app"] for entry in prefixes.values()},
			set(frappe.get_active_apps(_ensure_on_bench=True)),
		)

	def test_a_modular_app_addresses_every_doctype_through_its_own_module(self):
		"""The shape is the app's, and the module is the doctype's own."""
		from frappe.shell.links import canonical_path

		# Declaring nothing: two segments.
		# The `@` survives unencoded; a docname is not excluded for containing one. A space still quotes.
		self.assertEqual(canonical_path("User", "a@example.org"), "/apps/desk/user/a@example.org")
		self.assertEqual(canonical_path("User", "Test User"), "/apps/desk/user/Test%20User")

		with hooks_declaring("app_modular", {"frappe": True}):
			# Three segments, and the middle one is `User`'s own module, `Core`.
			self.assertEqual(canonical_path("User", "a@example.org"), "/apps/desk/core/user/a@example.org")
			# A doctype from a different module of the same app takes its own module.
			self.assertEqual(canonical_path("ToDo", "TODO-01"), "/apps/desk/desk/todo/TODO-01")

		# And the list form, which has no docname to hang off.
		with hooks_declaring("app_modular", {"frappe": True}):
			self.assertEqual(canonical_path("User"), "/apps/desk/core/user")

	def test_the_manifest_carries_the_shape(self):
		def frappe_entry():
			return next(entry for entry in assemble() if entry["app"] == "frappe")

		self.assertFalse(frappe_entry()["modular"])
		with hooks_declaring("app_modular", {"frappe": True}):
			self.assertTrue(frappe_entry()["modular"])

	def test_the_canonical_address_is_the_owners_prefix(self):
		"""A link built outside a session picks the owner's prefix and never redirects."""
		from frappe.utils import get_url_to_form

		self.assertTrue(get_url_to_form("System Settings").endswith("/apps/desk/system-settings"))
		self.assertTrue(get_url_to_form("User", "Test User").endswith("/apps/desk/user/Test%20User"))

	def test_a_doctype_reached_only_by_sharing_is_offered(self):
		"""A role-only read silently drops a doctype reached purely by sharing."""
		# `Role`, not `Note` or `Tag`: `Note` trips `sync_value_in_queue`'s test assertion, and `Tag`
		# is readable by a role-less System User already.
		import frappe.share
		from frappe.shell.doctypes import contents_for_app

		email = "shell-share-probe@example.com"
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True)
		user = frappe.get_doc(
			doctype="User",
			email=email,
			first_name="Shell Share Probe",
			user_type="System User",
			roles=[],
		).insert()
		self.addCleanup(lambda: frappe.delete_doc("User", user.name, force=True, ignore_missing=True))

		role = frappe.get_doc(doctype="Role", role_name="Shell Share Probe Role").insert()
		self.addCleanup(lambda: frappe.delete_doc("Role", role.name, force=True, ignore_missing=True))

		def offered():
			return {entry["doctype"] for entry in contents_for_app("frappe")}

		frappe.set_user(email)
		self.addCleanup(frappe.set_user, "Administrator")
		self.assertNotIn("Role", offered())

		frappe.set_user("Administrator")
		frappe.share.add("Role", role.name, email, read=1)

		frappe.set_user(email)
		self.assertIn("Role", offered())

	def test_the_module_landing_page_is_permission_filtered(self):
		"""Addressability is not filtered, contents are; nobody pastes a module page as a record link."""
		from frappe.shell.doctypes import contents_for_app

		self.assertTrue(contents_for_app("frappe", "core"))
		self.assertFalse(contents_for_app("frappe", "no-such-module"))

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		self.assertFalse(contents_for_app("frappe", "core"))


class TestSharedSlugs(IntegrationTestCase):
	"""Two DocTypes or two modules with one slug: the one created first keeps the address."""

	def insert(self, doc: dict):
		self.addCleanup(frappe.delete_doc, doc["doctype"], doc["name"], force=True, ignore_missing=True)
		# Only app code can bring two rows with one slug, and install and migrate only warn about it.
		with patch.dict(frappe.flags, {"in_migrate": True}):
			frappe.get_doc(doc).insert()

	def created_in_order(self, doctype: str, older: str, later: str):
		frappe.db.set_value(doctype, older, "creation", "2000-01-01", update_modified=False)
		frappe.db.set_value(doctype, later, "creation", "2000-01-02", update_modified=False)

	def built_with_warnings(self) -> tuple[dict, str]:
		with self.assertLogs(frappe.logger("shell"), "WARNING") as logged:
			table = build_address_table()
		return table, "\n".join(logged.output)

	def test_the_older_doctype_keeps_a_shared_slug(self):
		pair = ("Test Shared Slug", "Test_Shared Slug")
		for name in pair:
			self.insert(new_doctype(name, issingle=1).as_dict())

		for older, later in (pair, pair[::-1]):
			with self.subTest(older=older):
				self.created_in_order("DocType", older, later)
				table, warnings = self.built_with_warnings()

				self.assertEqual(table["doctypes"][older][0], "test-shared-slug")
				self.assertNotIn(later, table["doctypes"])
				self.assertIn(f"DocType {later} has no address", warnings)

	def test_the_older_module_keeps_a_shared_slug(self):
		pair = ("Test Shared Module", "Test_Shared Module")
		for index, module in enumerate([*pair, "Test Lonely Module"]):
			self.insert({"doctype": "Module Def", "name": module, "module_name": module, "custom": 1})
			if module in pair:
				self.insert(
					new_doctype(f"Test Shared Module Kind {index}", issingle=1, module=module).as_dict()
				)

		for older, later in (pair, pair[::-1]):
			with self.subTest(older=older):
				self.created_in_order("Module Def", older, later)
				table, warnings = self.built_with_warnings()

				self.assertEqual(table["modules"]["test-shared-module"], older)
				self.assertIn(f"Module Def {later} has no address", warnings)
				# A module no DocType sits in opens nothing, so it is not offered.
				self.assertNotIn("test-lonely-module", table["modules"])


class TestPageFiles(IntegrationTestCase):
	"""The pages a DocType or a module is checked against, read from disk by the app's shape."""

	def test_an_apps_pages_count_only_against_its_own_shape(self):
		source_dir = tempfile.mkdtemp(prefix=SECOND_APP)
		self.addCleanup(shutil.rmtree, source_dir)
		pages = os.path.join(source_dir, "probe_module", "frontend", "pages")
		os.makedirs(pages)
		page = os.path.join(pages, "board.js")
		with open(page, "w") as f:
			f.write("export default {}\n")

		real_path = frappe.get_app_path
		with (
			a_second_app() as (app, _),
			patch.object(
				frappe,
				"get_app_path",
				side_effect=lambda name, *rest: source_dir if name == app else real_path(name, *rest),
			),
		):
			self.assertEqual(page_files(modular=False).get("board"), page)
			self.assertNotIn("board", page_files(modular=True))

			with hooks_declaring("app_modular", {app: True}):
				self.assertEqual(page_files(modular=True).get("board"), page)
				self.assertNotIn("board", page_files(modular=False))


class TestNoHandBuiltDoctypeUrls(IntegrationTestCase):
	"""`routeFor` is the only sanctioned way to build a doctype URL, enforced here."""

	# A test, not a lint rule, because it has to reach every installed app's contributed files.

	# Two rules: the literal `/apps/<something>` never appears in frontend source, and no
	# template-literal route path, which resolves under a modular prefix to the wrong page.

	#: Each entry needs a reason; a growing allowlist means the rule is wrong.
	ALLOWED: ClassVar[set[str]] = {
		# The router's own construction of a contributed page's path.
		"frontend/src/router/contributed.ts",
		# The builders themselves, and the module that publishes them.
		"frontend/src/router/routeFor.ts",
		"frontend/src/router/generated.ts",
		"frontend/src/public.ts",
		# Documentation of the rule, in the file that explains where the table went.
		"frontend/src/addresses.ts",
	}

	HAND_BUILT = re.compile(
		r"""(?x)
		(/apps/[a-z][a-z0-9_-]*/)      # rule 1: another app's prefix, spelled out
		| (:to="`/)                    # rule 2: a template-literal route path...
		| (href="`/)
		| (\.href\s*=\s*`/)
		| (router\.(push|replace)\(`/)
		"""
	)

	def sources(self):
		"""Every frontend file the bundle compiles: the shell's, and contributed ones."""
		import glob
		import os

		from frappe.shell.manifest import contribution_globs

		frontend = os.path.join(frappe.get_app_source_path("frappe"), "frontend", "src")
		for pattern in ("**/*.ts", "**/*.vue"):
			yield from glob.glob(os.path.join(frontend, pattern), recursive=True)

		for app in frappe.get_all_apps():
			try:
				source_dir = frappe.get_app_path(app)
			except Exception:
				continue
			for pattern in contribution_globs(source_dir):
				yield from glob.glob(pattern)

	def test_no_source_file_builds_a_doctype_url_by_hand(self):
		import os

		root = os.path.dirname(frappe.get_app_source_path("frappe"))
		offences = []

		for path in self.sources():
			relative = os.path.relpath(path, root)
			# Allowlist entries are written relative to the frappe repo root.
			if relative.removeprefix("frappe/") in self.ALLOWED:
				continue
			with open(path) as handle:
				source = strip_comments(handle.read())
			for number, line in enumerate(source.splitlines(), start=1):
				if self.HAND_BUILT.search(line):
					offences.append(f"{relative}:{number}: {line.strip()}")

		self.assertEqual(
			offences,
			[],
			"These build a doctype URL by hand. Use `routeFor`/`urlFor` — the shape is "
			"one segment deeper under an app that declares `app_modular`, so a "
			"hand-built path resolves to the wrong page rather than failing:\n" + "\n".join(offences),
		)


class TestNavigationItemRenderers(IntegrationTestCase):
	"""A kind is a type record plus a colocated `frontend/item.js`, and this keeps them together."""

	# The record arrives at migrate and the JS at build, so the pairing cannot be enforced at runtime.

	def type_root(self) -> str:
		return frappe.get_app_path("frappe", "desk", "navigation_item_type")

	def shipped_types(self) -> list[str]:
		import os

		return sorted(
			entry
			for entry in os.listdir(self.type_root())
			if os.path.isdir(os.path.join(self.type_root(), entry))
		)

	def test_every_shipped_item_type_has_a_renderer_beside_it(self):
		import os

		missing = [
			scrubbed
			for scrubbed in self.shipped_types()
			if not os.path.isfile(os.path.join(self.type_root(), scrubbed, "frontend", "item.js"))
		]

		self.assertEqual(
			missing,
			[],
			"These item types ship a record and no renderer, so the rail resolves them into "
			"boot and then drops them without drawing anything: " + ", ".join(missing),
		)

	def test_every_renderer_has_a_type_record_beside_it(self):
		import os

		orphaned = [
			scrubbed
			for scrubbed in self.shipped_types()
			if os.path.isfile(os.path.join(self.type_root(), scrubbed, "frontend", "item.js"))
			and not os.path.isfile(os.path.join(self.type_root(), scrubbed, f"{scrubbed}.json"))
		]

		self.assertEqual(
			orphaned,
			[],
			"These renderers have no type record beside them. The plugin reads the type's "
			"NAME off that JSON rather than title-casing the folder — `doctype` title-cases "
			"to 'Doctype', and the kind is called `DocType` — so it cannot even be named: "
			+ ", ".join(orphaned),
		)

	def test_an_app_shipping_only_a_kind_reaches_the_bundle(self):
		"""`contributes` decides whether an app's source is compiled in at all; a kind alone must count."""
		import os
		import tempfile

		from frappe.shell.manifest import contributes

		with tempfile.TemporaryDirectory() as source_dir:
			renderer = os.path.join(source_dir, "widgets", "navigation_item_type", "chart", "frontend")
			os.makedirs(renderer)
			self.assertFalse(contributes(source_dir), "nothing shipped yet")

			with open(os.path.join(renderer, "item.js"), "w") as handle:
				handle.write("export default { render: () => null }\n")

			self.assertTrue(contributes(source_dir))


class TestReplacementPageContributions(IntegrationTestCase):
	"""An app whose only contribution is a replacement page still reaches the bundle."""

	def assembled_apps(self, source_dir: str) -> list[str]:
		with (
			patch.object(frappe, "get_all_apps", return_value=["frappe", "helpdesk"]),
			patch.object(frappe, "get_app_path", side_effect=lambda app: source_dir),
			patch.object(frappe, "get_hooks", return_value={}),
			patch("frappe.shell.manifest.declared_prefix", return_value="helpdesk"),
		):
			return [entry["app"] for entry in assemble()]

	def test_pages_json_and_a_page_file_get_a_manifest_entry(self):
		for folder in (("doctype", "hd_ticket", "frontend"), ("custom", "contact")):
			with self.subTest(folder="/".join(folder)):
				source_dir = tempfile.mkdtemp(prefix="helpdesk")
				self.addCleanup(shutil.rmtree, source_dir)
				declared = os.path.join(source_dir, "helpdesk", *folder)
				os.makedirs(os.path.join(declared, "pages"))
				self.assertNotIn("helpdesk", self.assembled_apps(source_dir))

				with open(os.path.join(declared, "pages.json"), "w") as f:
					json.dump({"record": "agent"}, f)
				with open(os.path.join(declared, "pages", "agent.js"), "w") as f:
					f.write('export default { component: () => import("./Agent.vue") }\n')

				self.assertIn("helpdesk", self.assembled_apps(source_dir))

	def test_pages_json_alone_gets_a_manifest_entry(self):
		for folder in (("doctype", "hd_ticket", "frontend"), ("custom", "contact")):
			with self.subTest(folder="/".join(folder)):
				source_dir = tempfile.mkdtemp(prefix="helpdesk")
				self.addCleanup(shutil.rmtree, source_dir)
				declared = os.path.join(source_dir, "helpdesk", *folder)
				os.makedirs(declared)
				self.assertNotIn("helpdesk", self.assembled_apps(source_dir))

				with open(os.path.join(declared, "pages.json"), "w") as f:
					json.dump({"record": "agent"}, f)

				self.assertIn("helpdesk", self.assembled_apps(source_dir))


class TestShellAssetSwap(IntegrationTestCase):
	"""The swap must survive a filesystem that refuses to rename the published directory."""

	def _trees(self):
		root = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, root, ignore_errors=True)
		published = os.path.join(root, "frontend")
		staging = published + ".staging"
		for tree, marker in ((published, "old"), (staging, "new")):
			os.makedirs(os.path.join(tree, "assets"))
			with open(os.path.join(tree, "index.html"), "w") as f:
				f.write(marker)
			with open(os.path.join(tree, "assets", f"app-{marker}.js"), "w") as f:
				f.write(marker)
		return published, staging

	def _assert_swapped(self, published, staging):
		with open(os.path.join(published, "index.html")) as f:
			self.assertEqual(f.read(), "new")
		self.assertEqual(os.listdir(os.path.join(published, "assets")), ["app-new.js"])
		self.assertFalse(os.path.exists(staging))
		self.assertFalse(os.path.exists(published + ".previous"))

	def test_the_new_tree_replaces_the_old(self):
		published, staging = self._trees()
		swap_shell_assets(staging, published)
		self._assert_swapped(published, staging)

	def test_a_refused_rename_copies_the_new_tree_over_the_old(self):
		published, staging = self._trees()
		with patch("os.rename", side_effect=OSError(errno.EXDEV, "Invalid cross-device link")):
			swap_shell_assets(staging, published)
		self._assert_swapped(published, staging)

	def test_a_failed_copy_leaves_the_old_shell_readable(self):
		published, staging = self._trees()
		with (
			patch("os.rename", side_effect=OSError(errno.EXDEV, "Invalid cross-device link")),
			patch("shutil.copytree", side_effect=OSError(errno.ENOSPC, "No space left on device")),
			self.assertRaises(OSError),
		):
			swap_shell_assets(staging, published)
		with open(os.path.join(published, "index.html")) as f:
			self.assertEqual(f.read(), "old")
		self.assertTrue(os.path.exists(os.path.join(staging, "index.html")))

	def test_any_other_rename_failure_is_raised(self):
		published, staging = self._trees()
		with (
			patch("os.rename", side_effect=OSError(errno.EACCES, "Permission denied")),
			self.assertRaises(PermissionError),
		):
			swap_shell_assets(staging, published)
