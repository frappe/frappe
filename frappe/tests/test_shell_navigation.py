# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The desk v2 navigation resolver, `frappe/shell/navigation.py`; the layers belong to `frappe`."""

import contextlib
import json
from unittest.mock import patch

import frappe
from frappe.deferred_insert import queue_prefix
from frappe.shell.boot import BUDGET_LOG_TITLE as TITLE
from frappe.shell.boot import KEY_BUDGET, get_boot
from frappe.shell.navigation import resolve_navigation
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.utils import set_request

APP = "frappe"

# The address of the sidebar these tests ship; `module_def_core` is both the standard
# record's name and the payload key.
ADDRESS = ("Module Def", "Core")
ADDRESS_KEY = "module_def_core"


@contextlib.contextmanager
def shipping():
	"""Place app content on the site the way an install does."""
	# Developer mode, or `validate_standard` refuses the row; `in_import`, or the export writes a
	# JSON file the rollback cannot reach.
	developer_mode = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 1
	frappe.flags.in_import = True
	try:
		yield
	finally:
		frappe.flags.in_import = False
		frappe.conf.developer_mode = developer_mode


class NavigationTestCase(IntegrationTestCase):
	"""Roll the database back after every test, not after the class."""

	# A standard `Rail` is named after its app, so two tests in one class would collide.

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("navigation_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="navigation_test"))


def item(key: str, **kwargs) -> dict:
	return {"doctype": "Navigation Item", "item_type": "DocType", "key": key, **kwargs}


def doctype_item(key: str, doctype: str, **kwargs) -> dict:
	return item(key, link_doctype="DocType", link_to=doctype, **kwargs)


def moved(key: str, *anchors: dict, **kwargs) -> dict:
	"""A layer row that moves the item it names; a layer's row order says nothing."""
	return item(key, anchors=json.dumps(list(anchors)), **kwargs)


def make_rail(
	items: list[dict], *, standard: int = 0, user: str | None = None, app: str = APP, extends: str = ""
):
	doc = frappe.get_doc(
		doctype="Rail",
		app=app,
		extends=extends,
		standard=standard,
		user=user or "",
		items=items,
	)
	with shipping():
		return doc.insert(ignore_permissions=True)


def make_sidebar(items: list[dict], *, standard: int = 0, user: str | None = None, **kwargs):
	doc = frappe.get_doc(
		doctype="Sidebar",
		app=APP,
		standard=standard,
		user=user or "",
		link_doctype=kwargs.pop("link_doctype", ADDRESS[0]),
		link_to=kwargs.pop("link_to", ADDRESS[1]),
		navigation_items=items,
		**kwargs,
	)
	with shipping():
		return doc.insert(ignore_permissions=True)


def keys(items: list[dict]) -> list[str]:
	return [entry["key"] for entry in items]


class TestDerivedRail(NavigationTestCase):
	"""An app that ships no `Rail` record still gets one."""

	def test_an_app_with_no_rail_gets_its_own_doctypes(self):
		rail = resolve_navigation(APP)["rail"]

		self.assertTrue(rail)
		self.assertTrue(all(entry["item_type"] == "DocType" for entry in rail))
		self.assertIn("User", keys(rail))

	def test_a_derived_item_is_keyed_on_the_doctype_name(self):
		entry = next(entry for entry in resolve_navigation(APP)["rail"] if entry["key"] == "User")

		self.assertEqual(entry["link_to"], "User")
		self.assertEqual(entry["link_doctype"], "DocType")

	def test_a_derived_item_carries_no_label(self):
		entry = next(entry for entry in resolve_navigation(APP)["rail"] if entry["key"] == "User")

		self.assertNotIn("label", entry)
		self.assertNotIn("icon", entry)

	def test_a_derived_rail_is_permission_filtered(self):
		with set_user("Guest"):
			self.assertNotIn("User", keys(resolve_navigation(APP)["rail"]))

	def test_derivation_produces_a_rail_and_no_sidebars(self):
		self.assertEqual(resolve_navigation(APP)["sidebars"], {})

	def test_a_derived_rail_goes_through_the_merge(self):
		make_rail([item("User", added=1, link_to="User", label="Everyone")], user=frappe.session.user)

		entry = next(entry for entry in resolve_navigation(APP)["rail"] if entry["key"] == "User")
		self.assertEqual(entry["label"], "Everyone")


class TestShippedRail(NavigationTestCase):
	def test_a_shipped_rail_replaces_derivation(self):
		make_rail([doctype_item("user", "User", label="People")], standard=1)

		rail = resolve_navigation(APP)["rail"]
		self.assertEqual(keys(rail), ["user"])
		self.assertEqual(rail[0]["label"], "People")

	def test_an_app_that_ships_an_empty_rail_gets_an_empty_rail(self):
		make_rail([], standard=1)

		self.assertEqual(resolve_navigation(APP)["rail"], [])

	def test_the_site_layer_then_the_users(self):
		make_rail(
			[doctype_item("user", "User"), doctype_item("role", "Role")],
			standard=1,
		)
		make_rail([moved("role", {"before": "user"})])
		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["role", "user"])

		make_rail([moved("user", {"before": "role"})], user=frappe.session.user)
		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user", "role"])

	def test_a_layer_that_anchors_nothing_moves_nothing(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_rail(
			[item("role", label="Roles", overrides=json.dumps(["label"])), item("user")],
			user=frappe.session.user,
		)

		rail = resolve_navigation(APP)["rail"]
		self.assertEqual(keys(rail), ["user", "role"])
		self.assertEqual(rail[1]["label"], "Roles")

	def test_a_hidden_item_never_reaches_the_payload(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_rail([item("role", hidden=1)])

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_a_user_can_unhide_what_the_site_hid(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_rail([item("role", hidden=1)])
		make_rail([item("role", hidden=0)], user=frappe.session.user)

		self.assertIn("role", keys(resolve_navigation(APP)["rail"]))

	def test_a_delta_naming_an_item_the_app_removed_is_inert(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item("gone"), item("user")])

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_a_layer_added_row_is_the_item(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item("note", added=1, link_to="Note", label="Notes")])

		rail = resolve_navigation(APP)["rail"]
		self.assertIn("note", keys(rail))
		self.assertEqual(next(e for e in rail if e["key"] == "note")["label"], "Notes")

	def test_a_row_with_no_key_names_nothing(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item(None, added=1, link_to="Note", label="Notes")])

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])


class TestOverrides(NavigationTestCase):
	"""`overrides` names the fields a delta has an opinion about, explicitly."""

	def setUp(self):
		super().setUp()
		make_rail(
			[doctype_item("user", "User", label="People", icon="user")],
			standard=1,
		)

	def resolved(self) -> dict:
		return next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")

	def test_only_the_named_fields_are_overridden(self):
		make_rail([item("user", label="Staff", icon="crown", overrides=json.dumps(["label"]))])

		entry = self.resolved()
		self.assertEqual(entry["label"], "Staff")
		self.assertEqual(entry["icon"], "user")

	def test_a_named_field_can_be_blanked(self):
		make_rail([item("user", icon="", overrides=json.dumps(["icon"]))])

		self.assertNotIn("icon", self.resolved())

	def test_a_row_that_names_nothing_changes_nothing(self):
		make_rail([item("user", label="Staff")])

		self.assertEqual(self.resolved()["label"], "People")

	def test_an_unreadable_overrides_list_is_read_as_no_opinion(self):
		make_rail([item("user", label="Staff", overrides="not json")])

		self.assertEqual(self.resolved()["label"], "People")


class TestTheWire(NavigationTestCase):
	def test_the_stored_flags_do_not_travel(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item("user", added=0, overrides="[]")])

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		for field in ("hidden", "added", "overrides"):
			self.assertNotIn(field, entry)

	def test_a_blank_field_is_omitted_rather_than_sent_as_null(self):
		make_rail([doctype_item("user", "User")], standard=1)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertEqual(set(entry), {"key", "item_type", "link_doctype", "link_to"})

	def test_a_payload_arrives_parsed(self):
		make_rail([doctype_item("user", "User", payload=json.dumps({"open_in_new_tab": 1}))], standard=1)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertEqual(entry["payload"], {"open_in_new_tab": 1})

	def test_an_unreadable_payload_is_dropped_and_logged(self):
		make_rail([doctype_item("user", "User", payload="{not json")], standard=1)

		with patch("frappe.log_error") as log_error:
			entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")

		self.assertNotIn("payload", entry)
		self.assertTrue(log_error.called)

	def test_an_item_whose_parent_is_gone_is_promoted(self):
		make_rail([doctype_item("user", "User", parent_key="people")], standard=1)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertNotIn("parent_key", entry)

	def test_a_parent_that_is_present_is_kept(self):
		make_rail(
			[
				item("people", item_type="Section", label="People"),
				doctype_item("user", "User", parent_key="people"),
			],
			standard=1,
		)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertEqual(entry["parent_key"], "people")


class TestSidebars(NavigationTestCase):
	def test_a_sidebar_is_keyed_by_its_scrubbed_address(self):
		shipped = make_sidebar([doctype_item("user", "User")], standard=1)
		mine = make_sidebar(
			[item("user", label="Me", overrides=json.dumps(["label"]))], user=frappe.session.user
		)

		sidebars = resolve_navigation(APP)["sidebars"]

		# The standard record's own name agrees with the key by construction...
		self.assertEqual(shipped.name, ADDRESS_KEY)
		# ...and the user's layer, which is hash-named, still merges into it.
		self.assertNotEqual(mine.name, ADDRESS_KEY)
		self.assertEqual(sidebars[ADDRESS_KEY][0]["label"], "Me")

	def test_a_v2_resolver_never_reads_v1s_rows(self):
		sidebar = make_sidebar([doctype_item("user", "User")], standard=1)
		with shipping():
			sidebar.append("items", {"type": "Link", "label": "A desk v1 row", "link_type": "DocType"})
			sidebar.save(ignore_permissions=True)

		items = resolve_navigation(APP)["sidebars"][ADDRESS_KEY]
		self.assertEqual(keys(items), ["user"])

	def test_an_address_that_resolves_to_nothing_is_absent(self):
		make_sidebar([], standard=1)

		self.assertNotIn(ADDRESS_KEY, resolve_navigation(APP)["sidebars"])

	def test_a_sidebar_nobody_ships_is_not_resolved(self):
		make_sidebar([item("user", added=1, link_to="User")])

		self.assertEqual(resolve_navigation(APP)["sidebars"], {})

	def test_desk_v1s_own_sidebars_are_not_in_the_payload(self):
		make_sidebar([doctype_item("user", "User")], standard=1)

		self.assertEqual(list(resolve_navigation(APP)["sidebars"]), [ADDRESS_KEY])


class TestNavigationInBoot(NavigationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		set_request(method="GET", path="/apps/desk")

	def tearDown(self):
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def test_boot_carries_the_resolved_navigation(self):
		from frappe.shell.boot import get_boot

		boot = get_boot("/apps/desk")

		self.assertIn("navigation", boot)
		self.assertIn("User", keys(boot["navigation"]["rail"]))
		self.assertEqual(boot["navigation"]["sidebars"], {})

	def test_the_index_has_no_navigation(self):
		from frappe.shell.boot import get_boot

		self.assertNotIn("navigation", get_boot("/apps"))

	def test_navigation_is_a_framework_key_a_contribution_cannot_overwrite(self):
		from frappe.shell.boot import get_boot

		with patch("frappe.shell.boot.app_boot", return_value={"navigation": "mine"}):
			boot = get_boot("/apps/desk")

		self.assertIsInstance(boot["navigation"], dict)

	def test_boot_stays_under_the_ceiling_with_navigation_in_it(self):
		from frappe.shell.boot import get_boot

		self.assertLess(len(json.dumps(get_boot("/apps/desk"), default=str)), 40_000)


class TestBootBudget(NavigationTestCase):
	"""The per-key growth alarm at `get_boot`'s exit."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		set_request(method="GET", path="/apps/desk")
		self._clear()

	def tearDown(self):
		self._clear()
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def _clear(self):
		frappe.cache.delete_keys("boot_budget:")
		frappe.cache.delete_value(f"{queue_prefix}Error Log")

	def _logged(self) -> list[str]:
		"""The rows this check has queued, oldest first, read from redis: boot is a GET and is rolled back."""
		queued = frappe.cache.lrange(f"{queue_prefix}Error Log", 0, -1) or []
		records = [json.loads(raw.decode()) for raw in queued]

		return [record["error"] for record in records if record.get("method") == TITLE]

	def test_navigation_for_frappes_own_prefix_is_inside_the_budget(self):
		"""Administrator at `frappe`'s prefix, the worst case frappe's own CI can measure: 19,064 B."""
		payload = json.dumps(resolve_navigation(APP), separators=(",", ":"), default=str)

		self.assertLess(len(payload), KEY_BUDGET)

	def test_a_key_over_budget_is_logged_and_shipped_whole(self):
		"""An over-budget payload ships whole; the row is the only thing the check adds."""
		oversized = "x" * (KEY_BUDGET + 1)

		with patch("frappe.shell.boot.app_boot", return_value={"huge": oversized}):
			boot = get_boot("/apps/desk")

		self.assertEqual(boot["huge"], oversized)
		self.assertEqual(len(self._logged()), 1)
		self.assertIn("huge is 100,003 B", self._logged()[0])
		self.assertIn("Administrator", self._logged()[0])
		self.assertIn("at prefix desk", self._logged()[0])
		self.assertIn("over the 100,000 B key budget", self._logged()[0])

	def test_a_key_inside_the_budget_logs_nothing(self):
		with patch("frappe.shell.boot.app_boot", return_value={"snug": "x" * 10}):
			get_boot("/apps/desk")

		self.assertEqual(self._logged(), [])

	def test_one_row_per_key_per_prefix_per_day_however_many_users_trip_it(self):
		"""The user is named in the message and never in the cache key."""
		with patch("frappe.shell.boot.app_boot", return_value={"huge": "x" * (KEY_BUDGET + 1)}):
			get_boot("/apps/desk")
			get_boot("/apps/desk")
			with set_user(self.a_second_user()):
				get_boot("/apps/desk")

		self.assertEqual(len(self._logged()), 1)

	def test_the_same_key_at_two_addresses_gets_a_row_each(self):
		"""The guard is keyed on the key and the prefix, so one address cannot mute another."""
		with patch("frappe.shell.boot.core_boot", return_value={"huge": "x" * (KEY_BUDGET + 1)}):
			get_boot("/apps/desk")
			get_boot("/apps")

		logged = self._logged()

		self.assertEqual(len(logged), 2)
		self.assertIn("at prefix desk", logged[0])
		self.assertIn("at the /apps index", logged[1])

	def test_the_row_is_queued_rather_than_inserted_into_a_rolled_back_request(self):
		"""Boot is a GET, so a direct insert would be discarded on a transactional engine."""
		with patch("frappe.shell.boot.app_boot", return_value={"huge": "x" * (KEY_BUDGET + 1)}):
			get_boot("/apps/desk")

		self.assertEqual(len(self._logged()), 1)
		self.assertEqual(frappe.db.count("Error Log", {"method": TITLE}), 0)

	def test_the_daily_claim_is_atomic(self):
		"""`SET NX`, so two workers weighing one payload write one row between them."""
		with patch("frappe.shell.boot.app_boot", return_value={"huge": "x" * (KEY_BUDGET + 1)}):
			get_boot("/apps/desk")

		claim = frappe.cache.make_key("boot_budget:huge:desk")

		# nosemgrep: frappe-cache-breaks-multitenancy
		self.assertFalse(frappe.cache.set(name=claim, value=1, ex=60, nx=True))
		self.assertGreater(frappe.cache.ttl(claim), 0)

	def test_a_non_ascii_key_is_weighed_as_the_wire_carries_it(self):
		"""`json.dumps` would escape each character to `\\uXXXX` and over-report by 3x."""
		# 30,000 three-byte characters: 90,000 B as UTF-8, 180,000 B escaped.
		under_budget_as_utf8 = "\u0928" * 30_000

		with patch("frappe.shell.boot.app_boot", return_value={"devanagari": under_budget_as_utf8}):
			get_boot("/apps/desk")

		self.assertEqual(self._logged(), [])

	def test_the_index_payload_is_weighed_too(self):
		"""The index belongs to no app, and shares `get_boot`'s exit and so its alarm."""
		with patch("frappe.shell.boot.core_boot", return_value={"huge": "x" * (KEY_BUDGET + 1)}):
			get_boot("/apps")

		self.assertEqual(len(self._logged()), 1)
		self.assertIn("at the /apps index", self._logged()[0])

	def test_the_boot_total_is_context_and_never_a_second_threshold(self):
		"""Two keys inside the budget summing past it is not an alarm."""
		half = "x" * (KEY_BUDGET - 10)

		with patch("frappe.shell.boot.app_boot", return_value={"a": half, "b": half}):
			get_boot("/apps/desk")

		self.assertEqual(self._logged(), [])

	def test_a_key_that_will_not_serialise_drops_the_check_rather_than_the_shell(self):
		"""The response layer raises the real error moments later; the check stays silent."""

		class Unserialisable:
			def __repr__(self):
				raise ValueError("nope")

		with patch("frappe.shell.boot.app_boot", return_value={"bad": Unserialisable()}):
			boot = get_boot("/apps/desk")

		self.assertIn("bad", boot)
		self.assertEqual(self._logged(), [])

	def a_second_user(self) -> str:
		user = frappe.get_doc(
			doctype="User",
			email="boot-budget@example.com",
			first_name="Boot Budget",
			roles=[{"role": "System Manager"}],
		).insert(ignore_if_duplicate=True)

		return user.name


# Extension — one app's rows on another app's rail

# The extending apps are named but never installed; `active` below is what makes one count.

EXTENDER = "telephony"
OTHER_EXTENDER = "payments"


@contextlib.contextmanager
def active(*apps: str):
	"""Present these apps to the resolver as installed and enabled, in this order."""
	with patch("frappe.get_active_apps", return_value=[APP, *apps]):
		yield


def make_extension(items: list[dict], *, app: str = EXTENDER, host: str = APP):
	return make_rail(items, standard=1, app=app, extends=host)


def anchored(key: str, doctype: str, *anchors: dict, **kwargs) -> dict:
	return doctype_item(key, doctype, anchors=json.dumps(list(anchors)), **kwargs)


class TestExtendedRail(NavigationTestCase):
	def test_a_contributed_item_reaches_the_hosts_rail(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])

		with active(EXTENDER):
			rail = resolve_navigation(APP)["rail"]

		self.assertEqual(keys(rail), ["user", "telephony:calls"])

	def test_an_apps_own_rail_is_not_its_extension_of_somebody_elses(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([doctype_item("elsewhere", "Role")], standard=1, extends="erpnext")

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_an_app_that_is_not_active_contributes_nothing(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])

		with active():
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_extension_merges_into_a_derived_rail(self):
		make_extension([anchored("calls", "Role", {"after": "User"})])

		with active(EXTENDER):
			rail = resolve_navigation(APP)["rail"]

		self.assertIn("User", keys(rail))
		self.assertEqual(keys(rail)[-1], "telephony:calls")

	def test_a_person_arranges_one_list_and_not_one_per_app(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_extension([doctype_item("calls", "Role")])
		make_rail([moved("telephony:calls", {"before": "user"})], user=frappe.session.user)

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["telephony:calls", "user", "role"])

	def test_a_person_may_hide_a_contributed_item(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])
		make_rail([item("telephony:calls", hidden=1)], user=frappe.session.user)

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_a_contribution_is_positioned_and_not_only_appended(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_extension([anchored("calls", "Role", {"after": "user"})])

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user", "telephony:calls", "role"])

	def test_two_apps_contribute_in_installation_order(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])
		make_extension([doctype_item("invoices", "Role")], app=OTHER_EXTENDER)

		with active(OTHER_EXTENDER, EXTENDER):
			self.assertEqual(
				keys(resolve_navigation(APP)["rail"]),
				["user", "payments:invoices", "telephony:calls"],
			)

	def test_a_contributed_item_is_filtered_by_doctype_read(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role"), doctype_item("todos", "ToDo")])

		with active(EXTENDER), set_user("Guest"):
			rail = resolve_navigation(APP)["rail"]

		self.assertNotIn("telephony:calls", keys(rail))

	def test_the_target_apps_own_door_does_not_run(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])

		with active(EXTENDER), patch("frappe.shell.permissions.has_app_permission") as door:
			resolve_navigation(APP)

		door.assert_not_called()

	def test_the_stored_columns_never_reach_the_browser(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([anchored("calls", "Role", {"after": "user"})])

		with active(EXTENDER):
			entry = resolve_navigation(APP)["rail"][1]

		self.assertNotIn("anchors", entry)
		self.assertNotIn("switches_app", entry)
		self.assertNotIn("app", entry)


class TestSwitchingApps(NavigationTestCase):
	"""Following a contributed item keeps you in the host unless its app says otherwise."""

	@contextlib.contextmanager
	def prefixed(self, prefix: str = "telephony", modular: bool = False):
		with (
			patch("frappe.shell.registry.declared_prefix", return_value=prefix),
			patch("frappe.shell.registry.is_modular", return_value=modular),
		):
			yield

	def test_an_item_that_does_not_switch_carries_no_url(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])

		with active(EXTENDER):
			entry = resolve_navigation(APP)["rail"][1]

		self.assertNotIn("url", entry)

	def test_a_switching_item_carries_the_finished_absolute_url(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role", switches_app=1)])

		with active(EXTENDER), self.prefixed():
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "/apps/telephony/role")

	def test_a_modular_prefix_puts_the_module_in_the_address(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role", switches_app=1)])

		with active(EXTENDER), self.prefixed(modular=True):
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "/apps/telephony/core/role")

	def test_a_record_item_carries_the_record(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension(
			[
				item(
					"admin",
					item_type="Record",
					link_doctype="User",
					link_to="Administrator",
					switches_app=1,
				)
			]
		)

		with active(EXTENDER), self.prefixed():
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "/apps/telephony/user/Administrator")

	def test_a_kind_with_no_cross_app_address_falls_back_to_the_host(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([item("docs", item_type="Link", url="https://frappe.io", switches_app=1)])

		with active(EXTENDER), self.prefixed():
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "https://frappe.io")

	def test_a_host_row_never_switches(self):
		make_rail([doctype_item("user", "User", switches_app=1)], standard=1)

		with active(), self.prefixed():
			self.assertNotIn("url", resolve_navigation(APP)["rail"][0])
