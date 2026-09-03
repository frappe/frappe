# The desk v2 shell: routing, the prefix contract, and the two guards.

import re
from contextlib import ExitStack, contextmanager
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.shell import SHELL_ROOT
from frappe.shell.doctypes import clear_doctype_owners
from frappe.shell.install import PrefixCollisionError, before_app_install
from frappe.shell.manifest import SingletonConflict, enforce_singletons
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
	"""One module graph admits one version of each shared library."""

	def test_conflicting_ranges_fail_the_build_naming_both_apps(self):
		manifest = [
			{"app": "frappe", "deps": {"vue": "^3.5.13", "frappe-ui": "1.0.0-beta.24"}},
			{"app": "gameplan", "deps": {"vue": "^3.5.13", "frappe-ui": "1.0.0-beta.50"}},
		]

		with self.assertRaises(SingletonConflict) as caught:
			enforce_singletons(manifest)

		message = str(caught.exception)
		self.assertIn("frappe-ui", message)
		self.assertIn("beta.24", message)
		self.assertIn("beta.50", message)
		self.assertIn("gameplan", message)
		# `vue` agrees, so it must not be reported.
		self.assertNotIn("  vue:", message)

	def test_agreement_passes(self):
		enforce_singletons(
			[
				{"app": "frappe", "deps": {"vue": "^3.5.13"}},
				{"app": "crm", "deps": {"vue": "^3.5.13", "date-fns": "^4.1.0"}},
			]
		)

	def test_a_non_singleton_may_differ_freely(self):
		"""The list is closed. An app pins its own libraries without asking."""
		enforce_singletons(
			[
				{"app": "crm", "deps": {"date-fns": "^4.1.0"}},
				{"app": "gameplan", "deps": {"date-fns": "^2.0.0"}},
			]
		)


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
		self.assertIn("timezone", boot)
		# The declaring app's contribution, merged under core.
		self.assertEqual(boot["default_route"], "/deals")

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

		poison = {"csrf_token": "stolen", "user": {"name": "nobody"}, "shell_base": "/elsewhere"}
		with patch("frappe.shell.boot.app_boot", return_value=poison):
			boot = get_boot("/apps/desk")

		self.assertNotEqual(boot["csrf_token"], "stolen")
		self.assertNotEqual(boot["user"]["name"], "nobody")
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

		with a_second_app() as (owner, _):
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
