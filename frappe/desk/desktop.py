# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
# Author - Shivam Mishra <shivam@frappe.io>

import os
from functools import wraps
from json import JSONDecodeError, dumps, loads

import frappe
from frappe import DoesNotExistError, ValidationError, _, _dict
from frappe.app_state import get_disabled_modules
from frappe.cache_manager import build_table_count_cache
from frappe.core.doctype.custom_role.custom_role import get_custom_allowed_roles
from frappe.desk.desk_views import DeskViews
from frappe.desk.doctype.custom_workspace.custom_workspace import (
	apply_customization,
	effective_renderer,
	get_customization,
	replace_widgets,
)
from frappe.desk.doctype.workspace_variant.workspace_variant import DEFAULT_LAYOUT
from frappe.desk.utils import is_item_allowed
from frappe.permissions import AUTOMATIC_ROLES
from frappe.utils import cint
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
		self.variant = None

		# A standard workspace stays the live, app-owned base; a site's customization is a
		# separate delta merged on top here. Use a fresh (non-cached) doc on the merge path
		# so we never mutate the shared cached document.
		customization = get_customization(self.page_name)
		self.doc_is_shared = not customization
		if customization:
			self.doc = frappe.get_doc("Workspace", self.page_name)
			apply_customization(self.doc, customization)
		else:
			self.doc = frappe.get_cached_doc("Workspace", self.page_name)

		self.can_read = self.get_cached("user_perm_can_read", self.get_can_read_items)
		self.onboarding_list = []

		if not minimal:
			self.onboarding_list = self.get_onboarding_names()

			self.table_counts = get_table_with_counts()

	def is_permitted(self):
		"""Return true if the workspace is visible to the current user.

		Visibility is gated purely by access (module visibility / roles):

		1. Its `module` must be visible to the user, meaning not one they have blocked.
		2. Then, if the workspace has `roles`, the user must have one of them.

		The module check runs before the roles branch. It used to sit inside the no-roles branch,
		so a role-gated workspace in a blocked module stayed visible and the block did nothing for
		exactly the workspaces someone had restricted.

		No dock layer is an access filter, whether the app's fragment, the site's arrangement or a
		user's own. All three are arrangements, applied on the client from `frappe.boot.dock`.
		Keeping them out of here keeps the full permitted pool available for the picker.
		"""
		from frappe.utils import has_common
		from frappe.utils.modules import is_module_visible

		# A page you made yourself is yours whatever its module. Blocking a module hides a product's
		# navigation, and it used to hide the user's own private pages with it: a page filed under
		# Accounts vanished for its own owner if they had Accounts blocked, from their private shell
		# as well as from the Accounts sidebar, and the desk offered no way to get it back.
		if self.doc.for_user and self.doc.for_user == frappe.session.user:
			return True

		if not is_module_visible(self.doc.module):
			return False

		allowed = [d.role for d in self.doc.roles]
		allowed.extend(get_custom_allowed_roles("page", self.doc.name))

		if not allowed:
			return True

		if has_common(frappe.get_roles(), allowed):
			return True

	def get_onboarding_names(self):
		if not self.doc.content:
			return []
		return [x["data"]["onboarding_name"] for x in loads(self.doc.content) if x["type"] == "onboarding"]

	def use_layout(self, requested: str | None = None) -> None:
		"""Draw the first role layout, in the app's order, whose role the session holds.

		`requested` names a layout to draw instead: a role, or `DEFAULT_LAYOUT`. A private
		workspace has one layout and never walks.
		"""
		if not self.doc.public:
			return

		rows = {row.role: row for row in self.doc.get("variants") or []}
		# app import skips validate, so a hand-edited JSON may still bind an automatic role
		for role in AUTOMATIC_ROLES:
			rows.pop(role, None)

		if requested:
			role = requested if requested in rows else None
		else:
			roles = set(frappe.get_roles())
			role = next((role for role in rows if role in roles), None)
		if not role:
			return

		if self.doc_is_shared:
			self.doc = frappe.get_doc("Workspace", self.page_name)
		self.doc.content = rows[role].content or "[]"
		replace_widgets(self.doc, loads(rows[role].widgets or "{}"))
		self.onboarding_list = self.get_onboarding_names()
		self.variant = role

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

		# a block can outlive the onboarding it names; that hides the block, not the workspace
		is_complete = frappe.db.get_value("Module Onboarding", onboarding, "is_complete")
		if is_complete is None or is_complete:
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

	def get_onboardings(self):
		from frappe.desk.doctype.onboarding_step.onboarding_step import get_step_details

		onboardings = []
		for name in self.onboarding_list:
			doc = self.get_onboarding_doc(name)
			if doc:
				onboardings.append(
					{
						"label": name,
						"title": _(doc.title),
						"items": [get_step_details(row.step, row.is_optional) for row in doc.steps],
					}
				)
		return onboardings

	def build_workspace(self):
		self.cards = {"items": self.get_links()}
		self.charts = {"items": self.get_charts()}
		self.shortcuts = {"items": self.get_shortcuts()}
		self.onboardings = {"items": self.get_onboardings()}
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


WIDGET_FIELDS = {
	"chart": ("charts", ("label", "chart_name")),
	"number_card": ("number_cards", ("label", "number_card_name")),
	"shortcut": (
		"shortcuts",
		(
			"label",
			"type",
			"link_to",
			"doc_view",
			"icon",
			"color",
			"format",
			"stats_filter",
			"url",
			"kanban_board",
			"report_ref_doctype",
			"is_query_report",
			"ref_doctype",
		),
	),
	"card": ("cards", ("label", "icon", "description", "links")),
	"quick_list": ("quick_lists", ("label", "document_type", "quick_list_filter", "order_by")),
	"custom_block": ("custom_blocks", ("label", "custom_block_name")),
	"onboarding": ("onboardings", ("name", "title", "is_complete", "steps")),
}

LINK_FIELDS = (
	"label",
	"type",
	"link_type",
	"link_to",
	"doctype_layout",
	"is_query_report",
	"report_ref_doctype",
	"onboard",
	"description",
	"dependencies",
	"incomplete_dependencies",
	"count",
)


@frappe.whitelist(methods=["GET"])
@frappe.read_only()
def get_workspace(name: str, variant: str | None = None) -> dict:
	"""Everything the workspace island draws, filtered to what the session user may read.

	`variant` asks for one layout, a role or `DEFAULT_LAYOUT`, and only an editor gets it.
	"""
	module = frappe.db.get_value("Workspace", name, "module")
	if module is None or module in get_disabled_modules():
		raise frappe.DoesNotExistError(_("Workspace {0} not found").format(name))

	from frappe.desk.doctype.workspace.workspace import can_edit_workspace

	workspace = Workspace({"name": name})
	doc = workspace.doc
	if doc.for_user:
		permitted = doc.for_user == frappe.session.user
	else:
		permitted = workspace.is_permitted()
	if not permitted:
		raise frappe.PermissionError(_("You are not permitted to open this workspace"))

	can_edit = can_edit_workspace(doc)
	workspace.use_layout(variant if can_edit else None)
	doc = workspace.doc
	widgets = readable_widgets(workspace)
	_fold_chart_settings(widgets["charts"])
	_load_custom_blocks(widgets["custom_blocks"])
	for card in widgets["cards"].values():
		card["links"] = [{field: link.get(field) for field in LINK_FIELDS} for link in card["links"]]

	content = loads(doc.content or "[]")
	content = [block for block in content if is_drawable(block, widgets)]
	customization = get_customization(name) if doc.standard else None

	return {
		"name": doc.name,
		"title": _(doc.title),
		"public": bool(doc.public),
		"variant": workspace.variant,
		"content": content,
		"widgets": widgets,
		"can_edit": can_edit,
		"is_hidden": bool(doc.is_hidden),
		"standard": bool(doc.standard),
		"is_layout_customized": is_layout_customized(customization, workspace.variant),
		**(editor_context(doc, customization) if can_edit else {}),
	}


def editor_context(doc, customization) -> dict:
	"""What the editor shows about where a save goes: the layouts, and the file or site copy."""
	from frappe.desk.doctype.workspace.workspace import get_workspace_app

	if not doc.public:
		return {"layouts": [], "save_target": "private"}

	base = frappe.get_cached_doc("Workspace", doc.name)
	if not base.standard:
		layouts = [{"role": None, "source": "Site"}]
		layouts += [{"role": row.role, "source": "Site"} for row in base.variants]
		return {"layouts": layouts, "save_target": "site"}

	app = get_workspace_app(base)
	app_title = (frappe.get_hooks("app_title", app_name=app) or [app])[0] if app else _("App")
	site_roles = [row.role for row in customization.variants] if customization else []
	app_roles = [row.role for row in base.variants]

	layouts = [
		{"role": None, "source": "Site copy" if customization and customization.content else app_title}
	]
	layouts += [{"role": r, "source": "Site copy" if r in site_roles else app_title} for r in app_roles]
	layouts += [{"role": r, "source": "Site"} for r in site_roles if r not in app_roles]

	if frappe.conf.developer_mode:
		scrubbed = frappe.scrub(base.name)
		path = os.path.join(frappe.get_module_path(base.module), "workspace", scrubbed, f"{scrubbed}.json")
		return {"layouts": layouts, "save_target": os.path.relpath(path, frappe.get_app_source_path(app))}
	return {"layouts": layouts, "save_target": "site copy"}


def readable_widgets(workspace) -> dict:
	"""The drawn layout's widgets the session user may read, keyed by widget table and label."""
	workspace.build_workspace()
	built = {
		"chart": workspace.charts["items"],
		"number_card": workspace.number_cards["items"],
		"shortcut": workspace.shortcuts["items"],
		"card": workspace.cards["items"],
		"quick_list": workspace.quick_lists["items"],
		"custom_block": workspace.custom_blocks["items"],
		"onboarding": [
			{"name": o["label"], "title": o["title"], "is_complete": 0, "steps": o["items"]}
			for o in workspace.onboardings["items"]
		],
	}

	widgets = {key: {} for key, _fields in WIDGET_FIELDS.values()}
	for block in loads(workspace.doc.content or "[]"):
		block_type = block.get("type")
		if block_type not in WIDGET_FIELDS:
			continue
		block_name = (block.get("data") or {}).get(f"{block_type}_name")
		item = _find_widget(built[block_type], block_type, block_name)
		if item is not None:
			key, fields = WIDGET_FIELDS[block_type]
			widgets[key][block_name] = {field: item.get(field) for field in fields}
	return widgets


def is_layout_customized(customization, variant: str | None) -> bool:
	"""Whether the layout drawn is the site's copy rather than the app's."""
	if not customization:
		return False
	if variant:
		return variant in {row.role for row in customization.variants}
	return bool(customization.content)


def _find_widget(items: list, block_type: str, block_name: str | None):
	# labels come back translated from the builder, so match the way legacy does
	if not block_name:
		return None
	if block_type == "onboarding":
		return next((item for item in items if item["name"] == block_name), None)
	label = _(block_name)
	return next((item for item in items if item.get("label") == label), None)


def is_drawable(block: dict, widgets: dict) -> bool:
	block_type = block.get("type")
	if block_type not in WIDGET_FIELDS:
		return True
	key, _fields = WIDGET_FIELDS[block_type]
	return (block.get("data") or {}).get(f"{block_type}_name") in widgets[key]


def _fold_chart_settings(charts: dict) -> None:
	if not charts:
		return
	config = frappe.db.get_value("Dashboard Settings", frappe.session.user, "chart_config")
	config = frappe.parse_json(config) or {}
	for chart in charts.values():
		chart["chart_settings"] = config.get(chart["chart_name"]) or {}


def _load_custom_blocks(blocks: dict) -> None:
	if not blocks:
		return
	names = [block["custom_block_name"] for block in blocks.values()]
	records = {
		r.name: r
		for r in frappe.get_all(
			"Custom HTML Block",
			filters={"name": ("in", names)},
			fields=["name", "html", "style", "script"],
			ignore_permissions=True,
		)
	}
	for block in blocks.values():
		record = records.get(block["custom_block_name"]) or {}
		block.update(html=record.get("html"), style=record.get("style"), script=record.get("script"))


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
		page["renderer"] = effective_renderer(page.renderer, customization)
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
		"renderer",
	]
	all_pages = frappe.get_all(
		"Workspace", fields=fields, filters=filters, order_by=order_by, ignore_permissions=True
	)

	# overlay the property facet (visibility / icon / colour / position) of any site
	# customization before filtering & sorting; roles & content are merged inside Workspace().
	if _overlay_customization_properties(all_pages):
		all_pages.sort(key=lambda page: page.get("sequence_id") or 0)

	for page in all_pages:
		if page.renderer != "Legacy":
			del page["content"]

	pages = []
	private_pages = []

	# Filter Page based on Permission
	for page in all_pages:
		try:
			workspace = Workspace(page, True)
			if has_access or workspace.is_permitted():
				if page.public and (has_access or not page.is_hidden):
					pages.append(page)
				elif page.for_user == frappe.session.user:
					private_pages.append(page)
				elif not page.public and not page.for_user:
					pages.append(page)
				page["label"] = _(page.get("name"))

			# Derived, never stored: there is no `Workspace.app` any more, so the module decides
			# which app a workspace belongs to. It is `None` for a module no app lists, which a
			# site's own module may be. Resolving this through `get_module_app` threw for exactly
			# those modules, and the exception escaped the `PermissionError` handler below.
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


# (doctype, field naming the user, field naming the document doctype, its name field, action, filters)
ACTIVITY_SOURCES = (
	(
		"Communication",
		"owner",
		"reference_doctype",
		"reference_name",
		"Replied",
		{"sent_or_received": "Sent"},
	),
	(
		"Comment",
		"comment_email",
		"reference_doctype",
		"reference_name",
		"Commented",
		{"comment_type": "Comment"},
	),
	("Version", "owner", "ref_doctype", "docname", "Updated", {}),
	("View Log", "viewed_by", "reference_doctype", "reference_name", "Viewed", {}),
	("ToDo", "assigned_by", "reference_type", "reference_name", "Assigned", {}),
)
RECENT_ACTIVITY_DAYS = 30


@frappe.whitelist(methods=["GET"])
@frappe.read_only()
def get_recent_activity(
	doctype: str, filters: str | dict | list | None = None, limit: int = 20
) -> list[dict]:
	"""The session user's newest action in the last 30 days on each document of `doctype` that
	`filters` match and the user may read, newest first. An edit counts only when it changed a
	field the list view shows or filters on."""
	limit = min(cint(limit) or 20, 100)
	since = frappe.utils.add_days(frappe.utils.now_datetime(), -RECENT_ACTIVITY_DAYS)
	reported = [
		df
		for df in frappe.get_meta(doctype).fields
		if (df.in_list_view or df.in_standard_filter) and not df.permlevel
	]

	latest = {}
	for source, user_field, doctype_field, name_field, action, extra in ACTIVITY_SOURCES:
		fields = [f"{name_field} as name", "creation"]
		if source == "Version":
			fields.append("data")
		for row in frappe.get_all(
			source,
			filters={
				**extra,
				user_field: frappe.session.user,
				doctype_field: doctype,
				"creation": (">=", since),
			},
			fields=fields,
			order_by="creation desc",
			limit=limit * 5,
		):
			text = _change_text(reported, row.data) if source == "Version" else None
			if source == "Version" and not text:
				continue
			if row.name and (row.name not in latest or row.creation > latest[row.name].creation):
				latest[row.name] = _dict(name=row.name, creation=row.creation, action=_(action), text=text)

	if not latest:
		return []

	filters = frappe.parse_json(filters) or []
	if isinstance(filters, dict):
		filters = [
			[doctype, field, *(value if isinstance(value, list) else ["=", value])]
			for field, value in filters.items()
		]
	readable = set(
		frappe.get_list(
			doctype, filters=[*filters, [doctype, "name", "in", list(latest)]], pluck="name", limit=0
		)
	)
	return sorted(
		(event for name, event in latest.items() if name in readable),
		key=lambda event: event.creation,
		reverse=True,
	)[:limit]


def _change_text(reported: list, data: str | None) -> str | None:
	"""The first of `reported` fields a Version changed, as 'Set Status to Closed'."""
	try:
		changed = {field: new for field, _old, new in (loads(data).get("changed") or [])}
	except (JSONDecodeError, TypeError, ValueError):
		return None

	for df in reported:
		if df.fieldname in changed:
			return _("Set {0} to {1}").format(_(df.label), changed[df.fieldname])


@frappe.whitelist()
def update_onboarding_step(name: str | int, field: str, value: int | str):
	"""Update status of onboaridng step

	Args:
	        name (string): Name of the doc
	        field (string): field to be updated
	        value: Value to be updated

	"""
	from frappe.desk.doctype.module_onboarding.module_onboarding import (
		can_update_step,
		capture_step_update,
		update_completion,
	)

	allowed_fields = ["is_skipped", "is_complete"]
	if field not in allowed_fields:
		return

	if not can_update_step(name):
		frappe.throw(_("You are not allowed to update this onboarding step"), frappe.PermissionError)

	if field == "is_complete" and cint(value):
		frappe.get_doc("Onboarding Step", name).throw_if_unfinished()

	frappe.db.set_value("Onboarding Step", name, field, cint(value))
	capture_step_update(name, field, cint(value))
	update_completion(name)


@frappe.whitelist()
def get_installed_apps():
	frappe.permissions.validate_desk_user()
	return frappe.get_active_apps()
