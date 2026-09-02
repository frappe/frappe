# NAVIGATION FILTERING — one rule, dispatched on the bucket each item type declares.
#
# #42231: filtering navigation is a courtesy and never a control. `frappe/utils/modules.py:48`
# says it in the framework's own words — "Hiding a module hides the way to a document, never the
# document itself" — so a rule here may skip an expensive case and be wrong in the safe
# direction. What a document costs to open is decided at the document, by DocPerm.
#
# The single home is the whole point of the ticket. `is_item_allowed` (`desk/utils.py:70`)
# returns False for a type it does not know and the dock's `is_reachable` (`dock.py:1043`)
# returns True: one question, two answers, arrived at by nobody's decision and only because
# there were two places to put it.
#
# It sits beside the resolver rather than beside the `Sidebar` model, which is where #42231
# decision 10 put it. #42356 then moved resolution itself out of both containers' controllers,
# for the reason that decision was reaching for — the rule spans two surfaces, so it belongs to
# neither — and this filter's only caller is that resolver.
#
# No per-item permission call anywhere below. #42231 decision 7 measured 553 `has_permission`
# calls at **3,594 ms** for an ordinary System User against **25 ms** for one role-based pass,
# and this runs inside boot's blocking pre-mount fetch.

from functools import cached_property

import frappe
from frappe.utils.modules import get_visible_modules

# The six buckets, spelled as they are on `Navigation Item Type.permission_rule`.
READABLE_DOCTYPE = "Readable DocType"
MODULE_CONTENTS = "Module Contents"
DERIVED_FROM_CHILDREN = "Derived From Children"
PERMITTED_PAGE = "Permitted Page"
ALWAYS_VISIBLE = "Always Visible"
CUSTOM = "Custom"


def filter_items(items: list[dict], context: "NavigationContext") -> list[dict]:
	"""Drop every item this user may not see, then drop whatever is left holding nothing.

	One pass for the buckets that decide an item on its own, then a fixpoint for the two that
	decide it from what survived under it. The order is forced: a `Section` cannot know whether
	it is empty until everything below it has been judged.

	Runs on the **merged** list, after the layers have been folded in. #42231 decision 11 read
	#42230's decisions 4 and 8 as opposite orderings and found they are not: a layer does two
	things and they gate differently. *Arrangement* — order and parenting — resolves against the
	full base, so one person's stored move means the same thing whatever they may see; then this
	runs, over the arrangement's result, which is what stops an *addition* from bringing back an
	item the person is not allowed to see.
	"""
	if not items:
		return items

	verdicts: dict[int, bool | None] = {}
	custom: dict[str, list[int]] = {}
	unknown: dict[str, int] = {}

	for index, item in enumerate(items):
		item_type = item.get("item_type")
		bucket = context.rule(item_type)

		if bucket == CUSTOM:
			custom.setdefault(item_type, []).append(index)
		elif bucket == DERIVED_FROM_CHILDREN:
			# Left undecided on purpose. `None` is what the cascade below looks for.
			verdicts[index] = None
		elif bucket in (READABLE_DOCTYPE, MODULE_CONTENTS, PERMITTED_PAGE, ALWAYS_VISIBLE):
			verdicts[index] = _decide(bucket, item, context)
		else:
			# No type row, or a row declaring a bucket this version does not implement.
			verdicts[index] = False
			unknown[item_type] = unknown.get(item_type, 0) + 1

	for item_type, indexes in custom.items():
		verdicts.update(_ask_the_type(item_type, indexes, items, context))

	for item_type, count in unknown.items():
		context.report_unfilterable(item_type, count)

	return _cascade(items, verdicts, context)


def _decide(bucket: str, item: dict, context: "NavigationContext") -> bool:
	if bucket == ALWAYS_VISIBLE:
		return True

	if bucket == READABLE_DOCTYPE:
		return context.may_read(_destination_doctype(item, context))

	if bucket == MODULE_CONTENTS:
		return context.module_is_offered(item.get("link_to"))

	return context.page_is_permitted(item.get("link_to"))


def _destination_doctype(item: dict, context: "NavigationContext") -> str | None:
	"""Which column names the doctype, read off the type row rather than off a list of names.

	A type whose `target_doctype` is `DocType` points *at* a doctype, so the doctype is its
	`link_to`; every other type that reads this bucket points at a document and carries the
	doctype separately in `link_doctype`. Both of the framework's cases fall out of that —
	`DocType` and `Record` — and so does a contributed type that picks the bucket, which is what
	#42228's two-files-and-no-framework-change property requires.
	"""
	if context.target(item.get("item_type")) == "DocType":
		return item.get("link_to")

	return item.get("link_doctype")


def _ask_the_type(
	item_type: str, indexes: list[int], items: list[dict], context: "NavigationContext"
) -> dict[int, bool]:
	"""The `Custom` bucket: hand the type's own `can_see` every item of its kind at once.

	Batched, and that is the signature #42231 decision 9 settled rather than a detail of it. A
	per-item `can_see(item, user)` is the shape that produced the 3,594 ms measurement, and it
	invites an override to loop over `frappe.has_permission`; handing over the whole list plus
	the context this pass has already computed makes the cheap implementation the obvious one.

	A type that declares `Custom` and ships no `can_see` fails closed, like a type with no row
	at all — the declaration is a promise of code, and the missing half is a bug in an app.
	Anything the resolver raises is the same: a rail that silently shows everything because one
	app's filter threw is the failure this bucket exists to make impossible.
	"""
	mine = [items[index] for index in indexes]
	can_see = context.resolver(item_type)

	if can_see is None:
		context.report_unfilterable(item_type, len(mine), custom=True)
		return dict.fromkeys(indexes, False)

	try:
		allowed = {entry.get("key") for entry in can_see(mine, context)}
	except Exception:
		frappe.log_error(title=f"Navigation item type {item_type} could not decide visibility")
		return dict.fromkeys(indexes, False)

	return {index: items[index].get("key") in allowed for index in indexes}


def _cascade(items: list[dict], verdicts: dict[int, bool | None], context: "NavigationContext") -> list[dict]:
	"""Drop a `Derived From Children` item holding nothing, and keep going until nothing moves.

	To a fixpoint because emptiness propagates: a Section holding only an emptied Section is
	itself empty, and one pass would leave the outer one standing (#42231 decision 6). `develop`
	never checks a Section Break at all (`sidebar.py:1539`), so a section whose every row was
	filtered away survives there as a heading over nothing — a door you cannot open, which is
	exactly what a courtesy filter should not leave behind.

	An item dropped by any *other* bucket leaves its children where they are; `_promote_orphans`
	lifts them to the top level on the way out. That is deliberate and is the same treatment as
	an app removing a section: a permission rule about a heading says nothing about the rows
	under it.
	"""
	children: dict[str, list[int]] = {}
	for index, item in enumerate(items):
		parent = item.get("parent_key")
		if parent:
			children.setdefault(parent, []).append(index)

	kept = {index for index in range(len(items)) if verdicts.get(index) is not False}

	while True:
		empty = {
			index
			for index in kept
			if verdicts.get(index) is None and not _holds_something(index, items, children, kept, context)
		}
		if not empty:
			break
		kept -= empty

	return [item for index, item in enumerate(items) if index in kept]


def _holds_something(
	index: int,
	items: list[dict],
	children: dict[str, list[int]],
	kept: set[int],
	context: "NavigationContext",
) -> bool:
	"""What is *under* a derived item, which is two different places depending on the type.

	A `Section` holds its own child rows, found by `parent_key`. A type pointing at a `Sidebar`
	holds that sidebar's rows, which are not on this list at all — so a rail item whose sidebar
	filtered away to nothing goes with it. #42421 found that has no other observable form: a
	`Sidebar` item's whole content is the sidebar, so with no rows it has no destination, and
	"renders as independent" and "is not drawn" are the same picture.

	`None` from `linked` means the sidebars are not resolved here and the question cannot be
	asked, which keeps the item. Unknown is not empty.
	"""
	item = items[index]

	if context.target(item.get("item_type")) == "Sidebar":
		linked = context.linked
		return linked is None or item.get("link_to") in linked

	return any(child in kept for child in children.get(item.get("key"), []))


class NavigationContext:
	"""Every input the buckets read, computed at most once per resolution.

	Per resolution, not per request, and `frappe.utils.caching.request_cache` is the obvious
	home that would be wrong: nothing clears it on `frappe.set_user`, so a request that changes
	user would answer the second one out of the first one's sets. These are per-user sets, and a
	cache with no invalidation for the thing it varies on is worse than no cache.

	It is also what the `Custom` bucket is handed, so an app's own `can_see` gets the sets this
	pass has already paid for rather than computing its own.
	"""

	def __init__(self, app: str):
		self.app = app
		self.user = frappe.session.user
		# #42231 decision 13: Administrator short-circuits every permission check, matching
		# `permissions.py:109` — removing it would make navigation stricter than the permission
		# system it is a courtesy over. It buys the consequence worth writing down: **Administrator
		# is the worst possible account to test this filter with**, and every bug in these rules is
		# invisible to the person most likely to be looking.
		#
		# It covers the permission buckets and nothing else. An empty section is a stray heading
		# for Administrator too, and a type nobody can filter is a bug an administrator especially
		# needs to see, so the cascade and the fail-closed path below run for everyone.
		self.administrator = self.user == "Administrator"
		self._sidebars: dict[str, list[dict]] | None = None
		self._resolving = False
		self._reported: set[str] = set()
		# Looked up once per type, not once per container: a modular app resolves one sidebar per
		# module, and `get_attr` re-checks the installed-app list on every call.
		self._resolvers: dict[str, object] = {}

	# The buckets' inputs

	def may_read(self, doctype: str | None) -> bool:
		return bool(doctype) and (self.administrator or doctype in self.readable_doctypes)

	def module_is_offered(self, module: str | None) -> bool:
		"""A module is offered when something in it is readable, unless this user blocked it.

		The union of its contents is the only rule that needs no second thing for an
		administrator to maintain, and desk v1 never had another one: a module became visible
		there purely as a consequence of its workspaces surviving (`desktop.py:63-92`).

		The block is a **veto and not a permission**, which is why it runs ahead of the
		Administrator branch: it is this user's own `User.block_modules` row, so an administrator
		who hid a module meant it. It gates module-derived items only — block Accounts and a
		`DocType` item pointing at Sales Invoice stays, because cascading downward is what
		`is_module_visible`'s docstring forbids. And it runs here, before any layer is added on
		top, so no layer can resurface a blocked module (#42323).
		"""
		if not module or module in self.blocked_modules:
			return False

		return self.administrator or module in self.readable_modules

	def page_is_permitted(self, page: str | None) -> bool:
		return bool(page) and (self.administrator or page in self.permitted_pages)

	def address_is_offered(self, link_doctype: str | None, link_to: str | None) -> bool:
		"""Whether a whole sidebar's address survives this user's own vetoes.

		The block only, and not the two questions `module_is_offered` asks. A module sidebar may
		link outside its own module — 101 of ERPNext's rows do — so asking about the module's
		*contents* here would empty a sidebar whose rows are all fine.

		It lands on the address rather than on the rail item because that is what keeps it one
		rule: a module sidebar is addressed at its `Module Def`, so the block has something to
		name, and the rail item then goes on its own through the `Derived From Children` cascade
		(#42423). Without it the veto misses every module-primary rail, since such a rail reaches
		a module through a `Sidebar` item whose rows are `DocType` items.
		"""
		if link_doctype != "Module Def":
			return True

		return bool(link_to) and link_to not in self.blocked_modules

	@cached_property
	def readable_doctypes(self) -> set[str]:
		"""`get_doctypes_with_read() | get_shared_doctypes()`, once.

		The shell's own set, not a second answer to the same question: `shell/doctypes.py:164`
		already computes it for the derived rail and for an app's contents, and #42231 decision 10
		exists because two functions answering "may this user read this doctype" is how the two
		surfaces came to disagree in the first place.
		"""
		from .doctypes import get_readable_doctypes

		return get_readable_doctypes()

	@cached_property
	def blocked_modules(self) -> set[str]:
		"""Module names this user has hidden, as the complement of the framework's own answer.

		`get_visible_modules` and not `User.get_blocked_modules()`, which `desktop.py:83` and
		`desktop_icon.py:133` still read directly — a second module-visibility helper is the
		divergence this ticket is closing on the item side, and it would be no better here. One
		call for the whole list, since the batched helper exists precisely for that.

		Over every `Module Def`, not over the modules in the address table. The address table only
		names a module that owns at least one non-child doctype, so reading the universe off it
		would make "this module has nothing addressable in it" and "this user blocked it" the same
		answer — two different facts, and only one of them is a veto that outranks Administrator.
		"""
		modules = frappe.get_all("Module Def", pluck="name")

		return set(modules) - set(get_visible_modules(modules))

	@cached_property
	def readable_modules(self) -> set[str]:
		"""The modules holding at least one doctype this user may read.

		A set operation over two things already in hand, which is what makes decision 5 nearly
		free: the address table is cached on `metadata_version` and shared by every user, and the
		readable set is the one pass above.
		"""
		from .doctypes import get_address_table

		table = get_address_table()
		names = table["modules"]

		return {
			names[module_slug]
			for doctype, (_slug, module_slug) in table["doctypes"].items()
			if module_slug in names and doctype in self.readable_doctypes
		}

	@cached_property
	def permitted_pages(self) -> set[str]:
		"""The `DeskViews` page set, read fresh rather than out of its six-hour per-user cache.

		`get_allowed_pages(cache=True)` is what desk v1 reads, and #42231 decision 7 named that
		cache a precedent not to extend: a stale set means a user keeps seeing an item for up to
		six hours after losing the permission. Uncached it is one query, and only when a `Page`
		item is actually on the list to ask about.
		"""
		from frappe.desk.desk_views import DeskViews

		return set(DeskViews.get_allowed_pages())

	# The type table

	def rule(self, item_type: str | None) -> str | None:
		return self._types.get(item_type, (None, None))[0]

	def target(self, item_type: str | None) -> str | None:
		return self._types.get(item_type, (None, None))[1]

	def resolver(self, item_type: str):
		"""The `can_see` an app contributed beside its renderer, or None.

		One hook and not a second one: #42228 found that a kind is one contribution rather than a
		scattering, so the override rides in the same `navigation_item_resolvers` entry as the
		rest of the type's server code. (#42228 spelled the hook `sidebar_item_resolvers`, before
		#42312 renamed the row family to `Navigation Item`.)

		Two apps claiming one type name is a collision rather than an ordering: the type row
		itself is owned by whichever app ships it, so a second app's resolver is filing code
		against somebody else's kind. The later app wins, loudly — `override_doctype_class` taking
		`[-1]` *silently* (`base_document.py:151`) is the precedent #42228 rejected, and the noise
		is the whole difference.
		"""
		if item_type in self._resolvers:
			return self._resolvers[item_type]

		self._resolvers[item_type] = None
		paths = frappe.get_hooks("navigation_item_resolvers", default={}).get(item_type) or []

		if len(paths) > 1:
			frappe.log_error(
				title="Two apps contribute one navigation item type",
				message=f"{item_type} is resolved by {paths}; the last one wins.",
			)

		for path in reversed(paths):
			try:
				self._resolvers[item_type] = frappe.get_attr(f"{path}.can_see")
				return self._resolvers[item_type]
			except Exception:
				# A path an app got wrong is a bug in that app, and every way of getting it wrong
				# lands here: a missing attribute, an unimportable module, and `get_attr`'s own
				# throw for an app that is not installed. The type falls through to failing
				# closed, which logs and names it.
				frappe.log_error(title=f"Navigation item type {item_type} has an unusable resolver")

		return None

	@cached_property
	def _types(self) -> dict[str, tuple[str, str]]:
		"""`{type: (bucket, target_doctype)}` — what every kind declares about itself.

		One query for both columns. The bucket lives on the type's own standard JSON record
		because the server needs it before it runs anything, and because that keeps #42228's
		property intact: a doctype-pointing kind picks a bucket in its JSON and writes no Python
		at all (#42231 decision 9).
		"""
		return {
			row.name: (row.permission_rule, row.target_doctype)
			for row in frappe.get_all(
				"Navigation Item Type", fields=["name", "permission_rule", "target_doctype"]
			)
		}

	# What a derived item on the rail hangs off

	@property
	def sidebars(self) -> dict[str, list[dict]] | None:
		"""This app's resolved sidebars, filtered, computed once and shared with the rail.

		The rail is resolved *after* them and reads this, because a rail item pointing at a
		sidebar derives from that sidebar's rows. Boot wants both anyway, so sharing costs
		nothing there; the arrangement editor resolves a rail on its own and pays one pair of
		queries to answer the same question honestly.

		`None` while they are themselves being resolved. A sidebar row that points at a sidebar
		would otherwise re-enter this and never come back, and "not resolved yet" is genuinely
		not the same answer as "resolved to nothing".
		"""
		if not self.app:
			# A caller holding one sidebar and no prefix. Unknown, not empty.
			return None

		if self._sidebars is None and not self._resolving:
			from .navigation import resolve_sidebars

			self._resolving = True
			try:
				self._sidebars = resolve_sidebars(self.app, self)
			finally:
				self._resolving = False

		return self._sidebars

	@property
	def linked(self) -> set[str] | None:
		sidebars = self.sidebars

		return None if sidebars is None else set(sidebars)

	# Failing closed, loudly

	def report_unfilterable(self, item_type: str | None, count: int, *, custom: bool = False):
		"""One log row per type per resolution, naming the kind and how many items it cost.

		Deduped because `Error Log` writes are buffered and flushed at commit, so forty items of
		one broken kind would land as forty near-identical rows nobody reads — which is how a
		loud failure becomes a quiet one.

		Failing closed is #42228's verdict on a missing *renderer* wearing its other hat: "no rule"
		and "no renderer" behave identically, so an item that cannot be filtered is skipped and
		logged. Not a security argument — under a courtesy filter an invisible item plus a log
		entry surfaces the bug, while a silently visible one never does.
		"""
		if item_type in self._reported:
			return

		self._reported.add(item_type)
		reason = (
			"declares the Custom permission rule and contributes no `can_see`"
			if custom
			else "has no `Navigation Item Type` row, or declares a permission rule this version does not know"
		)
		frappe.log_error(
			title="Navigation item type cannot be filtered",
			message=f"{item_type!r} {reason}; {count} item(s) were skipped.",
		)
