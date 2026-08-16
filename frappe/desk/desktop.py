# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
# Author - Shivam Mishra <shivam@frappe.io>

from functools import wraps
from json import JSONDecodeError, dumps, loads

import frappe
from frappe import DoesNotExistError, ValidationError, _, _dict
from frappe.app_state import get_disabled_modules
from frappe.cache_manager import build_table_count_cache
from frappe.core.doctype.custom_role.custom_role import get_custom_allowed_roles
from frappe.desk.desk_views import DeskViews
from frappe.desk.doctype.custom_sidebar.custom_sidebar import check_workspace_manager
from frappe.desk.doctype.custom_workspace.custom_workspace import (
	apply_customization,
	get_customization,
)
from frappe.desk.layers import resolve_layers
from frappe.desk.utils import is_item_allowed
from frappe.utils.caching import request_cache


def handle_not_exist(fn):
	@wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except DoesNotExistError:
			frappe.clear_last_message()
			return []

	return wrapper


class Workspace(DeskViews):
	def __init__(self, page, minimal=False):
		self.page_name = page.get("name")
		self.page_title = page.get("title")
		self.public_page = page.get("public")
		self.workspace_manager = "Workspace Manager" in frappe.get_roles()

		self.user = frappe.get_user()

		# A standard workspace stays the live, app-owned base; a site's customization is a
		# separate delta merged on top here. Use a fresh (non-cached) doc on the merge path
		# so we never mutate the shared cached document.
		customization = get_customization(self.page_name)
		if customization:
			self.doc = frappe.get_doc("Workspace", self.page_name)
			apply_customization(self.doc, customization)
		else:
			self.doc = frappe.get_cached_doc("Workspace", self.page_name)

		self.can_read = self.get_cached("user_perm_can_read", self.get_can_read_items)

		if not minimal:
			if self.doc.content:
				self.onboarding_list = [
					x["data"]["onboarding_name"] for x in loads(self.doc.content) if x["type"] == "onboarding"
				]

			self.table_counts = get_table_with_counts()

	def is_permitted(self):
		"""Return true if the workspace is visible to the current user.

		Visibility is gated purely by access (module visibility / roles):

		* Its `module` must be visible to the user -- i.e. not one they have blocked.
		* Then, if the workspace has `roles`, the user must have one of them.

		The module gate runs **before** the roles branch. It used to sit inside the *no-roles*
		branch, which meant a role-gated workspace in a blocked module stayed visible -- the
		block silently did nothing for exactly the workspaces someone bothered to restrict.

		Neither dock layer -- the site's (`Dock Order`) nor the user's own (`User.dock_modules`)
		-- is an access filter. Both are arrangements, applied client-side from
		`frappe.boot.user_dock_modules`. Keeping them out of here ensures the full permitted pool
		stays available for the picker to choose from.
		"""
		from frappe.utils import has_common
		from frappe.utils.modules import is_module_visible

		if not is_module_visible(self.doc.module):
			return False

		allowed = [d.role for d in self.doc.roles]
		allowed.extend(get_custom_allowed_roles("page", self.doc.name))

		if not allowed:
			return True

		if has_common(frappe.get_roles(), allowed):
			return True

	def get_cached(self, cache_key, fallback_fn):
		value = frappe.cache.get_value(cache_key, user=frappe.session.user)
		if value is not None:
			return value

		value = fallback_fn()

		# Expire every six hour
		frappe.cache.set_value(cache_key, value, frappe.session.user, 21600)
		return value

	def get_can_read_items(self):
		if not self.user.can_read:
			self.user.build_permissions()

		return self.user.can_read

	def get_allowed_modules(self):
		if not self.user.allow_modules:
			self.user.build_permissions()

		return self.user.allow_modules

	def get_onboarding_doc(self, onboarding):
		# Check if onboarding is enabled
		if not frappe.get_system_settings("enable_onboarding"):
			return None

		if not self.onboarding_list:
			return None

		if frappe.db.get_value("Module Onboarding", onboarding, "is_complete"):
			return None

		doc = frappe.get_doc("Module Onboarding", onboarding)

		# Check if user is allowed
		allowed_roles = set(doc.get_allowed_roles())
		user_roles = set(frappe.get_roles())
		if not allowed_roles & user_roles:
			return None

		# Check if already complete
		if doc.check_completion():
			return None

		return doc

	def build_workspace(self):
		self.cards = {"items": self.get_links()}
		self.charts = {"items": self.get_charts()}
		self.shortcuts = {"items": self.get_shortcuts()}
		self.onboardings = {"items": []}
		self.quick_lists = {"items": self.get_quick_lists()}
		self.number_cards = {"items": self.get_number_cards()}
		self.custom_blocks = {"items": self.get_custom_blocks()}

	def _doctype_contains_a_record(self, name):
		exists = self.table_counts.get(name, False)

		if not exists and frappe.db.exists(name):
			if not frappe.db.get_value("DocType", name, "issingle"):
				exists = bool(frappe.get_all(name, limit=1))
			else:
				exists = True
			self.table_counts[name] = exists

		return exists

	def _prepare_item(self, item):
		if item.dependencies:
			dependencies = [dep.strip() for dep in item.dependencies.split(",")]

			incomplete_dependencies = [d for d in dependencies if not self._doctype_contains_a_record(d)]

			if len(incomplete_dependencies):
				item.incomplete_dependencies = incomplete_dependencies
			else:
				item.incomplete_dependencies = ""

		if item.onboard:
			# Mark Spotlights for initial
			if item.get("type") == "doctype":
				name = item.get("name")
				count = self._doctype_contains_a_record(name)

				item["count"] = count

		if item.get("link_type") == "DocType":
			item["description"] = frappe.get_meta(item.link_to).description

		# Translate label
		item["label"] = _(item.label) if item.label else _(item.name)

		return item

	def is_custom_block_permitted(self, custom_block_name):
		from frappe.utils import has_common

		allowed = [
			d.role for d in frappe.get_all("Has Role", fields=["role"], filters={"parent": custom_block_name})
		]

		if not allowed:
			return True

		roles = frappe.get_roles()

		if has_common(roles, allowed):
			return True

		return False

	@handle_not_exist
	def get_links(self):
		cards = self.doc.get_link_groups()

		if not self.doc.hide_custom:
			cards = cards + get_custom_reports_and_doctypes(self.doc.module)

		default_country = frappe.db.get_default("country")

		new_data = []
		for card in cards:
			new_items = []
			card = _dict(card)

			links = card.get("links", [])

			for item in links:
				item = _dict(item)

				# Condition: based on country
				if item.country and item.country != default_country:
					continue

				# Check if user is allowed to view
				if is_item_allowed(item.link_to, item.link_type, self):
					prepared_item = self._prepare_item(item)
					new_items.append(prepared_item)

			if new_items:
				if isinstance(card, _dict):
					new_card = card.copy()
				else:
					new_card = card.as_dict().copy()
				new_card["links"] = new_items
				new_card["label"] = _(new_card["label"])
				new_data.append(new_card)

		return new_data

	@handle_not_exist
	def get_charts(self):
		all_charts = []
		if frappe.has_permission("Dashboard Chart", throw=False):
			charts = self.doc.charts

			for chart in charts:
				if frappe.has_permission("Dashboard Chart", doc=chart.chart_name):
					# Translate label
					chart.label = _(chart.label) if chart.label else _(chart.chart_name)
					all_charts.append(chart)

		return all_charts

	@handle_not_exist
	def get_shortcuts(self):
		def _in_active_domains(item):
			if not item.restrict_to_domain:
				return True
			else:
				return item.restrict_to_domain in frappe.get_active_domains()

		items = []
		shortcuts = self.doc.shortcuts

		for item in shortcuts:
			new_item = item.as_dict().copy()
			if is_item_allowed(item.link_to, item.type, self) and _in_active_domains(item):
				if item.type == "Report":
					report = self.allowed_reports.get(item.link_to, {})
					if report.get("report_type") in ["Query Report", "Script Report", "Custom Report"]:
						new_item["is_query_report"] = 1
					else:
						new_item["ref_doctype"] = report.get("ref_doctype")

				# Translate label
				new_item["label"] = _(item.label) if item.label else _(item.link_to)

				items.append(new_item)

		return items

	@handle_not_exist
	def get_quick_lists(self):
		items = []
		quick_lists = self.doc.quick_lists

		for item in quick_lists:
			if is_item_allowed(item.document_type, "doctype", self):
				new_item = item.as_dict().copy()

				# Translate label
				new_item["label"] = _(item.label) if item.label else _(item.document_type)

				items.append(new_item)

		return items

	@handle_not_exist
	def get_number_cards(self):
		all_number_cards = []
		if frappe.has_permission("Number Card", throw=False):
			number_cards = self.doc.number_cards
			for number_card in number_cards:
				if frappe.has_permission("Number Card", doc=number_card.number_card_name):
					# Translate label
					number_card.label = (
						_(number_card.label) if number_card.label else _(number_card.number_card_name)
					)
					all_number_cards.append(number_card)

		return all_number_cards

	@handle_not_exist
	def get_custom_blocks(self):
		all_custom_blocks = []
		if frappe.has_permission("Custom HTML Block", throw=False):
			custom_blocks = self.doc.custom_blocks

			for custom_block in custom_blocks:
				if frappe.has_permission("Custom HTML Block", doc=custom_block.custom_block_name):
					if not self.is_custom_block_permitted(custom_block.custom_block_name):
						continue

					# Translate label
					custom_block.label = (
						_(custom_block.label) if custom_block.label else _(custom_block.custom_block_name)
					)
					all_custom_blocks.append(custom_block)

		return all_custom_blocks


@frappe.whitelist()
@frappe.read_only()
def get_desktop_page(page: str | dict):
	"""Apply permissions, customizations and return the configuration for a page on desk.

	Args:
	        page (json): page data

	Return:
	        dict: dictionary of cards, charts and shortcuts to be displayed on website
	"""
	try:
		workspace = Workspace(frappe.parse_json(page))
		workspace.build_workspace()
		return {
			"charts": workspace.charts,
			"shortcuts": workspace.shortcuts,
			"cards": workspace.cards,
			"onboardings": workspace.onboardings,
			"quick_lists": workspace.quick_lists,
			"number_cards": workspace.number_cards,
			"custom_blocks": workspace.custom_blocks,
		}
	except DoesNotExistError:
		frappe.log_error("Workspace Missing")
		return {}


# ---------------------------------------------------------------------------------------
# The dock, in two layers
# ---------------------------------------------------------------------------------------
#
# The site's arrangement (`Dock Order`, a Workspace Manager's) and the user's own
# (`User.dock_modules`), the second applied on top of the first. Both are ordered lists of the
# same rows -- `Dock Module` -- because there is nothing to tell them apart but who they are
# stored on.
#
# Ordering and hiding only, never pinning, and never a permission gate: a module a user may not
# reach is dropped from the resolved dock regardless of what either layer says about it.
#
# The merge itself is not here: it is `frappe.desk.layers`, which the sidebar's layers resolve
# through as well. What is the dock's own is `dock_key` and `apply_dock_row` below -- the two
# things the merge asks a surface to answer for itself.


def get_dock_order() -> list[dict]:
	"""The site's arrangement (`Dock Order.modules`), in row order."""
	return _dock_rows(frappe.get_cached_doc("Dock Order").modules)


def get_dock_curation() -> list[dict]:
	"""The session user's own arrangement (`User.dock_modules`), in row order.

	What the dock manager round-trips: it replaces only the current app's slice of an
	arrangement, so it has to see the layer it is editing rather than the resolved dock, which
	carries the site's rows too and would copy them into the user's own layer on the next save.
	"""
	return _dock_rows(frappe.get_cached_doc("User", frappe.session.user).dock_modules)


def _dock_rows(rows) -> list[dict]:
	return [{"module": row.module, "hidden": int(row.hidden or 0)} for row in rows if row.module]


def get_user_dock_modules() -> list[dict]:
	"""The dock as this user sees it: the site's arrangement with their own applied on top.

	One flat list across every app -- a dock renders per app, but an arrangement is stored
	whole, so an app's slice can be replaced without disturbing the rest.

	A module neither layer names is *absent from this list*, not appended to it: the client
	keeps it in its app's default order, trailing the modules the arrangement did name. That is
	what makes installing an app safe on a site that has already ordered its dock -- the new
	app's modules appear at the end of the dock rather than vanishing for want of a row.

	Resolved through `frappe.desk.layers`, the merge the sidebar's layers run on, with no base
	arrangement under them: no app ships a dock yet, so the site's layer is the first there is.
	A module left hidden is *kept*, carrying its flag -- the dock renders a hidden entry rather
	than dropping it, which is the one thing it does differently from a sidebar.
	"""
	from frappe.utils.modules import is_module_visible

	resolved, hidden = resolve_layers(
		[], [get_dock_order(), get_dock_curation()], key=dock_key, apply_row=apply_dock_row
	)
	# Applied last, so neither layer can name its way past module visibility -- an arrangement
	# is navigation reach, and reach is decided by the module gate alone.
	return [
		{"module": row["module"], "hidden": int(hidden.get(row["module"], 0))}
		for row in resolved
		if is_module_visible(row["module"])
	]


def dock_key(entry) -> str:
	"""What a dock entry is identified by: the module it points at.

	The degenerate case of the sidebar's `item_key`. That one has two shapes because a sidebar
	row may point nowhere and needs an identity anyway; a dock entry always points somewhere, so
	a module *is* its key and nothing is stored.
	"""
	return entry["module"]


def apply_dock_row(row, entry: dict | None) -> dict:
	"""What one layer row does to the dock entry it names: it is the entry.

	Never skipped, unlike a sidebar row, because there is no base arrangement a row could name
	its way outside of -- the layers are all there is, so a module one of them names is a module
	the dock has. And nothing to override: the row carries a module and a hidden flag, and the
	flag is the merge's business rather than the entry's.
	"""
	return {"module": row["module"]}


def shape_dock_rows(modules: list | str, require_visible: bool) -> list[dict]:
	"""One saved arrangement, narrowed to rows that can be stored.

	`modules` is the whole ordered arrangement the client is showing -- the shape a Sortable
	produces -- not a delta. Rows may be `"Stock"` or `{"module": "Stock", "hidden": 1}`.

	Existence is checked separately from visibility because `is_module_visible` answers a
	different question -- an unknown module is simply "not blocked", so it passes that check
	and would then fail link validation on save.

	`require_visible` is what the two layers disagree about. A user's own arrangement is
	filtered by their visibility, so a curation can never resurface a module module permissions
	hide. The site's is not: it is written for everyone, and dropping the rows the saver
	personally cannot see would let one Workspace Manager's blocked module quietly delete the
	site's intent for it. Visibility is applied to the *resolved* dock either way.
	"""
	from frappe.utils.modules import is_module_visible

	known = set(frappe.get_all("Module Def", pluck="name"))
	shaped, seen = [], set()

	for row in frappe.parse_json(modules) or []:
		module = row.get("module") if isinstance(row, dict) else row
		hidden = int(row.get("hidden") or 0) if isinstance(row, dict) else 0
		if not module or module in seen or module not in known:
			continue
		if require_visible and not is_module_visible(module):
			continue
		seen.add(module)
		shaped.append({"module": module, "hidden": hidden})

	return shaped


@frappe.whitelist()
def save_dock_preferences(modules: list | str):
	"""Persist this user's own arrangement into `User.dock_modules`."""
	user_doc = frappe.get_doc("User", frappe.session.user)
	user_doc.dock_modules = []
	for row in shape_dock_rows(modules, require_visible=True):
		user_doc.append("dock_modules", row)

	# ignore_permissions: same reasoning as `save_workspace_preferences` -- a user arranging
	# their own dock need not hold write access to the User doctype. Only the session user's
	# own record is touched, only its `dock_modules` table, and only with modules already
	# visible to them.
	#
	# ignore_links: arranging a dock saves the whole User document, so every Link on it is
	# revalidated -- including rows this endpoint never touches. A role left behind by an
	# uninstalled app is enough to make the save fail with "Could not find Row #4: Role: ...",
	# which is a true statement about the user's roles and no reason to refuse them a dock.
	# The rows written here are checked against `Module Def` in `shape_dock_rows` already.
	user_doc.flags.ignore_links = True
	user_doc.save(ignore_permissions=True)

	return get_user_dock_modules()


@frappe.whitelist()
def save_dock_order(modules: list | str):
	"""Persist the site's arrangement into `Dock Order`, for everyone.

	The site layer's whole point: "Accounts first, for everyone" is not expressible by any
	number of per-user arrangements. A user's own arrangement still lands on top of it.
	"""
	check_workspace_manager(_("You need to be Workspace Manager to change the dock for everyone."))

	doc = frappe.get_single("Dock Order")
	doc.modules = []
	for row in shape_dock_rows(modules, require_visible=False):
		doc.append("modules", row)

	# ignore_permissions: the role check above *is* the gate, and it is the same one the
	# doctype's permissions hold -- this saves through it rather than around it.
	doc.save(ignore_permissions=True)

	return get_user_dock_modules()


# A layer's raw rows, for the editor that is about to replace them. Not the resolved dock: an
# editor saves back the whole arrangement, so it has to be shown the layer it will overwrite.
# Kept out of the boot payload because it is only wanted the moment someone opens the manager.
#
# One endpoint per layer, each carrying its own gate, like the sidebar's saves and resets -- a
# single endpoint taking "which layer" would carry the gate in a branch instead.


@frappe.whitelist()
def get_user_dock_layer() -> list[dict]:
	"""This user's own arrangement. No gate: it is theirs, and it is all they can read."""
	return get_dock_curation()


@frappe.whitelist()
def get_site_dock_layer() -> list[dict]:
	check_workspace_manager(_("You need to be Workspace Manager to see the dock's site layer."))
	return get_dock_order()


def _overlay_customization_properties(pages: list) -> bool:
	"""Apply each site customization's property facet onto the listed page dict.

	Returns whether any `sequence_id` was overridden (so the caller knows to re-sort).
	"""
	resequenced = False
	for page in pages:
		customization = get_customization(page.name)
		if not customization:
			continue
		page["is_customized"] = True
		# the frontend renders the editor.js layout from this `content`; show the site's
		# saved snapshot verbatim (get_desktop_page applies the same on the doc).
		if customization.content:
			page["content"] = customization.content
			# the layout is a snapshot, so this workspace has stopped receiving the app's
			# layout changes. The desk warns before the save that causes it, and this is
			# what tells it the warning has already been earned.
			page["is_layout_customized"] = 1
		if customization.visibility == "Hidden":
			# Hidden for regular users; like the soft `is_hidden` flag, a Workspace Manager
			# still sees it (the workspace shows an in-page "hidden" banner) so it stays
			# discoverable and manageable.
			page["is_hidden"] = 1
		elif customization.visibility == "Visible":
			page["is_hidden"] = 0
		if customization.icon:
			page["icon"] = customization.icon
		if customization.indicator_color:
			page["indicator_color"] = customization.indicator_color
		if customization.override_sequence:
			page["sequence_id"] = customization.sequence_id
			resequenced = True
	return resequenced


@request_cache
def get_workspaces():
	"""Get list of sidebar items for desk.

	Cached per-request: a single boot resolves the visible workspaces several times
	(`DeskViews.build_entities`, `get_workspaces_with_sidebar`, and the lazy
	`DeskViews.allowed_workspaces` permission context), and each pass runs a
	`get_all("Workspace")` query plus a `Workspace()` build per page. Memoising for the
	life of the request collapses those into one enumeration without leaking across
	requests (the cache clears when the request ends).
	"""

	from frappe.utils.modules import get_module_placement

	has_access = "Workspace Manager" in frappe.get_roles()

	# adding None to allowed_domains to include pages without domain restriction
	allowed_domains = [None, *frappe.get_active_domains()]

	# a disabled app stays hidden even from Workspace Managers
	disabled_modules = list(get_disabled_modules())

	filters = {
		"restrict_to_domain": ["in", allowed_domains],
	}

	if has_access:
		filters = {}

	if disabled_modules:
		filters["module"] = ["not in", disabled_modules]

	# pages sorted based on sequence id
	order_by = "sequence_id asc"
	fields = [
		"name",
		"title",
		"for_user",
		"parent_page",
		"content",
		"public",
		"module",
		"icon",
		"indicator_color",
		"is_hidden",
		"sequence_id",
		"standard",
		"type",
		"link_type",
		"link_to",
		"external_link",
	]
	all_pages = frappe.get_all(
		"Workspace", fields=fields, filters=filters, order_by=order_by, ignore_permissions=True
	)

	# overlay the property facet (visibility / icon / colour / position) of any site
	# customization before filtering & sorting; roles & content are merged inside Workspace().
	if _overlay_customization_properties(all_pages):
		all_pages.sort(key=lambda page: page.get("sequence_id") or 0)

	pages = []
	private_pages = []

	# Filter Page based on Permission
	for page in all_pages:
		try:
			workspace = Workspace(page, True)
			if has_access or workspace.is_permitted():
				if page.public and (has_access or not page.is_hidden) and page.title != "Welcome Workspace":
					pages.append(page)
				elif page.for_user == frappe.session.user:
					private_pages.append(page)
				elif not page.public and not page.for_user:
					pages.append(page)
				page["label"] = _(page.get("name"))

			# Derived, never stored: there is no `Workspace.app` any more, so the module is the
			# only answer to which app a workspace belongs to. `None` for a module no app lists,
			# which a site's own module is entitled to be -- resolving this through
			# `get_module_app` threw for exactly those modules, and the throw escaped the
			# `PermissionError` handler below with it.
			page["app"] = get_module_placement(page["module"]) if page["module"] else None
			if page["link_type"] == "Report":
				report_type, ref_doctype = frappe.db.get_value(
					"Report", page["link_to"], ["report_type", "ref_doctype"]
				)
				page["report"] = {
					"report_type": report_type,
					"ref_doctype": ref_doctype,
				}

		except frappe.PermissionError:
			pass
	if private_pages:
		pages.extend(private_pages)

	if len(pages) == 0:
		welcome_workspace = next((x for x in all_pages if x["title"] == "Welcome Workspace"), None)
		if welcome_workspace:
			pages.append(welcome_workspace)

	return {
		"pages": pages,
		"has_access": has_access,
		"has_create_access": frappe.has_permission(doctype="Workspace", ptype="create"),
	}


def get_table_with_counts():
	counts = frappe.cache.get_value("information_schema:counts")
	if not counts:
		counts = build_table_count_cache()

	return counts


def get_custom_reports_and_doctypes(module):
	return [
		_dict({"label": _("Custom Documents"), "links": get_custom_doctype_list(module)}),
		_dict({"label": _("Custom Reports"), "links": get_custom_report_list(module)}),
	]


def get_custom_doctype_list(module):
	doctypes = frappe.get_all(
		"DocType",
		fields=["name"],
		filters={"custom": 1, "istable": 0, "module": module},
		order_by="name",
	)

	return [
		{
			"type": "Link",
			"link_type": "doctype",
			"link_to": d.name,
			"label": _(d.name),
		}
		for d in doctypes
	]


def get_custom_report_list(module):
	"""Return list on new style reports for modules."""
	reports = frappe.get_all(
		"Report",
		fields=["name", "ref_doctype", "report_type"],
		filters={"is_standard": "No", "disabled": 0, "module": module},
		order_by="name",
	)

	return [
		{
			"type": "Link",
			"link_type": "report",
			"doctype": r.ref_doctype,
			"dependencies": r.ref_doctype,
			"is_query_report": 1
			if r.report_type in ("Query Report", "Script Report", "Custom Report")
			else 0,
			"label": _(r.name),
			"link_to": r.name,
			"report_ref_doctype": r.ref_doctype,
		}
		for r in reports
	]


def save_new_widget(doc, page, blocks, new_widgets):
	widgets = _dict()
	if new_widgets:
		widgets = _dict(frappe.parse_json(new_widgets))

		if widgets.chart:
			doc.charts.extend(new_widget(widgets.chart, "Workspace Chart", "charts"))
		if widgets.shortcut:
			doc.shortcuts.extend(new_widget(widgets.shortcut, "Workspace Shortcut", "shortcuts"))
		if widgets.quick_list:
			doc.quick_lists.extend(new_widget(widgets.quick_list, "Workspace Quick List", "quick_lists"))
		if widgets.custom_block:
			doc.custom_blocks.extend(
				new_widget(widgets.custom_block, "Workspace Custom Block", "custom_blocks")
			)
		if widgets.number_card:
			doc.number_cards.extend(new_widget(widgets.number_card, "Workspace Number Card", "number_cards"))
		if widgets.card:
			doc.build_links_table_from_card(widgets.card)

	# remove duplicate and unwanted widgets
	clean_up(doc, blocks)

	try:
		doc.save(ignore_permissions=True)
	except (ValidationError, TypeError) as e:
		# Create a json string to log
		json_config = widgets and dumps(widgets, sort_keys=True, indent=4)

		# Error log body
		log = f"""
		page: {page}
		config: {json_config}
		exception: {e}
		"""
		doc.log_error("Could not save customization", log)
		raise

	return True


def clean_up(original_page, blocks):
	page_widgets = {}

	for wid in ["shortcut", "card", "chart", "quick_list", "number_card", "custom_block"]:
		# get list of widget's name from blocks
		page_widgets[wid] = [x["data"][wid + "_name"] for x in loads(blocks) if x["type"] == wid]

	# shortcut, chart, quick_list, number_card & custom_block cleanup
	for wid in ["shortcut", "chart", "quick_list", "number_card", "custom_block"]:
		updated_widgets = []
		original_page.get(wid + "s").reverse()

		for w in original_page.get(wid + "s"):
			if w.label in page_widgets[wid] and w.label not in [x.label for x in updated_widgets]:
				updated_widgets.append(w)
		original_page.set(wid + "s", updated_widgets)

	# card cleanup
	for i, v in enumerate(original_page.links):
		if v.type == "Card Break" and v.label not in page_widgets["card"]:
			del original_page.links[i : i + v.link_count + 1]


def new_widget(config, doctype, parentfield):
	if not config:
		return []
	prepare_widget_list = []
	for idx, widget in enumerate(config):
		# Some cleanup
		widget.pop("name", None)

		# New Doc
		doc = frappe.new_doc(doctype)
		doc.update(widget)

		# Manually Set IDX
		doc.idx = idx + 1

		# Set Parent Field
		doc.parentfield = parentfield

		prepare_widget_list.append(doc)
	return prepare_widget_list


def prepare_widget(config, doctype, parentfield):
	"""Create widget child table entries with parent details.

	Args:
	        config (dict): Dictionary containing widget config
	        doctype (string): Doctype name of the child table
	        parentfield (string): Parent field for the child table

	Return:
	        TYPE: List of Document objects
	"""
	if not config:
		return []
	order = config.get("order")
	widgets = config.get("widgets")
	prepare_widget_list = []
	for idx, name in enumerate(order):
		wid_config = widgets[name].copy()
		# Some cleanup
		wid_config.pop("name", None)

		# New Doc
		doc = frappe.new_doc(doctype)
		doc.update(wid_config)

		# Manually Set IDX
		doc.idx = idx + 1

		# Set Parent Field
		doc.parentfield = parentfield

		prepare_widget_list.append(doc)
	return prepare_widget_list


@frappe.whitelist()
def update_onboarding_step(name: str | int, field: str, value: int | str):
	"""Update status of onboaridng step

	Args:
	        name (string): Name of the doc
	        field (string): field to be updated
	        value: Value to be updated

	"""
	from frappe.utils.telemetry import capture

	allowed_fields = ["is_skipped", "is_complete"]
	if field not in allowed_fields:
		return
	frappe.db.set_value("Onboarding Step", name, field, value)

	capture(frappe.scrub(name), app="frappe_onboarding", properties={field: value})


@frappe.whitelist()
def get_installed_apps():
	return frappe.get_active_apps()


@frappe.whitelist()
@frappe.read_only()
def get_onboarding_data(module: str):
	"""Get onboarding data for a page

	Args:
	        page (string): page name

	Return:
	        dict: onboarding data
	"""
	if not frappe.get_system_settings("enable_onboarding"):
		return []

	onboardings = []
	onboarding_doc = frappe.get_doc("Module Onboarding", module)
	if onboarding_doc.is_complete:
		return []

	# Check if user is allowed
	allowed_roles = set(onboarding_doc.get_allowed_roles())
	user_roles = set(frappe.get_roles())
	if not allowed_roles & user_roles:
		return None

	item = {
		"label": _(module),
		"title": _(onboarding_doc.title),
		"items": [],
	}

	maps = get_onboarding_step_maps(onboarding_doc.name)
	for step in maps:
		steps = frappe.get_all("Onboarding Step", filters={"name": step}, order_by="idx", fields=["*"])

		if steps:
			item["items"].append(steps[0])

	onboardings.append(item)

	if all(step.get("is_complete") or step.get("is_skipped") for step in item["items"]):
		return []

	return onboardings


def get_onboarding_step_maps(onboarding):
	return frappe.get_all("Onboarding Step Map", filters={"parent": onboarding}, pluck="step", order_by="idx")
