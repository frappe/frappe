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
	# Where a code-only module's navigation went, so the desk can resolve an entity whose own
	# module ships none. Raw and unfiltered on purpose: the client already tests each heir against
	# `module_sidebars`, which is the per-user payload, so filtering here would say the same thing
	# twice. Keyed by real module name, unlike module_app above.
	from frappe.utils.modules import get_code_only_module_heirs

	bootinfo.code_only_module_heirs = get_code_only_module_heirs()
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


def get_app_rail_host_map():
	"""Map of companion app -> the host app it pins into with an `add_to_dock` row.

	A companion app (e.g. India Compliance for ERPNext, India Payroll for HRMS) has no shell of
	its own; its workspaces live inside the host app's dock. This map lets the desk resolve the
	app context (dock + header) of a companion app's workspaces to the host app, so you stay "in"
	the host's dock while using the companion. When a companion pins into more than one host, the
	first host wins.

	Derived from the **rows carrying `app`**, never from the hook's mere presence. Every app
	declares `add_to_dock` now, so a presence check would delete each adopting app from the apps
	screen. Pinning into a host costs the slot; declaring your own order does not.
	"""
	from frappe.desk.doctype.dock.dock import DOCK_HOOK

	host_map = {}
	for app_name in frappe.get_active_apps():
		for entry in frappe.get_hooks(DOCK_HOOK, app_name=app_name) or []:
			if isinstance(entry, dict) and entry.get("app") and entry.get("app") != app_name:
				host_map[app_name] = entry["app"]
				break
	return host_map


# Fallback apps-screen sort order for apps that don't declare a `sequence_id` in their
# `add_to_apps_screen` hook. Sits below Framework (1000) so it always trails real apps.
#
# This one stays. It orders the thing it lives on -- the app's slot on the apps screen -- and it
# is what makes the dock read in the same order as the screen people reach it from. Its
# module-level counterpart is gone: where a module sits on the dock is `add_to_dock`, an ordered
# list, which has no unset state to need a default.
DEFAULT_APP_SEQUENCE_ID = 100


def load_desktop_data(bootinfo):
	from frappe.desk.doctype.dock.dock import resolve_dock

	allowed_pages = [d.name for d in bootinfo.workspaces.get("pages")]
	# A companion app's workspaces resolve their app context (dock + header) to the host app they
	# pinned into, so the companion appears to live inside the host's dock rather than flipping
	# the desk to a shell of its own. Not redundant with the pin being in the host's entry set:
	# only the pinned workspace is derivable from that, and a companion's *other* workspaces need
	# the host's dock on screen too.
	bootinfo.app_rail_host = get_app_rail_host_map()
	# The dock this user sees, keyed by app: each app's own dock, with the site's arrangement and
	# then their own applied on top, filtered to what they may reach. Keyed by app because a dock
	# layer is per app -- arranging one app's rail says nothing about another's, and the client no
	# longer has to intersect one cross-app list with each app's entry set. An arrangement, not
	# the dock's contents -- an entry it doesn't name still shows, in its app's own order, after
	# the ones it does. An app with no arrangement is absent rather than carried as an empty list.
	bootinfo.dock = resolve_dock()
	# Keyed by exact-case module name, so a `Sidebar` row in `app_data[].dock` indexes straight
	# in. This
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


def get_app_data(allowed_pages: list[str]) -> list[dict]:
	"""The apps the desk knows about, each with the ordered set of entries its dock offers.

	This is what backs the apps (desktop) screen and the workspace dock: the dock renders
	`app_data[app].dock` for whichever app is in context, ordered by the arrangement in
	`frappe.boot.dock`. One typed list rather than the separate module and workspace lists it
	replaces -- the client used to reconcile the two to render a single rail, and the pin landed
	in the one the rail never read. Kept as its own function so anything that re-mounts a
	workspace can hand the client a fresh copy without duplicating the grouping rules (see
	`mount_workspace`).

	`allowed_pages` is the set of workspace names the user may see -- `bootinfo.workspaces.pages`,
	i.e. every public workspace they're permitted plus their own private ones.
	"""
	from frappe.desk.doctype.dock.dock import get_dock_workspaces

	app_data = []

	# Workspaces named by an `add_to_dock` row on this app's fragment -- its own, and the ones
	# companion apps pinned onto it instead of taking an apps-screen slot of their own. Resolved
	# once, folded into each host's list below.
	pinned = get_dock_workspaces()
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
				# The user can't access this app, so we don't expose its routes or its dock. We
				# still surface its name/title so things that reference the app can be labelled
				# (e.g. the sidebar header subtitle) instead of falling back to the user's name.
				# on_apps_screen stays False so it never shows on the apps screen, and an empty
				# `dock` keeps the desk-side lookups from breaking.
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
						dock=[],
					)
				)
				continue

		# The app's own workspaces. Not shipped: this list stopped being part of the payload when
		# the dock became one typed list, and the only thing left asking for it is the landing
		# route below. A workspace belongs to this app if its module is the app's; the left join
		# keeps module-less custom workspaces from being dropped, and `sequence_id` is the
		# workspace record's own configured order.
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

		# One ordered typed list: the app's own modules as `Sidebar` rows, then every `Workspace`
		# an `add_to_dock` row put on this app's fragment -- its own, and the ones companions
		# pinned onto it. A pin is *appended* rather than positioned: a companion is not
		# asserting a default into an arrangement that is not its, and where it sits is Layer
		# business. Permission-filtered like anything else that reaches the dock.
		dock = [{"sidebar": module} for module in get_app_modules(app_name)]
		for workspace in pinned.get(app_name, []):
			if workspace in allowed_pages:
				dock.append({"link_type": "Workspace", "link_to": workspace})

		app_data.append(
			dict(
				# whether the app opts into the apps screen via the add_to_apps_screen hook. An app
				# that pins into a host app's dock never takes a slot of its own, even if it still
				# declares add_to_apps_screen from before the dock existed -- the pin wins.
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
				dock=dock,
			)
		)

	return app_data


def get_app_modules(app_name: str) -> list[str]:
	"""The app's modules the user may see, in the order its dock offers them.

	This is the *entry set*, not the arrangement. Where a module actually sits is
	`add_to_dock` -- an ordered list in the app's `hooks.py`, resolved through the site's and
	each person's layers -- and a module that list never names simply trails the ones it does,
	in this order. So this has to be permission-filtered and stably ordered, and nothing more.

	Two tiers:

	1. **`modules.txt` position** -- the order the app declares its modules in.
	2. **name** -- for modules that exist only in the database (a `Module Def` added from the
	   UI, never written to `modules.txt`), which trail the declared ones alphabetically.

	Collapsing these to name alone would alphabetise the trailing set, which is a behaviour
	change and not one anybody asked for.
	"""
	from frappe.utils.modules import get_visible_modules

	modules = get_visible_modules(frappe.get_all("Module Def", filters={"app_name": app_name}, pluck="name"))
	if not modules:
		return []

	declared = {name: idx for idx, name in enumerate(frappe.get_module_list(app_name))}

	return sorted(modules, key=lambda module: (declared.get(module, len(declared)), module))


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


def get_module_sidebars():
	"""Build `bootinfo.module_sidebars` by resolving each of the site's shells.

	Which shells there are still comes from walking **modules**, not `Sidebar` rows (see
	`get_navigable_modules`); what a module owns is then whatever `get_sidebar_bases` finds
	under it, and each of those is handed to `resolve_sidebar`, which is where every rule that
	shapes an answer lives. This function chooses the set and assembles the payload; it decides
	nothing about what a shell resolves to.

	Keyed by **shell identity** -- a `Sidebar` document's exact name, or the exact module name
	where the base was computed. Keyed by module, a module's second sidebar was overwritten by
	its first and vanished with no error anywhere; a shell is what the desk shows and what a
	dock row selects, so it is the honest key. The naming rule (`set_default_title`) keeps the
	two the same string for every sidebar nobody deliberately renamed, so a reader holding a
	module still indexes straight in.

	This is one keyspace, exact case. The legacy payload was keyed by `title.lower()`, a third
	keyspace alongside `router.slug(name)` and the exact Workspace name.
	"""
	from frappe.desk.doctype.sidebar.sidebar import (
		SidebarContext,
		get_navigable_modules,
		resolve_sidebar,
	)

	modules = get_navigable_modules()
	if not modules:
		return {}

	user = frappe.session.user
	context = SidebarContext.for_modules(modules, user)

	payload = {}
	for shell in context.bases:
		resolved = resolve_sidebar(shell, user, context)
		if resolved:
			payload[shell] = resolved.as_boot_entry()

	return payload


def build_entity_module_map(module_sidebars):
	"""Map each entity (`link_to`) to the **shell** whose sidebar owns it.

	The successor to `default_workspace_map`. Built from the already-filtered payload and keyed
	the same way it is, so it can never name a shell or an entity the user cannot see, and what
	it returns indexes straight back into the payload.

	When two sidebars claim the same entity the winner is the **last-installed app**, and two
	claims from the *same* app are separated by shell name ascending. Install order is
	dependency order wherever a dependency exists -- the installer refuses to install an app
	before its `required_apps` -- so a claim from the app built on top beats the one underneath
	it, which is the `hrms` claims `Employee` case. The rule stops here: the desk's
	`get_modules_linking` orders *curations* and deliberately does not use it.

	Two consequences worth stating, because neither is visible in the loop:

	- **Ownership is per-user.** The payload is permission-filtered before it gets here, so the
	  winner is the last-installed app *among the claims this user can see*. Two users may
	  correctly resolve one entity to different shells, and a user who cannot see the winning
	  shell falls to the next claim down rather than to nothing.
	- **The loser is told nothing**, deliberately -- no log, no report, no `after_migrate` line.
	  What was wrong with the last-write-wins this replaces was that it was a *coin flip* (over a
	  dict ordered by module name), not that it was quiet; a rule an author can predict from their
	  own install order needs no warning. Please don't add one back.
	"""
	# A module placed by `get_module_placement` rather than by a shipped document can name an app
	# that isn't installed here, so an unknown app ranks below every installed one instead of
	# raising -- ownership is not worth a broken boot.
	install_index = {app: index for index, app in enumerate(frappe.get_installed_apps())}

	claims = {}
	for shell, sidebar in module_sidebars.items():
		claim = (install_index.get(sidebar.get("app"), -1), shell)
		for item in sidebar["items"]:
			if item.get("link_to") and item.get("is_default_module"):
				claims.setdefault(item["link_to"], []).append(claim)

	# the comparator, stated once: highest install index, then lowest shell name
	return {
		entity: min(entity_claims, key=lambda claim: (-claim[0], claim[1]))[1]
		for entity, entity_claims in claims.items()
	}


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
