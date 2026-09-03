# NAVIGATION FILTERING — one rule, dispatched on the bucket each item type declares.

# A courtesy, never a control: a rule here may skip an expensive case and be wrong in the safe
# direction. What a document costs to open is decided at the document, by DocPerm.

# No per-item permission call anywhere below: 553 `has_permission` calls cost 3,594 ms against
# 25 ms for one role-based pass, and this runs inside boot's blocking fetch.

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
	"""Drop every item this user may not see, then drop whatever is left holding nothing."""
	# Runs on the merged list, after the layers: arrangement resolves against the full base, and
	# this then stops an addition from bringing back an item the person may not see.
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
	"""Which column names the doctype: `link_to` for a type pointing at a DocType, else `link_doctype`."""
	if context.target(item.get("item_type")) == "DocType":
		return item.get("link_to")

	return item.get("link_doctype")


def _ask_the_type(
	item_type: str, indexes: list[int], items: list[dict], context: "NavigationContext"
) -> dict[int, bool]:
	"""The `Custom` bucket: hand the type's own `can_see` every item of its kind at once."""
	# Batched, so the cheap implementation is the obvious one; a type that declares `Custom`
	# and ships no `can_see`, or whose `can_see` raises, fails closed.
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
	"""Drop a `Derived From Children` item holding nothing, and keep going until nothing moves."""
	# A fixpoint because emptiness propagates: a Section holding only an emptied Section is empty.
	# An item dropped by another bucket leaves its children; `_promote_orphans` lifts them later.
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
	"""What is under a derived item: a `Section`'s child rows, or the rows of the sidebar it points at."""
	# `None` from `linked` means the sidebars are not resolved here; unknown is not empty.
	item = items[index]

	if context.target(item.get("item_type")) == "Sidebar":
		linked = context.linked
		return linked is None or item.get("link_to") in linked

	return any(child in kept for child in children.get(item.get("key"), []))


class NavigationContext:
	"""Every input the buckets read, computed at most once per resolution."""
	# Per resolution, not `request_cache`: nothing clears that on `frappe.set_user`, and these
	# are per-user sets.

	def __init__(self, app: str):
		self.app = app
		self.user = frappe.session.user
		# Administrator short-circuits the permission buckets only, as `has_permission` does; the
		# cascade and the fail-closed path run for everyone. Never test this filter as Administrator.
		self.administrator = self.user == "Administrator"
		self._sidebars: dict[str, list[dict]] | None = None
		self._resolving = False
		self._reported: set[str] = set()
		# Once per type, not per container: `get_attr` re-checks the installed-app list every call.
		self._resolvers: dict[str, object] = {}

	# The buckets' inputs

	def may_read(self, doctype: str | None) -> bool:
		return bool(doctype) and (self.administrator or doctype in self.readable_doctypes)

	def module_is_offered(self, module: str | None) -> bool:
		"""A module is offered when something in it is readable, unless this user blocked it."""
		# The block is a veto, not a permission, so it runs ahead of the Administrator branch and
		# before any layer is added; it gates module-derived items only.
		if not module or module in self.blocked_modules:
			return False

		return self.administrator or module in self.readable_modules

	def page_is_permitted(self, page: str | None) -> bool:
		return bool(page) and (self.administrator or page in self.permitted_pages)

	def address_is_offered(self, link_doctype: str | None, link_to: str | None) -> bool:
		"""Whether a whole sidebar's address survives this user's own vetoes."""
		# The block only: a module sidebar may link outside its module, so asking about the
		# module's contents would empty a sidebar whose rows are all fine.
		if link_doctype != "Module Def":
			return True

		return bool(link_to) and link_to not in self.blocked_modules

	@cached_property
	def readable_doctypes(self) -> set[str]:
		"""`get_doctypes_with_read() | get_shared_doctypes()`, once, from the shell's one answer."""
		from .doctypes import get_readable_doctypes

		return get_readable_doctypes()

	@cached_property
	def blocked_modules(self) -> set[str]:
		"""Module names this user has hidden, as the complement of `get_visible_modules`."""
		# Over every `Module Def`, not the address table's modules: a module with nothing
		# addressable and a blocked one are different facts.
		modules = frappe.get_all("Module Def", pluck="name")

		return set(modules) - set(get_visible_modules(modules))

	@cached_property
	def readable_modules(self) -> set[str]:
		"""The modules holding at least one doctype this user may read."""
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
		"""The `DeskViews` page set, uncached: the six-hour cache keeps a lost permission visible."""
		from frappe.desk.desk_views import DeskViews

		return set(DeskViews.get_allowed_pages())

	# The type table

	def rule(self, item_type: str | None) -> str | None:
		return self._types.get(item_type, (None, None))[0]

	def target(self, item_type: str | None) -> str | None:
		return self._types.get(item_type, (None, None))[1]

	def resolver(self, item_type: str):
		"""The `can_see` an app contributed beside its renderer, or None."""
		# Two apps claiming one type is a collision, not an ordering: the later app wins, loudly.
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
				# Every way of getting the path wrong lands here, including `get_attr`'s throw for an
				# app that is not installed; the type falls through to failing closed.
				frappe.log_error(title=f"Navigation item type {item_type} has an unusable resolver")

		return None

	@cached_property
	def _types(self) -> dict[str, tuple[str, str]]:
		"""`{type: (bucket, target_doctype)}` — what every kind declares about itself, in one query."""
		return {
			row.name: (row.permission_rule, row.target_doctype)
			for row in frappe.get_all(
				"Navigation Item Type", fields=["name", "permission_rule", "target_doctype"]
			)
		}

	# What a derived item on the rail hangs off

	@property
	def sidebars(self) -> dict[str, list[dict]] | None:
		"""This app's resolved sidebars, filtered, computed once and shared with the rail."""
		# `None` while they are being resolved: a sidebar row pointing at a sidebar would re-enter
		# this forever, and "not resolved yet" is not "resolved to nothing".
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
		"""One log row per type per resolution, naming the kind and how many items it cost."""
		# Deduped: Error Log writes are buffered, so forty items of one kind would be forty rows.
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
