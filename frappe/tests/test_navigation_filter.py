# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The desk v2 navigation filter: `frappe/shell/navigation_filter.py`.

**Every test here runs as somebody other than Administrator, and that is not a style choice.**
#42231 decision 13 keeps Administrator's short-circuit, so Administrator passes every permission
bucket before it is read — the shell measured them at 6 ms against an ordinary user's 3,594 ms
largely because of that branch. A suite written as Administrator would pass against a filter that
does nothing at all.

The user is a `Desk User` with no other role. Measured on this bench, that reads 56 doctypes:
`ToDo` yes, `Role` no — which is the pair almost every test below is built out of. `Role` is a
core doctype whose permissions have only ever been System Manager's, so the pair is stable
wherever this runs.
"""

import contextlib
from unittest.mock import patch

import frappe
from frappe.shell.arrangement import get_arrangement, save_arrangement
from frappe.shell.navigation import resolve_navigation, resolve_rail
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_shell_navigation import (
	ADDRESS,
	ADDRESS_KEY,
	APP,
	NavigationTestCase,
	doctype_item,
	item,
	keys,
	make_rail,
	make_sidebar,
	shipping,
)

READABLE = "ToDo"
UNREADABLE = "Role"

# A module holding something this user may read, and one holding nothing. `Desk` owns `ToDo`;
# the empty one is minted per test rather than picked off the site, because which of a bench's
# modules happen to be empty for a Desk User is a fact about the apps installed on it.
FULL_MODULE = "Desk"
EMPTY_MODULE = "Navigation Filter Test"

# A page every desk session has, and one whose `Page.roles` has only ever been System
# Manager's. Both are core frappe pages, so the pair travels.
PERMITTED_PAGE = "desktop"
FORBIDDEN_PAGE = "permission-manager"


def a_desk_user(email: str = "navigation_filter@example.com") -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			doctype="User",
			email=email,
			first_name="Filtered",
			user_type="System User",
			roles=[{"role": "Desk User"}],
		).insert(ignore_permissions=True)

	return email


def a_module(name: str = EMPTY_MODULE) -> str:
	"""A module with no doctypes in it, so `Module Contents` has nothing to find."""
	if not frappe.db.exists("Module Def", name):
		frappe.get_doc(doctype="Module Def", module_name=name, app_name="frappe").insert(
			ignore_permissions=True
		)

	return name


def block(module: str, user: str):
	"""Hide a module from one user the way `User.block_modules` does, and clear what caches it.

	`tabBlock Module` holds **0 rows across 45 users** on both bench sites, so the veto cannot be
	observed without seeding one — which is why it had never been exercised.
	"""
	doc = frappe.get_doc("User", user)
	doc.append("block_modules", {"module": module})
	doc.save(ignore_permissions=True)
	frappe.clear_cache(user=user)


def a_type(type_name: str, rule: str, **kwargs) -> str:
	"""A `Navigation Item Type` row, for the cases the framework's own eight cannot produce."""
	with shipping():
		frappe.get_doc(
			doctype="Navigation Item Type",
			type_name=type_name,
			module="Desk",
			permission_rule=rule,
			**kwargs,
		).insert(ignore_permissions=True)

	return type_name


def vanish(type_name: str):
	"""Take a type row away after its items were authored.

	This is the only way to *reach* the unknown-kind path, and it is also the real one:
	`item_type` is a Link, so nothing can author a row naming a type nobody shipped. An app that
	contributed a kind and was then uninstalled leaves exactly this behind.
	"""
	frappe.db.delete("Navigation Item Type", {"name": type_name})


def a_todo() -> str:
	return frappe.get_doc(doctype="ToDo", description="Filtered").insert(ignore_permissions=True).name


@contextlib.contextmanager
def contributing(item_type: str, path: str = "frappe.tests.test_navigation_filter"):
	"""Stand in for an app's `navigation_item_resolvers` entry, leaving every other hook alone."""
	real = frappe.get_hooks

	def hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if hook == "navigation_item_resolvers":
			return {item_type: [path]}
		return real(hook, default, app_name)

	with patch("frappe.get_hooks", hooks):
		yield


def can_see(items, context):
	"""The `Custom` bucket's contributed half, as an app would ship it.

	Batched by design: it is handed every item of its kind at once, plus the context whose sets
	this pass has already paid for, and returns the ones it allows.
	"""
	seen.append(len(items))

	return [entry for entry in items if entry.get("label") != "secret"]


seen: list[int] = []


def rail_keys(user: str) -> list[str]:
	with set_user(user):
		return keys(resolve_navigation(APP)["rail"])


class FilterTestCase(NavigationTestCase):
	def setUp(self):
		super().setUp()
		self.user = a_desk_user()
		seen.clear()
		# `block` writes a `Block Module` row and clears the user cache to make it visible. The
		# savepoint rolls the row back; nothing rolls the cache back, so a stale `User` document
		# would carry one test's block into the next one. Both users, because the veto test blocks
		# a module on Administrator.
		for user in (self.user, "Administrator"):
			self.addCleanup(frappe.clear_cache, user=user)

	def errors(self, title: str) -> int:
		return frappe.db.count("Error Log", {"method": title})


class TestReadableDocType(FilterTestCase):
	"""The bucket every doctype-pointing kind declares, and the only one the branch had."""

	def test_an_item_pointing_at_an_unreadable_doctype_is_dropped(self):
		make_rail(
			[doctype_item("mine", READABLE), doctype_item("theirs", UNREADABLE)],
			standard=1,
		)

		self.assertEqual(rail_keys(self.user), ["mine"])

	def test_a_record_item_is_checked_on_its_own_link_doctype(self):
		"""`Record` is the one kind that carries the doctype separately, and the column it is read
		from comes off the type row's `target_doctype` rather than off a list of type names.

		Checked at doctype level and no further. #42231 decision 4 accepted the leak outright: a
		per-row `has_permission(doctype, doc=name)` is exactly the shape the 3,594 ms measurement
		punishes, so a Record item can show and then refuse on click."""
		make_rail(
			[
				item("mine", item_type="Record", link_doctype=READABLE, link_to=a_todo()),
				item("theirs", item_type="Record", link_doctype=UNREADABLE, link_to="System Manager"),
			],
			standard=1,
		)

		self.assertEqual(rail_keys(self.user), ["mine"])

	def test_administrator_sees_what_the_bucket_would_have_dropped(self):
		"""#42231 decision 13. Removing the short-circuit would make navigation stricter than the
		permission system it is a courtesy over — and it is why every other test here changes
		user first."""
		make_rail([doctype_item("theirs", UNREADABLE)], standard=1)

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["theirs"])


class TestModuleContents(FilterTestCase):
	"""A module is offered when something in it is readable, and never when this user blocked it."""

	def test_a_module_holding_something_readable_survives(self):
		make_rail([item("desk", item_type="Module", link_to=FULL_MODULE)], standard=1)

		self.assertEqual(rail_keys(self.user), ["desk"])

	def test_a_module_holding_nothing_readable_is_dropped(self):
		make_rail([item("empty", item_type="Module", link_to=a_module())], standard=1)

		self.assertEqual(rail_keys(self.user), [])

	def test_a_blocked_module_ships_nothing(self):
		"""Not #42230's `hidden`, which travels with a flag so the person who set it can unset it.
		A blocked module is not reversible by the reader, so it is absent rather than flagged."""
		make_rail([item("desk", item_type="Module", link_to=FULL_MODULE)], standard=1)
		block(FULL_MODULE, self.user)

		self.assertEqual(rail_keys(self.user), [])

	def test_no_layer_can_resurface_a_blocked_module(self):
		"""The veto runs with permission filtering, over the merged list, so an addition is
		subject to it. `develop`'s `test_curation_cannot_resurface_a_blocked_module` is the
		behaviour this matches."""
		make_rail([doctype_item("mine", READABLE)], standard=1)
		make_rail(
			[item("desk", item_type="Module", link_to=FULL_MODULE, added=1)],
			user=self.user,
		)
		block(FULL_MODULE, self.user)

		self.assertEqual(rail_keys(self.user), ["mine"])

	def test_an_item_inside_a_blocked_module_is_not_touched(self):
		"""The veto gates module-derived items only. Cascading downward is what
		`is_module_visible`'s own docstring forbids: hiding a module hides the way to a document,
		never the document."""
		make_rail([doctype_item("todo", READABLE)], standard=1)
		block(FULL_MODULE, self.user)

		self.assertEqual(rail_keys(self.user), ["todo"])

	def test_an_empty_module_and_a_blocked_one_are_not_the_same_answer(self):
		"""Administrator short-circuits the contents rule and is still subject to the veto, so the
		two facts have to be told apart. Reading the module universe off the address table
		collapsed them: it only names a module owning at least one non-child doctype, so a module
		with nothing in it looked exactly like a blocked one."""
		make_rail([item("empty", item_type="Module", link_to=a_module())], standard=1)

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["empty"])

	def test_the_block_is_a_veto_and_not_a_permission(self):
		"""So it runs ahead of the Administrator branch rather than behind it. An administrator
		who hid a module from themselves meant it; that is their own preference row, and nothing
		else on the User form says otherwise."""
		make_rail([item("desk", item_type="Module", link_to=FULL_MODULE)], standard=1)
		block(FULL_MODULE, "Administrator")

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), [])


class TestTheOtherBuckets(FilterTestCase):
	def test_a_page_the_user_has_not_got_is_dropped(self):
		make_rail(
			[
				item("desktop", item_type="Page", link_to=PERMITTED_PAGE),
				item("nowhere", item_type="Page", link_to=FORBIDDEN_PAGE),
			],
			standard=1,
		)

		self.assertEqual(rail_keys(self.user), ["desktop"])

	def test_a_link_is_never_filtered(self):
		"""`Always Visible` is an explicit bucket rather than a fall-through, which is the whole
		difference from the dock's ungated `URL` case."""
		make_rail([item("out", item_type="Link", url="https://frappe.io")], standard=1)

		self.assertEqual(rail_keys(self.user), ["out"])


class TestTheCascade(FilterTestCase):
	"""`Derived From Children`: an item is worth showing while something under it survives."""

	def test_a_section_whose_children_all_went_goes_too(self):
		make_rail(
			[
				item("group", item_type="Section", label="Admin"),
				doctype_item("theirs", UNREADABLE, parent_key="group"),
			],
			standard=1,
		)

		self.assertEqual(rail_keys(self.user), [])

	def test_a_section_keeping_one_child_stays(self):
		make_rail(
			[
				item("group", item_type="Section", label="Mixed"),
				doctype_item("theirs", UNREADABLE, parent_key="group"),
				doctype_item("mine", READABLE, parent_key="group"),
			],
			standard=1,
		)

		self.assertEqual(rail_keys(self.user), ["group", "mine"])

	def test_an_emptied_section_takes_the_section_holding_it(self):
		"""To a fixpoint, not one pass. A section holding only an emptied section is itself
		empty, and stopping after one sweep leaves the outer one standing over nothing."""
		make_rail(
			[
				item("outer", item_type="Section", label="Outer"),
				item("inner", item_type="Section", label="Inner", parent_key="outer"),
				doctype_item("theirs", UNREADABLE, parent_key="inner"),
			],
			standard=1,
		)

		self.assertEqual(rail_keys(self.user), [])

	def test_an_item_dropped_by_any_other_bucket_leaves_its_children(self):
		"""A permission rule about a heading says nothing about the rows under it, so they are
		promoted to the top level — the same treatment as an app removing a section."""
		make_rail(
			[
				doctype_item("theirs", UNREADABLE),
				doctype_item("mine", READABLE, parent_key="theirs"),
			],
			standard=1,
		)

		with set_user(self.user):
			rail = resolve_navigation(APP)["rail"]

		self.assertEqual(keys(rail), ["mine"])
		self.assertNotIn("parent_key", rail[0])

	def test_a_hidden_section_is_not_counted_as_a_surviving_child(self):
		"""Filtering runs after `_drop_hidden`, so a section whose only child the person hid is
		empty rather than full."""
		make_rail(
			[
				item("group", item_type="Section", label="Mine"),
				doctype_item("mine", READABLE, parent_key="group"),
			],
			standard=1,
		)
		make_rail([item("mine", hidden=1)], user=self.user)

		self.assertEqual(rail_keys(self.user), [])


class TestLinkedSidebars(FilterTestCase):
	"""A rail item of type `Sidebar` derives from rows that are not on the rail at all."""

	def test_a_rail_item_whose_sidebar_filtered_away_is_dropped(self):
		"""#42421 found this has no other observable form: a `Sidebar` item's whole content is
		the sidebar, so with no rows it has no destination, and "renders as independent" and "is
		not drawn" are the same picture."""
		make_sidebar([doctype_item("theirs", UNREADABLE)], standard=1)
		make_rail(
			[item("core", item_type="Sidebar", link_doctype="Sidebar", link_to=ADDRESS_KEY)],
			standard=1,
		)

		with set_user(self.user):
			payload = resolve_navigation(APP)

		self.assertEqual(keys(payload["rail"]), [])
		self.assertNotIn(ADDRESS_KEY, payload["sidebars"])

	def test_a_rail_item_whose_sidebar_keeps_a_row_stays(self):
		make_sidebar([doctype_item("mine", READABLE), doctype_item("theirs", UNREADABLE)], standard=1)
		make_rail(
			[item("core", item_type="Sidebar", link_doctype="Sidebar", link_to=ADDRESS_KEY)],
			standard=1,
		)

		with set_user(self.user):
			payload = resolve_navigation(APP)

		self.assertEqual(keys(payload["rail"]), ["core"])
		self.assertEqual(keys(payload["sidebars"][ADDRESS_KEY]), ["mine"])


class TestTheModuleVetoOnASidebar(FilterTestCase):
	"""`block_modules` reaching a sidebar through the module it is *addressed* at.

	The tests above cover a `Module` item, which is how a doctype-primary app meets a module. A
	module-primary app never authors one: it reaches a module through a `Sidebar` item holding
	`DocType` rows, which the veto deliberately does not touch — so it used to miss that whole
	shape of rail (#42423).
	"""

	DOCTYPE_ADDRESS = ("DocType", READABLE)
	DOCTYPE_ADDRESS_KEY = "doctype_todo"

	def module_sidebar_on_the_rail(self):
		"""What a module-primary rail ships: a linked item over a sidebar of readable rows."""
		make_sidebar([doctype_item("mine", READABLE)], standard=1)
		make_rail(
			[item("core", item_type="Sidebar", link_doctype="Sidebar", link_to=ADDRESS_KEY)],
			standard=1,
		)

	def test_a_module_sidebar_goes_when_its_module_is_blocked(self):
		self.module_sidebar_on_the_rail()
		block("Core", self.user)

		with set_user(self.user):
			payload = resolve_navigation(APP)

		self.assertNotIn(ADDRESS_KEY, payload["sidebars"])
		self.assertEqual(keys(payload["rail"]), [], "the rail item goes with its sidebar")

	def test_the_same_sidebar_survives_when_another_module_is_blocked(self):
		"""The veto names one module, so it is worth showing that it names only that one."""
		self.module_sidebar_on_the_rail()
		block(FULL_MODULE, self.user)

		with set_user(self.user):
			payload = resolve_navigation(APP)

		self.assertEqual(keys(payload["sidebars"][ADDRESS_KEY]), ["mine"])
		self.assertEqual(keys(payload["rail"]), ["core"])

	def test_a_row_inside_a_blocked_module_is_still_reachable_elsewhere(self):
		"""Unchanged, and the reason this rule sits on the address rather than on the rows.
		Hiding a module hides the way to a document, never the document."""
		make_rail([doctype_item("todo", READABLE)], standard=1)
		block("Core", self.user)

		self.assertEqual(rail_keys(self.user), ["todo"])

	def test_a_doctype_addressed_sidebar_is_not_subject_to_the_veto(self):
		"""CRM's shape. A sidebar addressed at a doctype names no module, so no block reaches it
		-- including the block on the module that doctype happens to belong to."""
		make_sidebar(
			[doctype_item("mine", READABLE)],
			standard=1,
			link_doctype=self.DOCTYPE_ADDRESS[0],
			link_to=self.DOCTYPE_ADDRESS[1],
		)
		block("Core", self.user)

		with set_user(self.user):
			payload = resolve_navigation(APP)

		self.assertEqual(keys(payload["sidebars"][self.DOCTYPE_ADDRESS_KEY]), ["mine"])

	def test_no_layer_can_resurface_a_blocked_module_s_sidebar(self):
		"""The address is judged before the layers are read, so a person's own additions to that
		sidebar never get the chance to bring it back."""
		self.module_sidebar_on_the_rail()
		make_sidebar([doctype_item("added", READABLE, added=1)], user=self.user)
		block("Core", self.user)

		with set_user(self.user):
			payload = resolve_navigation(APP)

		self.assertNotIn(ADDRESS_KEY, payload["sidebars"])

	def test_the_veto_outranks_administrator_here_too(self):
		"""Same reason as the `Module` item: it is this account's own preference row."""
		self.module_sidebar_on_the_rail()
		block("Core", "Administrator")

		self.assertNotIn(ADDRESS_KEY, resolve_navigation(APP)["sidebars"])

	def test_one_sidebar_read_on_its_own_answers_the_same_way(self):
		"""`resolve_sidebar` is the arrangement editor's read, and a rule that held only on the
		boot path would let a person arrange a sidebar boot will never send them."""
		from frappe.shell.navigation import resolve_sidebar

		make_sidebar([doctype_item("mine", READABLE)], standard=1)
		block("Core", self.user)

		with set_user(self.user):
			self.assertEqual(resolve_sidebar(*ADDRESS), [])

	def test_the_editor_bypass_still_sees_it(self):
		"""`check_permission=False` is the layer editor's, and a manager arranging the site's
		sidebar must not silently delete rows out of a list their own block shortened."""
		from frappe.shell.navigation import resolve_sidebar

		make_sidebar([doctype_item("mine", READABLE)], standard=1)
		block("Core", self.user)

		with set_user(self.user):
			rows = resolve_sidebar(*ADDRESS, check_permission=False)

		self.assertEqual(keys(rows), ["mine"])

	def test_arranging_a_blocked_module_s_sidebar_is_refused(self):
		"""A save against a list that resolves to nothing is a **delete**: every submitted row
		reduces away and an empty reduction drops the layer. So an editor still open when the
		block landed would destroy an arrangement its owner can no longer see to rebuild."""
		make_sidebar([doctype_item("mine", READABLE), doctype_item("also", "Note")], standard=1)

		with set_user(self.user):
			showing = [dict(entry) for entry in get_arrangement("Sidebar", ADDRESS_KEY)]
			showing.insert(0, showing.pop())
			save_arrangement("Sidebar", ADDRESS_KEY, showing)

		block("Core", self.user)

		with set_user(self.user):
			with self.assertRaises(frappe.ValidationError):
				save_arrangement("Sidebar", ADDRESS_KEY, showing)

		self.assertTrue(
			frappe.db.exists("Sidebar", {"link_to": "Core", "user": self.user, "standard": 0}),
			"the arrangement is still there",
		)

	def test_the_site_scope_may_still_arrange_it(self):
		"""The block is one person's and the site's list is everybody's, so site scope bypasses
		this with the rest of the filter."""
		make_sidebar([doctype_item("mine", READABLE)], standard=1)
		block("Core", "Administrator")

		self.assertEqual(keys(get_arrangement("Sidebar", ADDRESS_KEY, scope="site")), ["mine"])


class TestFailingClosed(FilterTestCase):
	"""An item nobody can filter is skipped and logged, which is #42228's verdict on a missing
	renderer wearing its other hat: "no rule" and "no renderer" behave the same way."""

	TITLE = "Navigation item type cannot be filtered"

	def test_an_item_of_an_unknown_type_is_dropped_and_logged(self):
		"""`is_item_allowed` returns False here and the dock's `is_reachable` returns True. The
		divergence is resolved in the sidebar's favour."""
		make_rail(
			[
				doctype_item("mine", READABLE),
				item("mystery", item_type=a_type("Vanishing", "Always Visible")),
			],
			standard=1,
		)
		vanish("Vanishing")
		before = self.errors(self.TITLE)

		self.assertEqual(rail_keys(self.user), ["mine"])
		self.assertEqual(self.errors(self.TITLE), before + 1)

	def test_one_log_row_per_type_however_many_items(self):
		"""`Error Log` writes are buffered and flushed at commit, so forty items of one broken
		kind would land as forty near-identical rows nobody reads — which is how a loud failure
		becomes a quiet one."""
		gone = a_type("Vanishing", "Always Visible")
		make_rail([item(f"mystery{index}", item_type=gone) for index in range(5)], standard=1)
		vanish(gone)
		before = self.errors(self.TITLE)

		self.assertEqual(rail_keys(self.user), [])
		self.assertEqual(self.errors(self.TITLE), before + 1)

	def test_a_custom_type_shipping_no_resolver_fails_closed(self):
		"""The declaration is a promise of code, so the missing half is a bug in an app rather
		than a reason to show the item."""
		a_type("Unresolved", "Custom")
		make_rail([item("mine", item_type="Unresolved")], standard=1)
		before = self.errors(self.TITLE)

		self.assertEqual(rail_keys(self.user), [])
		self.assertEqual(self.errors(self.TITLE), before + 1)

	def test_administrator_is_not_exempt_from_this_one(self):
		"""The short-circuit is over the *permission* buckets. A kind nobody can filter is a bug
		an administrator especially needs to see, and an empty section is a stray heading for
		them too."""
		make_rail([item("mystery", item_type=a_type("Vanishing", "Always Visible"))], standard=1)
		vanish("Vanishing")

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), [])


class TestTheCustomBucket(FilterTestCase):
	"""The one door out, and #42228's finding that a kind is one contribution rather than a
	scattering: the override rides in the same hook entry as the rest of the type's server code."""

	def test_the_type_decides_and_is_asked_once(self):
		a_type("Contributed", "Custom")
		make_rail(
			[
				item("keep", item_type="Contributed", label="fine"),
				item("drop", item_type="Contributed", label="secret"),
				item("keep_too", item_type="Contributed", label="fine"),
			],
			standard=1,
		)

		with contributing("Contributed"):
			self.assertEqual(rail_keys(self.user), ["keep", "keep_too"])

		# Batched, not per item. A per-item signature is the shape that produced the 3,594 ms
		# measurement, and it invites an override to loop over `frappe.has_permission`.
		self.assertEqual(seen, [3])

	def test_a_resolver_that_raises_fails_closed(self):
		"""A rail that silently showed everything because one app's filter threw is the failure
		this bucket exists to make impossible."""

		def boom(items, context):
			raise ValueError("no")

		a_type("Contributed", "Custom")
		make_rail([item("mine", item_type="Contributed")], standard=1)

		with contributing("Contributed"), patch(f"{__name__}.can_see", boom):
			self.assertEqual(rail_keys(self.user), [])

	def test_the_resolver_is_handed_the_sets_this_pass_already_paid_for(self):
		captured = {}

		def nosy(items, context):
			captured["readable"] = context.readable_doctypes
			captured["user"] = context.user
			return items

		a_type("Contributed", "Custom")
		make_rail([item("mine", item_type="Contributed")], standard=1)

		with contributing("Contributed"), patch(f"{__name__}.can_see", nosy):
			self.assertEqual(rail_keys(self.user), ["mine"])

		self.assertEqual(captured["user"], self.user)
		self.assertIn(READABLE, captured["readable"])


class TestContributedRows(FilterTestCase):
	"""What replacing `_readable` actually changed.

	Contributed rows were the one thing this resolver filtered, on `Readable DocType` alone and
	before the merge — the stopgap #42364 needed because the host is the one party that cannot
	refuse a row another app files onto its rail. They now go through the same pass as everything
	else, on whatever bucket their own type declares.
	"""

	def test_a_contributed_doctype_item_is_still_dropped(self):
		make_rail([doctype_item("mine", READABLE)], standard=1)
		make_rail([doctype_item("theirs", UNREADABLE)], standard=1, extends=APP, app="crm")

		self.assertEqual(rail_keys(self.user), ["mine"])

	def test_a_contributed_page_item_is_now_checked_too(self):
		"""Under the old narrow rule a contributed `Page` item rode in unchecked, because the
		rule only knew one bucket."""
		make_rail([doctype_item("mine", READABLE)], standard=1)
		make_rail(
			[item("nowhere", item_type="Page", link_to=FORBIDDEN_PAGE)],
			standard=1,
			extends=APP,
			app="crm",
		)

		self.assertEqual(rail_keys(self.user), ["mine"])


class TestWhereTheFilterSits(FilterTestCase):
	"""#42231 decision 11: arrangement resolves before filtering, addition is filtered after."""

	def test_a_layer_cannot_add_an_item_the_user_may_not_see(self):
		make_rail([doctype_item("mine", READABLE)], standard=1)
		make_rail([doctype_item("theirs", UNREADABLE, added=1)], user=self.user)

		self.assertEqual(rail_keys(self.user), ["mine"])

	def test_a_move_resolves_against_the_full_list_and_not_the_filtered_one(self):
		"""#42230 decision 8's property, which is why the merge runs first. The move names an
		item this user cannot see; it still lands where the person who wrote it meant, because
		the anchor was resolved before anything was dropped."""
		make_rail(
			[doctype_item("a", READABLE), doctype_item("gone", UNREADABLE), doctype_item("b", READABLE)],
			standard=1,
		)
		make_rail(
			[item("b", anchors='[{"before": "gone"}]')],
			user=self.user,
		)

		self.assertEqual(rail_keys(self.user), ["a", "b"])


class TestTheEditorBypass(FilterTestCase):
	"""The single named exception (#42231 decision 12), and the scope that earns it."""

	def test_the_site_scope_shows_a_manager_rows_they_cannot_see(self):
		"""A manager arranging the site's rail is arranging it for everybody. Filtered down to
		what they personally may see, saving that list would silently delete other people's
		items."""
		make_rail([doctype_item("mine", READABLE), doctype_item("theirs", UNREADABLE)], standard=1)

		self.assertEqual(keys(get_arrangement("Rail", APP, scope="site")), ["mine", "theirs"])

	def test_the_user_scope_does_not(self):
		"""Nothing is bought by it: a person arranging their own list has nobody else's items to
		delete, so showing them rows they may not see would be a leak with no upside."""
		make_rail([doctype_item("mine", READABLE), doctype_item("theirs", UNREADABLE)], standard=1)

		with set_user(self.user):
			self.assertEqual(keys(get_arrangement("Rail", APP)), ["mine"])

	def test_a_save_reduces_against_the_same_list_it_showed(self):
		"""The read and the reduce base are set from one place, so a person's moves anchor
		against the list the client was actually looking at."""
		make_rail([doctype_item("mine", READABLE), doctype_item("theirs", UNREADABLE)], standard=1)

		with set_user(self.user):
			showing = get_arrangement("Rail", APP)
			payload = save_arrangement("Rail", APP, [dict(entry) for entry in showing])

		self.assertEqual(keys(payload["rail"]), ["mine"])

	def test_the_bypass_is_off_everywhere_else(self):
		make_rail([doctype_item("theirs", UNREADABLE)], standard=1)

		with set_user(self.user):
			self.assertEqual(keys(resolve_rail(APP)), [])
