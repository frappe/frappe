# The index boot's tile list: which apps get a tile, where each opens, and in what order.

from contextlib import ExitStack

import frappe
from frappe.shell import SHELL_ROOT
from frappe.shell.boot import get_boot
from frappe.tests import IntegrationTestCase
from frappe.tests.test_shell import a_second_app, hooks_declaring
from frappe.tests.test_shell_navigation import make_rail

V2_APP, V2_PREFIX = "shell_probe", "shell-probe"
LINK_APP, LINK_PREFIX = "shell_link_probe", "shell-link-probe"
ROLE = "Shell Index Probe"
USER = "shell-index-probe@example.com"


def screen(app: str, **kwargs) -> dict:
	return {"name": app, "title": app.replace("_", " ").title(), "logo": f"/assets/{app}/logo.svg", **kwargs}


class TestIndexTiles(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.clear_document_cache, "Installed Applications", "Installed Applications")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.savepoint("index_tiles_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="index_tiles_test"))
		# Before any fake app is active: inserting a User loads every installed app's templates.
		self.user = self.one_role_user()

	def two_apps(self, **screens: dict):
		"""A v2 app that ships a `Rail` and an app that links out, each declaring `screens[app]`."""
		stack = self.enterContext(ExitStack())
		stack.enter_context(a_second_app(V2_APP, V2_PREFIX))
		stack.enter_context(a_second_app(LINK_APP, LINK_PREFIX))
		stack.enter_context(hooks_declaring("add_to_apps_screen", screens))
		make_rail([], app=V2_APP, standard=1)
		for app in (V2_APP, LINK_APP):
			self.installed(app)

	def installed(self, app: str, wizard: bool = False):
		"""Record `app` in Installed Applications, with a setup wizard still to run if `wizard`."""
		doc = frappe.get_doc("Installed Applications")
		doc.append("installed_applications", {"app_name": app, "has_setup_wizard": int(wizard)})
		doc.save(ignore_permissions=True)

	def one_role_user(self) -> str:
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc(doctype="Role", role_name=ROLE, desk_access=1).insert()

		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				doctype="User",
				email=USER,
				first_name="Index Probe",
				user_type="System User",
				send_welcome_email=0,
				roles=[{"role": ROLE}],
			).insert()

		return USER

	def tiles(self, user: str = "Administrator") -> dict[str, dict]:
		frappe.set_user(user)
		return {tile["app"]: tile for tile in get_boot(f"/{SHELL_ROOT}")["apps"]}

	def test_a_v2_app_opens_its_prefix_and_any_other_app_links_out(self):
		self.two_apps(**{V2_APP: screen(V2_APP, route="/probe"), LINK_APP: screen(LINK_APP, route="/link")})

		boot = get_boot(f"/{SHELL_ROOT}")
		self.assertIsNone(boot["app"])
		self.assertEqual(boot["shell_base"], "/apps")

		tiles = self.tiles()
		self.assertEqual(tiles["frappe"]["kind"], "prefix")
		self.assertEqual(tiles["frappe"]["route"], "/apps/desk")
		self.assertEqual(
			tiles[V2_APP],
			{
				"app": V2_APP,
				"title": "Shell Probe",
				"logo": f"/assets/{V2_APP}/logo.svg",
				"kind": "prefix",
				"route": f"/apps/{V2_PREFIX}",
			},
		)
		self.assertEqual(tiles[LINK_APP]["kind"], "link")
		self.assertEqual(tiles[LINK_APP]["route"], "/link")

	def test_an_app_with_no_hook_gets_no_tile(self):
		self.two_apps(**{LINK_APP: screen(LINK_APP, route="/link")})

		self.assertNotIn(V2_APP, self.tiles())

	def test_a_companion_app_gets_no_tile(self):
		self.two_apps(**{V2_APP: screen(V2_APP), LINK_APP: screen(LINK_APP, route="/link")})
		make_rail([], app=LINK_APP, extends=V2_APP, standard=1)

		tiles = self.tiles()
		self.assertNotIn(LINK_APP, tiles)
		self.assertIn(V2_APP, tiles)

	def test_an_app_that_extends_a_host_and_ships_its_own_rail_keeps_its_tile(self):
		self.two_apps(**{V2_APP: screen(V2_APP), LINK_APP: screen(LINK_APP, route="/link")})
		make_rail([], app=V2_APP, extends="frappe", standard=1)

		self.assertEqual(self.tiles()[V2_APP]["kind"], "prefix")

	def test_an_app_that_extends_an_inactive_host_keeps_its_tile(self):
		self.two_apps(**{V2_APP: screen(V2_APP), LINK_APP: screen(LINK_APP, route="/link")})
		make_rail([], app=LINK_APP, extends="shell_absent_host", standard=1)

		self.assertIn(LINK_APP, self.tiles())

	def test_tiles_sort_by_sequence_then_install_order(self):
		self.two_apps(**{V2_APP: screen(V2_APP), LINK_APP: screen(LINK_APP, route="/link", sequence_id=1)})

		order = list(self.tiles())
		self.assertLess(order.index(LINK_APP), order.index(V2_APP))
		# frappe declares 1000, so it trails both.
		self.assertEqual(order[-1], "frappe")

	def test_tiles_with_one_sequence_keep_install_order(self):
		self.two_apps(
			**{
				V2_APP: screen(V2_APP, sequence_id=5),
				LINK_APP: screen(LINK_APP, route="/link", sequence_id=5),
			}
		)

		order = list(self.tiles())
		self.assertEqual(order.index(LINK_APP), order.index(V2_APP) + 1)

	def test_a_one_role_user_gets_v2_tiles_and_the_link_tiles_their_hook_allows(self):
		self.two_apps(
			**{
				V2_APP: screen(V2_APP, has_permission="frappe.permissions.check_app_permission"),
				LINK_APP: screen(
					LINK_APP, route="/link", has_permission="frappe.permissions.check_app_permission"
				),
			}
		)

		self.assertIn(LINK_APP, self.tiles())
		tiles = self.tiles(self.user)
		# A v2 tile answers to `has_app_permission`, never to the hook's check.
		self.assertIn(V2_APP, tiles)
		self.assertNotIn(LINK_APP, tiles)

	def test_an_app_awaiting_its_setup_wizard_shows_to_a_system_manager_only(self):
		self.two_apps(**{V2_APP: screen(V2_APP), LINK_APP: screen(LINK_APP, route="/link")})
		pending = "shell_wizard_probe"
		self.enterContext(a_second_app(pending, "shell-wizard-probe"))
		self.enterContext(hooks_declaring("add_to_apps_screen", {pending: screen(pending, route="/wizard")}))
		self.installed(pending, wizard=True)

		self.assertIn(pending, self.tiles())
		tiles = self.tiles(self.user)
		self.assertNotIn(pending, tiles)
		self.assertIn(LINK_APP, tiles)

	def test_a_v2_tile_answers_to_the_apps_permission_hook(self):
		self.two_apps(**{V2_APP: screen(V2_APP), LINK_APP: screen(LINK_APP, route="/link")})
		self.enterContext(
			hooks_declaring("app_permission", {V2_APP: "frappe.permissions.check_app_permission"})
		)

		self.assertIn(V2_APP, self.tiles())
		self.assertNotIn(V2_APP, self.tiles(self.user))

	def test_a_raising_permission_hook_hides_the_tile(self):
		self.two_apps(
			**{V2_APP: screen(V2_APP), LINK_APP: screen(LINK_APP, has_permission="frappe.no_such.check")}
		)

		self.assertNotIn(LINK_APP, self.tiles())
