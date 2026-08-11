# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
bootstrap client session
"""

import os

import frappe
import frappe.defaults
import frappe.desk.desk_page
from frappe.app_state import filter_out_disabled_doctypes, get_disabled_modules
from frappe.core.doctype.custom_icon.custom_icon import get_symbols
from frappe.core.doctype.installed_applications.installed_applications import (
	get_setup_wizard_completed_apps,
)
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo, get_navbar_settings
from frappe.core.doctype.permission_type.permission_type import get_doctype_ptype_map
from frappe.desk.desk_views import DeskViews
from frappe.desk.doctype.desktop_settings.desktop_settings import get_desktop_page, is_desktop_icons_page
from frappe.desk.doctype.form_tour.form_tour import get_onboarding_ui_tours
from frappe.desk.doctype.route_history.route_history import frequently_visited_links
from frappe.desk.form.load import get_meta_bundle
from frappe.desk.page.setup_wizard.setup_wizard import get_setup_wizard_url
from frappe.desk.utils import is_item_allowed
from frappe.email.inbox import get_email_accounts
from frappe.integrations.frappe_providers.cloud_settings import (
	get_boot_context as get_cloud_settings_boot_context,
)
from frappe.integrations.frappe_providers.frappecloud_billing import current_site_info, is_fc_site
from frappe.model.base_document import get_controller
from frappe.utils import add_user_info, get_system_timezone
from frappe.utils.caching import redis_cache
from frappe.utils.change_log import get_versions
from frappe.website.doctype.web_page_view.web_page_view import is_tracking_enabled


def get_bootinfo():
	"""build and return boot info"""
	from frappe.translate import get_lang_dict, get_translated_doctypes

	frappe.set_user_lang(frappe.session.user)
	bootinfo = frappe._dict()
	hooks = frappe.get_hooks()
	doclist = []

	# user
	get_user(bootinfo)
	# desktop icon info

	# system info
	bootinfo.sitename = frappe.local.site
	bootinfo.sysdefaults = frappe.defaults.get_defaults()
	bootinfo.sysdefaults["setup_complete"] = frappe.is_setup_complete()
	if not bootinfo.sysdefaults["setup_complete"]:
		bootinfo.setup_wizard_url = get_setup_wizard_url()

	bootinfo.server_date = frappe.utils.nowdate()

	if frappe.session["user"] != "Guest":
		bootinfo.user_info = get_user_info()

	desk_views = DeskViews()
	desk_views.build_entities()
	desk_views.add_to_boot(bootinfo)
	load_desktop_data(bootinfo)
	bootinfo.letter_heads = get_letter_heads()
	bootinfo.active_domains = frappe.get_active_domains()
	bootinfo.all_domains = frappe.get_all("Domain", pluck="name")
	add_layouts(bootinfo)

	# module_app is keyed by scrubbed module name
	disabled_modules = {frappe.scrub(module) for module in get_disabled_modules()}
	bootinfo.module_app = {
		module: app for module, app in frappe.local.module_app.items() if module not in disabled_modules
	}
	bootinfo.single_types = filter_out_disabled_doctypes(
		frappe.get_all("DocType", {"issingle": 1}, pluck="name")
	)
	bootinfo.nested_set_doctypes = filter_out_disabled_doctypes(
		frappe.get_all("DocField", {"fieldname": "lft"}, pluck="parent")
	)
	bootinfo.tree_view_doctypes = get_tree_view_doctypes()
	add_home_page(bootinfo, doclist)
	load_translations(bootinfo)
	add_timezone_info(bootinfo)
	load_conf_settings(bootinfo)
	load_print(bootinfo, doclist)
	doclist.extend(get_meta_bundle("Page"))
	bootinfo.home_folder = frappe.db.get_value("File", {"is_home_folder": 1})
	bootinfo.navbar_settings = get_navbar_settings()
	bootinfo.notification_settings = get_notification_settings()
	bootinfo.notification_unread_count = frappe.db.count(
		"Notification Log", {"read": 0, "for_user": frappe.session.user}
	)
	bootinfo.onboarding_tours = get_onboarding_ui_tours()
	set_time_zone(bootinfo)

	# ipinfo
	if frappe.session.data.get("ipinfo"):
		bootinfo.ipinfo = frappe.session["data"]["ipinfo"]

	# add docs
	bootinfo.docs = doclist
	load_country_doc(bootinfo)
	load_currency_docs(bootinfo)

	for method in hooks.boot_session or []:
		frappe.get_attr(method)(bootinfo)

	if bootinfo.lang:
		bootinfo.lang = str(bootinfo.lang)
	bootinfo.versions = {k: v["version"] for k, v in get_versions().items()}

	bootinfo.error_report_email = frappe.conf.error_report_email
	bootinfo.calendars = sorted(frappe.get_hooks("calendars"))
	bootinfo.treeviews = frappe.get_hooks("treeviews") or []
	bootinfo.has_awesomebar_search = bool(hooks.awesomebar_search)
	bootinfo.lang_dict = get_lang_dict()
	bootinfo.success_action = get_success_action()
	bootinfo.update(get_email_accounts(user=frappe.session.user))
	bootinfo.sms_gateway_enabled = bool(frappe.db.get_single_value("SMS Settings", "sms_gateway_url"))
	bootinfo.frequently_visited_links = frequently_visited_links()
	bootinfo.link_preview_doctypes = get_link_preview_doctypes()
	bootinfo.additional_filters_config = get_additional_filters_from_hooks()
	bootinfo.desk_settings = get_desk_settings()
	bootinfo.app_logo_url = get_app_logo()
	bootinfo.link_title_doctypes = get_link_title_doctypes()
	bootinfo.translated_doctypes = get_translated_doctypes()
	bootinfo.doctype_ptype_map = get_doctype_ptype_map()
	bootinfo.subscription_conf = add_subscription_conf()
	bootinfo.is_fc_site = is_fc_site()
	bootinfo.cloud_settings = get_cloud_settings_boot_context()
	bootinfo.enable_address_autocompletion = frappe.db.get_single_value(
		"Geolocation Settings", "enable_address_autocompletion"
	)

	if sentry_dsn := get_sentry_dsn():
		bootinfo.sentry_dsn = sentry_dsn

	bootinfo.json_request_apps = get_json_request_apps()
	bootinfo.setup_wizard_completed_apps = get_setup_wizard_completed_apps() or []
	bootinfo.desktop_icon_urls = get_desktop_icon_urls()
	bootinfo.desktop_icon_style = get_icon_style() or "Subtle"
	bootinfo.desktop_page = get_desktop_page()
	bootinfo.custom_icons = get_symbols()
	if bootinfo.is_fc_site:
		bootinfo.site_info = current_site_info()
	return bootinfo


def get_json_request_apps() -> list[str]:
	"""Apps that opt into native JSON request bodies via `use_json_request_body` in hooks.py.

	The frontend (`frappe.request`) uses this to decide, per call, whether to send args as a
	native `application/json` body. Apps that don't opt in keep the legacy form-encoded payload.
	"""
	return [
		app
		for app in frappe.get_installed_apps()
		if any(frappe.get_hooks("use_json_request_body", app_name=app))
	]


def get_icon_style():
	icon_style = frappe.db.get_single_value("Desktop Settings", "icon_style")
	if icon_style not in ["Subtle", "Solid"]:
		return "Solid"
	return icon_style


def get_letter_heads():
	letter_heads = {}

	if not frappe.has_permission("Letter Head"):
		return letter_heads
	for letter_head in frappe.get_list("Letter Head", fields=["name", "content", "footer"]):
		letter_heads.setdefault(
			letter_head.name, {"header": letter_head.content, "footer": letter_head.footer}
		)

	return letter_heads


def load_conf_settings(bootinfo):
	from frappe.core.api.file import get_file_chunk_size, get_max_file_size

	bootinfo.max_file_size = get_max_file_size()
	bootinfo.file_chunk_size = get_file_chunk_size()
	for key in ("developer_mode", "socketio_port", "socketio_backend", "file_watcher_port"):
		if key in frappe.conf:
			bootinfo[key] = frappe.conf.get(key)


def get_boot_module_app():
	"""`frappe.local.module_app` extended with modules that exist only in the DB.

	A Module Def created from the UI (e.g. to host a custom doctype) carries its app in
	`app_name` but never appears in any modules.txt, so `frappe.local.module_app` misses it.
	The desk uses this map to resolve a routed doctype's owning app -- which sidebar to show
	and which app's workspace rail to switch to -- so fold those modules in for the boot
	payload only. Server-side file-path resolution (`frappe.get_module_app`) intentionally
	stays modules.txt-based."""
	module_app = dict(frappe.local.module_app)
	installed_apps = set(frappe.get_installed_apps())
	for module in frappe.get_all("Module Def", fields=["name", "app_name"]):
		key = frappe.scrub(module.name)
		if key not in module_app and module.app_name in installed_apps:
			module_app[key] = module.app_name
	return module_app


def get_app_rail_map():
	"""Workspaces that companion apps pin into another app's workspace dock (the rail).

	A companion app (e.g. India Compliance for ERPNext, India Payroll for HRMS) stays off the
	apps screen and instead surfaces its workspaces inside a host app's rail via the
	`add_to_workspace_dock` hook. Each entry names the host `app` and the `workspace` to pin.
	Returns a map of host app name -> ordered list of workspace names.

	Nothing is permission-filtered here: the caller keeps only workspaces the user is allowed to
	see, so a pinned workspace is gated by its own Roles table like any other workspace."""
	rail_map = {}

	for entry in frappe.get_hooks("add_to_workspace_dock") or []:
		if not isinstance(entry, dict):
			continue

		host_app = entry.get("app")
		workspace = entry.get("workspace")
		if not host_app or not workspace:
			continue

		rail_map.setdefault(host_app, []).append(workspace)

	return rail_map


def get_app_rail_host_map():
	"""Map of companion app -> the host app it pins into via `add_to_workspace_dock`.

	A companion app has no shell of its own; its workspaces live inside the host app's rail. This
	map lets the desk resolve the app context (dock + header) of a companion app's workspaces to
	the host app, so you stay "in" the host's rail while using the companion. When a companion pins
	into more than one host, the first host wins."""
	host_map = {}
	for app_name in frappe.get_installed_apps():
		for entry in frappe.get_hooks("add_to_workspace_dock", app_name=app_name) or []:
			if isinstance(entry, dict) and entry.get("app") and entry.get("workspace"):
				host_map[app_name] = entry["app"]
				break
	return host_map


# Fallback apps-screen sort order for apps that don't declare a `sequence_id` in their
# `add_to_apps_screen` hook. Sits below Framework (1000) so it always trails real apps.
DEFAULT_APP_SEQUENCE_ID = 100


def load_desktop_data(bootinfo):
	from frappe.desk.desktop import get_user_dock_modules

	allowed_pages = [d.name for d in bootinfo.workspaces.get("pages")]
	# A companion app's workspaces resolve their app context (dock + header) to the host app they
	# were pinned into via `add_to_workspace_dock`, so the companion appears to live inside the
	# host's rail rather than flipping the desk to a shell of its own.
	bootinfo.app_rail_host = get_app_rail_host_map()
	# The user's curated workspace selection (`User.workspaces`), ordered. Kept separate from
	# `bootinfo.workspaces` (which holds every permitted workspace link) so the workspace selector
	# can prefer it when set, without it affecting the full workspace listing.
	bootinfo.user_dock_modules = get_user_dock_modules()
	# Keyed by exact-case module name, so `app_data[].modules` indexes straight in. This
	# replaced three overlapping payloads -- `workspace_sidebar_item` (keyed by lowercased
	# workspace title), `default_workspace_map` and `module_wise_workspaces` -- which between
	# them made the desk reconcile four keyspaces for one identity.
	bootinfo.module_sidebars = get_module_sidebars()
	bootinfo.entity_module = build_entity_module_map(bootinfo.module_sidebars)

	# Only the Desktop Icon grid reads these; the default Apps screen builds itself from
	# `app_data` below. Set after `module_sidebars`, which `is_icon_permitted` reads.
	if is_desktop_icons_page():
		from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons

		bootinfo.desktop_icons = get_desktop_icons(bootinfo=bootinfo)

	bootinfo.app_data = get_app_data(allowed_pages)
	# A *sibling* of `app_data`, never a member of it -- see `get_standalone_modules`.
	bootinfo.standalone_modules = get_standalone_modules(bootinfo.module_sidebars)


def get_app_data(allowed_pages: list[str]) -> list[dict]:
	"""The apps the desk knows about, each with the workspaces that belong to it.

	This is what backs the apps (desktop) screen and the workspace dock: the dock lists
	`app_data[app].workspaces` for whichever app is in context. Kept as its own function so
	anything that re-mounts a workspace can hand the client a fresh copy without duplicating
	the grouping rules (see `mount_workspace`).

	`allowed_pages` is the set of workspace names the user may see -- `bootinfo.workspaces.pages`,
	i.e. every public workspace they're permitted plus their own private ones.
	"""
	app_data = []

	# Companion apps pin their workspaces into a host app's dock (rail) via `add_to_workspace_dock`,
	# instead of taking an apps-screen slot of their own. Resolved once, merged per host app below.
	rail_map = get_app_rail_map()
	app_rail_host = get_app_rail_host_map()

	Workspace = frappe.qb.DocType("Workspace")
	Module = frappe.qb.DocType("Module Def")

	for app_name in frappe.get_active_apps():
		# get app details from app_info (/apps)
		apps = frappe.get_hooks("add_to_apps_screen", app_name=app_name)
		app_info = {}
		if apps:
			app_info = apps[0]
			has_permission = app_info.get("has_permission")
			if has_permission and not frappe.get_attr(has_permission)():
				# The user can't access this app, so we don't expose its routes, workspaces or
				# modules. We still surface its name/title so things that reference the app can be
				# labelled (e.g. the sidebar header subtitle) instead of falling back to the user's
				# name. on_apps_screen stays False so it never shows on the apps screen, and an
				# empty `workspaces` keeps the desk-side lookups from breaking.
				app_data.append(
					dict(
						on_apps_screen=False,
						sequence_id=app_info.get("sequence_id") or DEFAULT_APP_SEQUENCE_ID,
						app_name=app_info.get("name") or app_name,
						app_title=app_info.get("title")
						or (frappe.get_hooks("app_title", app_name=app_name) or [None])[0]
						or app_name,
						app_route="",
						app_logo_url=app_info.get("logo")
						or frappe.get_hooks("app_logo_url", app_name=app_name)
						or frappe.get_hooks("app_logo_url", app_name="frappe"),
						modules=[],
						workspaces=[],
					)
				)
				continue

		# A workspace belongs to this app if its module is the app's (standard, app-shipped
		# workspaces) or its `app` field points at it (custom workspaces have no module). Use a
		# left join so module-less custom workspaces aren't dropped. Ordered by `sequence_id` so
		# the dock lists them in the workspace record's configured order.
		#
		# Private workspaces are included on the same footing as public ones: a private workspace
		# mounted to an app belongs on that app's dock, and nowhere else. Restricting to the
		# session user is belt-and-braces -- `allowed_pages` already covers it, since
		# `get_workspaces()` only ever extends its page list with the user's *own* private
		# workspaces -- but it keeps the query honest on its own terms.
		workspaces = [
			r[0]
			for r in (
				frappe.qb.from_(Workspace)
				.left_join(Module)
				.on(Workspace.module == Module.name)
				.select(Workspace.name)
				.where(
					# app membership is the module's app, full stop -- `Workspace.app` was a
					# second, hand-set answer to the same question and is gone
					(Module.app_name == app_name)
					& ((Workspace.public == 1) | (Workspace.for_user == frappe.session.user))
				)
				.orderby(Workspace.sequence_id)
				.run()
			)
			if r[0] in allowed_pages
		]

		# Fold in workspaces that companion apps pinned to this app's rail (see get_app_rail_map).
		# They are permission-filtered like the app's own workspaces and de-duplicated, so the dock
		# lists them alongside the host app's without a companion app claiming an apps-screen icon.
		for rail_workspace in rail_map.get(app_name, []):
			if rail_workspace in allowed_pages and rail_workspace not in workspaces:
				workspaces.append(rail_workspace)

		app_data.append(
			dict(
				# whether the app opts into the apps screen via the add_to_apps_screen hook. An app
				# that pins into a host app's dock never takes a slot of its own, even if it still
				# declares add_to_apps_screen from before the dock existed -- the dock hook wins.
				on_apps_screen=bool(apps) and app_name not in app_rail_host,
				# Sort order for the apps (desktop) screen; lower shows first, Framework is pinned
				# last (sequence_id 1000). Apps that don't declare one fall to a middle default.
				sequence_id=app_info.get("sequence_id") or DEFAULT_APP_SEQUENCE_ID,
				app_name=app_info.get("name") or app_name,
				app_title=app_info.get("title")
				or (
					(
						frappe.get_hooks("app_title", app_name=app_name)
						and frappe.get_hooks("app_title", app_name=app_name)[0]
					)
					or ""
				)
				or app_name,
				app_route=app_info.get("route")
				or (
					frappe.get_hooks("app_home", app_name=app_name)
					and frappe.get_hooks("app_home", app_name=app_name)[0]
				)
				or (workspaces and "/desk/" + frappe.utils.slug(workspaces[0]))
				or "",
				# Only the app's own logo (from add_to_apps_screen or its app_logo_url hook); left
				# empty when it declares none, so the desk renders an alphabet icon instead.
				app_logo_url=app_info.get("logo")
				or frappe.get_hooks("app_logo_url", app_name=app_name)
				or None,
				modules=get_app_modules(app_name),
				workspaces=workspaces,
			)
		)

	return app_data


def get_app_modules(app_name: str) -> list[str]:
	"""The app's modules the user may see, in the app's own `modules.txt` order.

	Modules are a desk-level concept of their own for an app that ships no workspaces (common
	enough for smaller apps in the ecosystem): its dock lists the modules' computed sidebars
	instead of workspaces, so this list is what gets rendered and it has to be both
	permission-filtered and stably ordered. `modules.txt` is the order the app itself declares;
	modules that exist only in the database (a `Module Def` added from the UI, never written to
	`modules.txt`) trail the declared ones, alphabetically.
	"""
	from frappe.utils.modules import get_visible_modules

	modules = frappe.get_all("Module Def", filters={"app_name": app_name}, pluck="name")
	declared = {name: idx for idx, name in enumerate(frappe.get_module_list(app_name))}

	return sorted(
		get_visible_modules(modules),
		key=lambda module: (declared.get(module, len(declared)), module),
	)


def get_standalone_modules(module_sidebars: dict) -> list[dict]:
	"""Custom modules with no placement, each of which stands on the desktop as its own tile.

	There is no site tile and no pseudo-app: the module *is* the tile, carrying its own sidebar
	title, header icon and landing route.

	This is a sibling of `app_data` rather than an entry inside it, and the shape is
	load-bearing. The desk maps `app_data` to installed app names (`frappe.utils.get_installed_apps`),
	so a module injected there would have the client reporting a module as an installed app.

	Derived from *custom modules with no placement*, and explicitly **not** from `Desktop Icon`
	rows: an Apps-mode site holds none of those, so a fresh install would be given no floor at
	all. The floor is the whole point -- a custom module can never become unreachable, whether
	it was never placed or was orphaned when the app naming it went away (uninstalling clears
	the placement, see `frappe.installer.release_custom_module_placements`). A placement naming
	an app that is no longer active is read as no placement here too, so the floor holds even if
	the module's row is never saved again.

	Visibility is inherited rather than reinvented: the set is intersected with
	`module_sidebars`, which has already applied the per-user module gate and already dropped
	the modules whose sidebar holds nothing the user can navigate to.
	"""
	if not module_sidebars:
		return []

	active_apps = set(frappe.get_active_apps())
	standalone = []

	# Ordered by name, as `get_navigable_modules` is: nothing about a custom module suggests an
	# order of its own, and an unstable one would reshuffle the desktop on every edit.
	for module in frappe.get_all(
		"Module Def", filters={"custom": 1}, fields=["name", "app_name"], order_by="name asc"
	):
		if module.app_name in active_apps:
			# placed: it is listed in that app's dock, so it is not standing on its own
			continue

		sidebar = module_sidebars.get(module.name)
		if not sidebar:
			continue

		standalone.append(
			{
				"module": module.name,
				"title": sidebar["label"],
				"header_icon": sidebar["header_icon"],
				"route": get_module_landing_route(sidebar),
			}
		)

	return standalone


def get_module_landing_route(sidebar: dict) -> str | None:
	"""Where a module's tile leads, as far as the server can answer it.

	The rule is the desk's own (`sidebar.module_landing_route`): a module opens on **the first
	navigable item in the sidebar this user resolved**. So it reads `items` -- already
	permission-filtered and already customized -- and not the module's workspaces, which are
	neither.

	Only the workspace case is answered here, because a workspace route is a slug and nothing
	more, while every other item type resolves through `frappe.utils.generate_route` on the
	client -- doc views, report types, filters as query params. The desktop asks the client's
	`module_landing_route` first and falls back to this, so this is the floor a tile has before
	the sidebar object exists, not a second implementation of routing.

	It stops at the *first* navigable item rather than scanning on for a workspace it can
	answer. A tile is a link with a click handler, and the two have to lead to the same place:
	a route found further down the sidebar would send a middle-click somewhere the ordinary
	click never goes.
	"""
	item = next((item for item in sidebar.get("items") or [] if item.get("type") == "Link"), None)
	if not item or item.get("link_type") != "Workspace" or not item.get("link_to"):
		return None

	public = frappe.db.get_value("Workspace", item["link_to"], "public")
	if public is None:
		return None

	prefix = "/desk/" if public else "/desk/private/"
	return prefix + frappe.utils.slug(item["link_to"])


def load_translations(bootinfo):
	from frappe.translate import get_translation_version

	bootinfo["lang"] = frappe.lang
	bootinfo["translations_version"] = get_translation_version()


def get_user_info():
	# get info for current user
	user_info = frappe._dict()
	add_user_info(frappe.session.user, user_info)

	return user_info


def get_user(bootinfo):
	"""get user info"""
	bootinfo.user = frappe.get_user().load_user()


def add_home_page(bootinfo, docs):
	"""load home page"""
	if frappe.session.user == "Guest":
		return
	home_page = frappe.db.get_default("desktop:home_page")

	if not frappe.is_setup_complete():
		bootinfo.setup_wizard_requires = frappe.get_hooks("setup_wizard_requires")

	try:
		page = frappe.desk.desk_page.get(home_page)
		docs.append(page)
		bootinfo["home_page"] = page.name
	except (frappe.DoesNotExistError, frappe.PermissionError):
		frappe.clear_last_message()
		bootinfo["home_page"] = "desktop"


def add_timezone_info(bootinfo):
	system = bootinfo.sysdefaults.get("time_zone")
	import frappe.utils.momentjs

	bootinfo.timezone_info = {"zones": {}, "rules": {}, "links": {}}
	frappe.utils.momentjs.update(system, bootinfo.timezone_info)


def load_print(bootinfo, doclist):
	print_settings = frappe.db.get_singles_dict("Print Settings")
	print_settings.doctype = ":Print Settings"
	doclist.append(print_settings)
	load_print_css(bootinfo, print_settings)


def load_print_css(bootinfo, print_settings):
	import frappe.www.printview

	bootinfo.print_css = frappe.www.printview.get_print_style(
		print_settings.print_style or "Redesign", for_legacy=True
	)


def get_success_action():
	return frappe.get_all("Success Action", fields=["*"])


def get_link_preview_doctypes():
	from frappe.utils import cint

	link_preview_doctypes = frappe.get_all("DocType", {"show_preview_popup": 1}, pluck="name")
	customizations = frappe.get_all(
		"Property Setter", fields=["doc_type", "value"], filters={"property": "show_preview_popup"}
	)

	for custom in customizations:
		if not cint(custom.value) and custom.doc_type in link_preview_doctypes:
			link_preview_doctypes.remove(custom.doc_type)
		else:
			link_preview_doctypes.append(custom.doc_type)

	return filter_out_disabled_doctypes(link_preview_doctypes)


def get_additional_filters_from_hooks():
	filter_config = frappe._dict()
	filter_hooks = frappe.get_hooks("filters_config")
	for hook in filter_hooks:
		filter_config.update(frappe.get_attr(hook)())

	return filter_config


def add_layouts(bootinfo):
	bootinfo.doctype_layouts = frappe.get_all(
		"DocType Layout",
		fields=[
			"name",
			"title",
			"document_type",
			"based_on",
			"is_standard",
			"default_print_format",
			"default_email_template",
			"condition",
		],
	)


def get_desk_settings():
	from frappe.core.doctype.user.user import desk_properties

	return frappe.get_value("User", frappe.session.user, desk_properties, as_dict=True)


def get_notification_settings():
	from frappe.desk.doctype.notification_settings.notification_settings import (
		create_notification_settings,
	)

	try:
		return frappe.get_cached_doc("Notification Settings", frappe.session.user)
	except frappe.DoesNotExistError:
		if frappe.flags.read_only:
			raise
		frappe.clear_last_message()
		create_notification_settings(frappe.session.user)
		frappe.local.flags.commit = True
		return frappe.get_cached_doc("Notification Settings", frappe.session.user)


def get_link_title_doctypes():
	dts = frappe.get_all("DocType", {"show_title_field_in_link": 1})
	custom_dts = frappe.get_all(
		"Property Setter",
		{"property": "show_title_field_in_link", "value": "1"},
		["doc_type as name"],
	)
	return filter_out_disabled_doctypes([d.name for d in dts + custom_dts if d])


def set_time_zone(bootinfo):
	bootinfo.time_zone = {
		"system": get_system_timezone(),
		"user": bootinfo.get("user_info", {}).get(frappe.session.user, {}).get("time_zone", None)
		or get_system_timezone(),
	}


def load_country_doc(bootinfo):
	country = frappe.db.get_default("country")
	if not country:
		return
	try:
		bootinfo.docs.append(frappe.get_cached_doc("Country", country))
	except Exception:
		pass


def load_currency_docs(bootinfo):
	currency = frappe.qb.DocType("Currency")

	currency_docs = (
		frappe.qb.from_(currency)
		.select(
			currency.name,
			currency.fraction,
			currency.fraction_units,
			currency.number_format,
			currency.smallest_currency_fraction_value,
			currency.symbol,
			currency.symbol_on_right,
		)
		.where(currency.enabled == 1)
		.run(as_dict=1, update={"doctype": ":Currency"})
	)

	bootinfo.docs += currency_docs


@redis_cache
def get_tree_view_doctypes():
	return filter_out_disabled_doctypes(frappe.get_all("DocType", {"default_view": "Tree"}, pluck="name"))


def add_subscription_conf():
	try:
		return frappe.conf.subscription
	except Exception:
		return ""


def get_sentry_dsn():
	if not frappe.get_system_settings("enable_telemetry"):
		return

	return os.getenv("FRAPPE_SENTRY_DSN")


def get_navigable_modules() -> list[str]:
	"""The site's modules, minus the ones this user may not navigate to.

	This is the set `get_module_sidebars` walks. It is deliberately *every* `Module Def` and
	not "every module that has a `Module Sidebar` row": a module the walk never enumerates can
	never be handed a sidebar, however that sidebar might be produced.

	Ordered by name. The row-driven walk it replaces inherited `get_all`'s default
	`modified desc`, so the payload reshuffled whenever anyone edited any sidebar -- an order
	nothing could have been relying on. Consumers that iterate the payload
	(`build_entity_module_map`, the desk's `get_modules_linking`) now get a stable one.
	"""
	from frappe.utils.modules import get_visible_modules

	# Two independent gates: `get_visible_modules` is the per-user navigation gate (blocked +
	# role-granted), `get_disabled_modules` is site-level -- the module's app is turned off, so
	# nobody navigates to it regardless of permissions.
	disabled = get_disabled_modules()
	visible = get_visible_modules(frappe.get_all("Module Def", pluck="name", order_by="name asc"))

	return [module for module in visible if module not in disabled]


def get_sidebar_bases(modules: list[str]) -> dict[str, frappe._dict]:
	"""The sidebar base for each of `modules`, keyed by module, its item rows included.

	Two origins and only two, per D4: an app shipped a `Module Sidebar` document, or the system
	computed one from the module's own contents. A module with no document is therefore not
	baseless -- it is computed and site-cached, in the same shape, so the resolution below
	cannot tell which route a base arrived by.

	**A document with no items falls back the same way**, because a sidebar with nothing in it
	is not navigation -- the module would be dropped from the payload entirely, which is
	indistinguishable from having no sidebar at all. Only its *rows* are computed: whatever the
	document says about itself (title, icon, app) is authored content and stands, so a stub
	someone created to name a module keeps its name and gains contents.

	Consequence worth knowing: emptying a sidebar's items is no longer a way to hide a module.
	Hiding belongs to the customization layers and to `User.block_modules`, which run later and
	are per-user; an empty base reads as unfinished, not as intent.

	The documents come back in one query for the whole set, and the computed route costs a site
	whose modules all ship a populated document nothing at all: it runs only for the modules
	that query did not return, and for the ones it returned empty.
	"""
	from frappe.desk.doctype.module_sidebar.module_sidebar import get_computed_base

	bases = frappe.get_all(
		"Module Sidebar",
		filters={"module": ["in", modules]},
		fields=[
			"name",
			"module",
			"title",
			"app",
			"header_icon",
		],
	)

	items_by_sidebar = get_module_sidebar_items([base.name for base in bases])
	for base in bases:
		# not `items`: `frappe._dict` inherits `dict.items()`, so that attribute is the method
		base.rows = items_by_sidebar.get(base.name, [])

	resolved = {base.module: base for base in bases}
	for module in modules:
		base = resolved.get(module)
		if base is None:
			resolved[module] = get_computed_base(module)
		elif not base.rows:
			base.rows = get_computed_base(module).rows

	return resolved


def get_module_sidebars():
	"""Build `bootinfo.module_sidebars` by resolving each of the site's modules to its sidebar.

	Resolution walks **modules**, not `Module Sidebar` rows (see `get_navigable_modules`), and
	each module's base comes from `get_sidebar_bases` -- shipped as a document, or computed
	from the module's own contents. Every module therefore has a base; what still drops one
	from the payload is having nothing in it the user can navigate to.

	Keyed by **exact-case module name**, which is the fix for the desk's long-standing
	keyspace problem: `app_data[].modules` is already a list of exact Module Def names, so it
	now indexes straight in. The legacy payload is keyed by `title.lower()`, a third keyspace
	alongside `router.slug(name)` and the exact Workspace name.
	"""
	from frappe import _
	from frappe.desk.doctype.module_onboarding.module_onboarding import get_permitted_onboardings
	from frappe.utils.modules import get_module_placement

	modules = get_navigable_modules()
	if not modules:
		return {}

	bases = get_sidebar_bases(modules)
	workspaces_by_module = get_module_workspaces()
	onboardings = get_permitted_onboardings()

	from frappe.desk.doctype.custom_module_sidebar.custom_module_sidebar import (
		apply_customizations,
		get_customization,
	)

	# `is_item_allowed` lives on `DeskViews`; one throwaway instance is the shared context.
	perm_ctx = frappe.new_doc("Workspace")
	user = frappe.session.user
	payload = {}
	for module in modules:
		base = bases[module]
		filtered = filter_sidebar_items(base.rows, perm_ctx)

		# Deltas are applied *after* the permission filter, so a customization can never
		# resurface an item the user may not see, and an added item has already been checked.
		filtered, customized = apply_customizations(module, filtered, user)

		# Same rule as the legacy builder: a sidebar with nothing but Section Breaks left is
		# a sidebar the user cannot use. Mirrored by `is_icon_permitted`; must not drift.
		# Runs after the deltas, so hiding every item genuinely hides the module.
		if not any(i["type"] != "Section Break" for i in filtered):
			continue

		label = base.title or module
		header_icon = base.header_icon
		if customized:
			for layer in (get_customization(module, None), get_customization(module, user)):
				if layer and layer.label:
					label = layer.label
				if layer and layer.header_icon:
					header_icon = layer.header_icon

		payload[module] = {
			"module": module,
			"label": _(label),
			# The desk's whole notion of app context: the rail asks this one question and lists
			# that app's other modules, or nothing at all when there is no answer. So it has to
			# agree with the placement `get_standalone_modules` reads a few lines down -- a module
			# both surfaces call placed elsewhere would have no rail *and* no tile. A shipped
			# document declares its app and that stands; a document that doesn't (an authored stub,
			# a custom module's) falls back to the module's placement, exactly as a computed base
			# already does.
			"app": base.app or get_module_placement(module),
			"header_icon": header_icon,
			# Derived, never stored: the onboarding this module offers *this user*, which is the
			# only form of the question the desk ever asks. A module opens on the first item of
			# the list below for the same reason -- both used to be pointers on the base, and a
			# pointer resolved before permission filtering can name something the reader cannot
			# open.
			"module_onboarding": onboardings.get(module),
			"customized": 1 if customized else 0,
			"workspaces": workspaces_by_module.get(module, []),
			"items": filtered,
		}

	return payload


def get_module_sidebar_items(sidebar_names):
	"""Every `Module Sidebar Item` row for the given sidebars, grouped by parent."""
	if not sidebar_names:
		return {}

	items = {}
	for item in frappe.get_all(
		"Module Sidebar Item",
		filters={"parenttype": "Module Sidebar", "parent": ["in", sidebar_names]},
		fields=[
			"parent",
			"idx",
			# no `key`: a base row's identity is derived from the columns below, and a value
			# stored in that column by an older derivation must not out-rank them. Rows written
			# before the change still hold one until their app next re-imports the sidebar.
			"type",
			"label",
			"link_type",
			"link_to",
			"icon",
			"child",
			"indent",
			"collapsible",
			"keep_closed",
			"url",
			"show_arrow",
			"filters",
			"route_options",
			"navigate_to_tab",
			"open_in_new_tab",
			"default_workspace",
		],
		order_by="idx asc",
	):
		items.setdefault(item.parent, []).append(item)

	return items


def get_module_workspaces():
	"""Public workspaces per module, in `sequence_id` order.

	Replaces `Workspace.get_module_wise_workspaces()`, which ordered by `creation` and was
	not permission-filtered.
	"""
	from frappe.desk.desktop import get_workspaces

	workspaces = {}
	allowed = {p.name for p in get_workspaces()["pages"]}

	for row in frappe.get_all(
		"Workspace",
		filters={"public": 1, "module": ["is", "set"]},
		fields=["name", "module"],
		order_by="sequence_id asc, creation asc",
	):
		if row.name in allowed:
			workspaces.setdefault(row.module, []).append(row.name)

	return workspaces


def filter_sidebar_items(items, perm_ctx):
	"""Shape, de-duplicate and permission-filter sidebar item rows for the boot payload.

	The dedupe is what the deleted uniqueness validator used to promise, moved to the one place
	that can keep the promise: rows reach here from a shipped document, a computed base and a
	customization's added rows alike, so no single writer could have guaranteed it. Two rows
	sharing an identity *are* the same item -- there is nothing a customization could say about
	one and not the other -- and the first position wins, which is what the desk rendered
	before.
	"""
	from frappe import _
	from frappe.desk.doctype.module_sidebar.module_sidebar import item_key

	filtered = []
	seen = set()
	for item in items:
		key = item_key(item)
		if key in seen:
			continue
		seen.add(key)

		entry = {
			"key": key,
			"label": _(item.label),
			"link_to": item.link_to,
			"link_type": item.link_type,
			"type": item.type,
			"icon": item.icon,
			"child": item.child,
			"collapsible": item.collapsible,
			"indent": item.indent,
			"keep_closed": item.keep_closed,
			"url": item.url,
			"show_arrow": item.show_arrow,
			"filters": item.filters,
			"route_options": item.route_options,
			"tab": item.navigate_to_tab,
			"open_in_new_tab": item.open_in_new_tab,
			"default_workspace": item.default_workspace,
		}
		if (
			item.link_type == "Report"
			and item.link_to
			and frappe.db.exists("Report", item.link_to)
			and not frappe.db.get_value("Report", item.link_to, "disabled")
		):
			report_type, ref_doctype = frappe.db.get_value(
				"Report", item.link_to, ["report_type", "ref_doctype"]
			)
			entry["report"] = {"report_type": report_type, "ref_doctype": ref_doctype}

		if item.type == "Section Break" or is_item_allowed(item.link_to, item.link_type, perm_ctx):
			filtered.append(entry)

	return filtered


def build_entity_module_map(module_sidebars):
	"""Map each entity (`link_to`) to the module whose sidebar owns it.

	The module-keyed successor to `default_workspace_map`. Built from the already-filtered
	payload, so it can never name a module or entity the user cannot see.
	"""
	entity_module = {}
	for module, sidebar in module_sidebars.items():
		for item in sidebar["items"]:
			if item.get("link_to") and item.get("default_workspace"):
				entity_module[item["link_to"]] = module

	return entity_module


def get_desktop_icon_urls():
	icons_map = {}

	for app in frappe.get_active_apps():
		app_path = frappe.get_app_path(app)
		icons_dir = os.path.join(app_path, "public", "icons", "desktop_icons")

		if not os.path.exists(icons_dir):
			continue

		icons_map[app] = {"subtle": [], "solid": []}

		for variant in ["subtle", "solid"]:
			variant_path = os.path.join(icons_dir, variant)

			if os.path.exists(variant_path):
				for fname in os.listdir(variant_path):
					if fname.endswith(".svg"):
						abs_path = os.path.join(variant_path, fname)
						assets_path = abs_path.replace(
							os.path.join(app_path, "public"), os.path.join("assets", app)
						)
						icons_map[app][variant].append(assets_path)

	return icons_map
