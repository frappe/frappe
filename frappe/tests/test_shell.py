# The desk v2 shell: routing, the prefix contract, and the two guards.
#
# Several of these prove things the running skeleton cannot show by running — the
# `frappe_` default derivation (no app on this bench is named that way), the shell's
# refusal to be cached (invisible under `developer_mode`), and the singleton conflict
# (both real consumers agree today). Those are exactly the ones that would otherwise
# rot silently.

from contextlib import ExitStack, contextmanager
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


def hooks_declaring(hook_name: str, values: dict[str, str]):
	"""Patch `get_hooks` for ONE hook on named apps, delegating everything else.

	Delegation is not politeness: `log_error` reads hooks of its own, so a blanket
	`return_value=` patch breaks the very error path some of these tests assert on.
	"""
	real = frappe.get_hooks

	def fake(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if hook == hook_name and app_name in values:
			return [values[app_name]]
		return real(hook, default, app_name)

	return patch.object(frappe, "get_hooks", side_effect=fake)


def hooks_returning(app_prefixes: dict[str, str]):
	return hooks_declaring("app_prefix", app_prefixes)


#: A second app, invented here rather than borrowed from the bench.
SECOND_APP = "shell_probe"
SECOND_PREFIX = "shell-probe"


@contextmanager
def a_second_app(app: str = SECOND_APP, prefix: str | None = SECOND_PREFIX, active: bool = True):
	"""Present a second app to the shell without one being installed.

	Most of what the shell promises — that a prefix resolves, that boot is composed per
	app, that two claimants collide — needs an app besides frappe to mean anything. This
	suite used to borrow the bench's `crm` for that, which made it assert what a
	developer's bench happens to contain: on CI, where frappe is the only app installed,
	fifteen tests failed on `ModuleNotFoundError: No module named 'crm'` and its knock-ons.

	Every seam the shell reads an app through is faked here, and only for `app`:

	- `get_active_apps`, which the prefix registry is built from
	- `get_installed_apps`, which `get_boot_module_app` filters DB-only modules on, and
	  which the install-time prefix guard reads
	- `get_hooks(app_name=...)`, which would otherwise import the app to read them

	`active=False` presents the app as **installed but disabled**: it appears in
	`get_installed_apps` and not in `get_active_apps`, which is exactly the shape
	`get_active_apps` produces for an app named in the `disabled_apps` global.

	Delegation matters as much as it does in `hooks_declaring`: anything asked about a
	real app must still get the real answer.

	The invented app exists in those three answers and **nowhere on disk**, so do not
	route a path this app does not claim while it is active: anything that falls past
	`ShellPage` reaches `StaticPage`, which resolves every app to `get_app_path(app,
	"www")` and raises `ModuleNotFoundError` on one that was never installed.
	"""
	real_hooks = frappe.get_hooks
	real_active = frappe.get_active_apps
	real_installed = frappe.get_installed_apps

	def fake_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if app_name == app:
			# A declared prefix if one was asked for; otherwise the app declares nothing
			# and the derivation in `default_prefix` is what runs.
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


class TestShellPrefixes(IntegrationTestCase):
	def test_default_derivation_when_an_app_declares_nothing(self):
		"""Charter item 2: install an app and it is served, with no declaration at all.

		Both real consumers on this bench exercise one branch each — CRM takes the
		default, frappe overrides — but no app here is named `frappe_*`, so the
		prefix-stripping branch has nothing to prove it but this.
		"""
		self.assertEqual(default_prefix("crm"), "crm")
		self.assertEqual(default_prefix("frappe_whatsapp"), "whatsapp")
		# Underscores are preserved: the derivation strips a vendor prefix, it does not
		# try to guess a nicer name.
		self.assertEqual(default_prefix("hr_management"), "hr_management")
		# An app named exactly `frappe_` must not claim the empty prefix, which would
		# swallow the whole of /apps.
		self.assertEqual(default_prefix("frappe_"), "frappe_")

	def test_an_app_that_declares_nothing_gets_its_own_name(self):
		# `prefix=None` is the point: the app declares no `app_prefix`, so this is the
		# derivation in `default_prefix` running for real rather than a hook answering.
		with a_second_app(prefix=None) as (app, _):
			self.assertEqual(declared_prefix(app), app)

	def test_the_framework_declares_its_own_prefix(self):
		"""Charter item 7: no privileged path. The desk uses the door it is building."""
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
		"""`Rule("/apps/<prefix>/<path:app_path>")` would NOT match a bare `/apps/<prefix>`.

		v1's `/crm` only works because a file literally named `crm/www/crm.html`
		happens to exist. The registry-based renderer has no such accident to rely on,
		so the bare case needs its own test.
		"""
		self.assertIsInstance(self.renderer_for("apps/desk"), ShellPage)
		with a_second_app() as (_, prefix):
			self.assertIsInstance(self.renderer_for(f"apps/{prefix}"), ShellPage)

	def test_a_doctype_route_resolves_under_a_prefix(self):
		with a_second_app() as (_, prefix):
			self.assertIsInstance(self.renderer_for(f"apps/{prefix}/some-doctype/SOME-001"), ShellPage)

	def test_the_index_resolves(self):
		self.assertIsInstance(self.renderer_for(SHELL_ROOT), ShellPage)

	def test_an_unclaimed_prefix_is_a_website_404(self):
		"""The shell owns error states only *inside* a prefix it serves (#42124)."""
		self.assertIsInstance(self.renderer_for("apps/no-such-app"), NotFoundPage)

	def test_desk_v1_is_untouched(self):
		"""This map must coexist with v1, not replace it.

		`/desk` is v1's and stays v1's, even though the framework claims `/apps/desk`.
		That a *prefix* is claimed only under `/apps` — never at the bare name — is
		`split_shell_path`'s to prove, and `test_split_shell_path` does; asserting it
		here would mean routing a bare invented name, which reaches `StaticPage` and the
		filesystem (see `a_second_app`).
		"""
		self.assertNotIsInstance(self.renderer_for("desk"), ShellPage)


class TestPrefixCollisionGuard(IntegrationTestCase):
	"""Collisions fail hard at install, naming every claimant.

	In `before_app_install`, where a raise leaves the site byte-identical —
	`before_install`'s refusal path exits 0 and reports success.
	"""

	def test_a_colliding_prefix_is_refused_naming_both_claimants(self):
		"""Collide with the framework's own `desk`, which every bench has.

		Any installed app would do; frappe is the one guaranteed to be there, and using
		it also proves the framework holds no privileged claim — it collides like anyone.
		"""
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
		"""A disabled app is not serving, but it has not given the prefix up.

		`get_active_apps` is `get_installed_apps` minus the `disabled_apps` global, so a
		guard reading the active list cannot see a disabled claimant at all. Letting the
		install through would make the collision appear later and elsewhere: re-enabling
		the original leaves two apps declaring one prefix, and `build_prefix_registry` is
		a dict comprehension, so one silently overwrites the other and an app becomes
		unreachable with nothing logged.

		Refusing at install is the only point where the operator is present and the site
		is still byte-identical.
		"""
		with a_second_app(prefix="shop", active=False) as (disabled, prefix):
			self.assertNotIn(disabled, frappe.get_active_apps(_ensure_on_bench=True))
			self.assertIn(disabled, frappe.get_installed_apps(_ensure_on_bench=True))

			with hooks_returning({"newapp": prefix}):
				with self.assertRaises(PrefixCollisionError) as caught:
					before_app_install("newapp")

		# Both claimants named, the disabled one included -- an operator who cannot see
		# it in the app list needs the message to say which app is holding the prefix.
		message = str(caught.exception)
		self.assertIn("newapp", message)
		self.assertIn(prefix, message)
		self.assertIn(disabled, message)

	def test_a_v1_route_does_not_collide_with_the_same_name_under_apps(self):
		"""The /apps redraw is what removed this collision.

		CRM is the real case: v1 holds `/crm`, v2 holds `/apps/crm`, and they no longer
		compete — which is why both skeleton consumers ship on their real names. Asserted
		on an invented app so the property is checked, not this bench's app list.
		"""
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
	"""One module graph admits one version of each shared library.

	Both real consumers agree today, so nothing on this bench would exercise this —
	which is precisely why it needs a test rather than a demonstration.
	"""

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
		"""v1's boot is 147,711 bytes, ~120 KB of it desk workspace furniture.

		A generous ceiling: the point is to fail loudly if v1's furniture ever creeps
		back in, not to police a few hundred bytes.
		"""
		import json

		from frappe.shell.boot import get_boot

		with a_second_app() as (_, prefix):
			payload = get_boot(f"/apps/{prefix}")
		self.assertLess(len(json.dumps(payload, default=str)), 40_000)

	def test_the_slug_table_is_permission_independent(self):
		"""An address space cannot change shape per user.

		v1's de-slug table is keyed on `can_read`, so two colleagues pasting the same
		URL resolve it differently. Access is still refused at the record.
		"""
		from frappe.shell.doctypes import slugs_for_app

		# The framework's own table, which is the one a Guest is most thoroughly refused
		# from reading — so if the shape were permission-keyed at all, it would show here.
		as_admin = slugs_for_app("frappe")

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		as_guest = slugs_for_app("frappe")

		self.assertEqual(as_admin, as_guest)
		self.assertEqual(as_admin["user"], "User")

	def test_the_slug_table_tracks_doctypes_being_added_and_removed(self):
		"""A new doctype must be addressable, and a deleted one must stop being so.

		Regression: this cache was originally invalidated from `doc_events` on DocType,
		which looks right and is not — `frappe.delete_doc("DocType", ...)` never reaches
		an `after_delete` handler, so a deleted doctype stayed addressable. It is keyed
		on `metadata_version` instead, which every schema-change path already resets.
		"""
		from frappe.shell.doctypes import slugs_for_app

		name = "Shell Slug Probe"
		# Start from a known state rather than a pristine one: a previous aborted run of
		# this test can leave the doctype behind, and the first assertion would then
		# fail for a reason that has nothing to do with what is being tested.
		if frappe.db.exists("DocType", name):
			frappe.delete_doc("DocType", name, force=True)
		self.assertNotIn("shell-slug-probe", slugs_for_app("frappe"))

		frappe.get_doc(
			doctype="DocType",
			name=name,
			module="Core",
			custom=1,
			fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title"}],
			permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
		).insert()
		self.addCleanup(lambda: frappe.delete_doc("DocType", name, force=True, ignore_missing=True))

		self.assertEqual(slugs_for_app("frappe").get("shell-slug-probe"), name)

		frappe.delete_doc("DocType", name, force=True)
		self.assertNotIn("shell-slug-probe", slugs_for_app("frappe"))

	def test_a_contributed_boot_key_cannot_overwrite_core(self):
		"""Core is spread LAST.

		`app_boot` is a third-party callable merged into the same dict as `csrf_token`
		and `user`. If it won, an app could break every save at its own prefix with a
		bare 400 by returning a key it did not know was taken.
		"""
		from frappe.shell.boot import get_boot

		poison = {"csrf_token": "stolen", "user": {"name": "nobody"}, "shell_base": "/elsewhere"}
		with patch("frappe.shell.boot.app_boot", return_value=poison):
			boot = get_boot("/apps/desk")

		self.assertNotEqual(boot["csrf_token"], "stolen")
		self.assertNotEqual(boot["user"]["name"], "nobody")
		self.assertEqual(boot["shell_base"], "/apps/desk")

	def test_the_desk_prefix_boot_is_small_too(self):
		"""The framework's own prefix is the biggest one, so it is the one to measure.

		Child tables are excluded from the slug table — they have no page and no
		address, and frappe alone has enough of them to dominate this payload.
		"""
		import json

		from frappe.shell.boot import get_boot
		from frappe.shell.doctypes import slugs_for_app

		self.assertLess(len(json.dumps(get_boot("/apps/desk"), default=str)), 40_000)
		self.assertNotIn("doc-field", slugs_for_app("frappe"))

	def test_a_doctype_in_a_db_only_module_resolves_to_its_real_owner(self):
		"""A Module Def created from the UI is in no modules.txt.

		`frappe.local.module_app` misses it, so its doctypes would fall to the `frappe`
		floor and be addressable at /apps/desk rather than the owning app's prefix. The
		floor is deliberate for the *unresolvable* case (#42068) — it must not swallow a
		case that is perfectly resolvable from the database.
		"""
		from frappe.shell.doctypes import get_doctype_owners

		with a_second_app() as (owner, _):
			# `custom=1` keeps this in the database and off the disk: without it
			# `on_update` writes a module folder and rewrites the owning app's
			# modules.txt under `developer_mode`, which is a real edit to a real app
			# for the sake of a test.
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

			# The condition this actually guards against is a process whose `module_app`
			# was built BEFORE the Module Def existed — a running worker, or any fresh
			# process reading a cold cache. Inserting the Module Def rebuilds the map in
			# *this* process, which would make the assertion pass either way, so the
			# pre-existing state is restored explicitly.
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
		# The framework is on the index by construction — charter item 7 made true
		# rather than stated.
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
		"""`@frappe.whitelist()` excludes Guest and nobody else.

		Without an explicit gate, any portal login could call the endpoint directly and
		read core boot — site defaults, the installed-app list — which desk v1 never
		exposed below System User. The tile list being filtered does not help: the leak
		is the core payload around it.
		"""
		from frappe.shell.boot import get_boot

		website_user = frappe.db.get_value("User", {"user_type": "Website User", "enabled": 1}, "name")
		if not website_user:
			self.skipTest("no enabled Website User on this site")

		frappe.set_user(website_user)
		with self.assertRaises(frappe.PermissionError):
			get_boot("/apps")

	def test_a_raising_gate_denies_rather_than_degrades(self):
		"""Deliberately asymmetric with `app_boot`, which degrades.

		A broken contributor costs its boot keys; a broken gate costs the door, because
		failing open is the one outcome a gate may not have.
		"""
		from frappe.shell.permissions import has_app_permission

		with hooks_declaring("app_permission", {"crm": "frappe.shell.nonexistent.handler"}):
			self.assertFalse(has_app_permission("crm"))
