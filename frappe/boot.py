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
	# module ships none. Unfiltered on purpose: the client already checks each heir against
	# `module_sidebars`, the per-user payload, so filtering here would repeat that. Keyed by real
	# module name, unlike module_app above.
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
	"""Map each companion app to the host app whose rail it mounts on.

	A companion app, such as India Compliance for ERPNext or India Payroll for HRMS, has no shell
	of its own; its entries live on the host app's rail. This map lets the desk resolve the app
	context (rail and header) of a companion app's workspaces to the host app, so the user stays
	in the host's rail while using the companion.

	It is read from the records rather than a hook, and it uses the dock layers cache, which
	exists for questions the boot asks on every request. Only mounts that take effect are here: a
	companion whose host is not installed, whose host ships no dock, or that ships no rows itself
	is an ordinary app with its own rail and apps-screen slot.
	"""
	from frappe.desk.doctype.dock.dock import mounted_apps

	return mounted_apps()


# Fallback apps-screen sort order for apps that don't declare a `sequence_id` in their
# `add_to_apps_screen` hook. Sits below Framework (1000) so it always trails real apps.
#
# This default stays. It orders the app's slot on the apps screen, which is what makes the rails
# read in the same order as the screen users reach them from. Its module-level counterpart is
# gone: where a module sits on a rail is a row's position in the `Dock` record its app ships,
# which has no unset state and so needs no default.
DEFAULT_APP_SEQUENCE_ID = 100


def load_desktop_data(bootinfo):
	from frappe.desk.doctype.dock.dock import resolve_dock

	# A companion app's workspaces resolve their app context (rail and header) to the host app it
	# mounts on, so the companion appears inside the host's rail rather than switching the desk to
	# a shell of its own. This is not redundant with the companion's rows being in the host's
	# entry set: only those rows are derivable from that, and a companion's other workspaces need
	# the host's rail on screen too.
	bootinfo.app_rail_host = get_app_rail_host_map()
	# The dock this user sees, keyed by app: each app's own dock, with the site's arrangement and
	# then the user's applied on top, filtered to what they can reach. It is keyed by app because
	# a dock layer is per app, so arranging one app's rail says nothing about another's and the
	# client no longer has to intersect one cross-app list with each app's entry set. This is an
	# arrangement rather than the dock's contents: an entry it does not name still shows, in its
	# app's own order, after the ones it does. An app with no arrangement is absent rather than
	# carried as an empty list.
	bootinfo.dock = resolve_dock()
	# Keyed by exact-case module name, so a `Sidebar` row in `app_data[].dock` indexes straight in.
	# This replaced three overlapping payloads: `workspace_sidebar_item` (keyed by lowercased
	# workspace title), `default_workspace_map` and `module_wise_workspaces`, which together made
	# the desk reconcile four keyspaces for one identity.
	bootinfo.module_sidebars = get_module_sidebars()
	bootinfo.entity_module = build_entity_module_map(bootinfo.module_sidebars)

	# Only the Desktop Icon grid reads these; the default Apps screen builds itself from
	# `app_data` below. Set after `module_sidebars`, which `is_icon_permitted` reads.
	if is_desktop_icons_page():
		from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons

		bootinfo.desktop_icons = get_desktop_icons(bootinfo=bootinfo)

	bootinfo.app_data = get_app_data()


def get_app_data() -> list[dict]:
	"""Return the apps the desk knows about, each with the ordered set of entries its dock offers.

	This backs the apps (desktop) screen and the dock, which renders
	`app_data[app].dock` for whichever app is in context, ordered by the arrangement in
	`frappe.boot.dock`. It is one typed list rather than the separate module and workspace lists
	it replaces, which the client had to reconcile to render a single rail and where the pin
	landed in the list the rail never read. It stays its own function so anything that re-mounts a
	workspace can hand the client a fresh copy without duplicating the grouping rules (see
	`mount_workspace`).

	It takes no arguments. It used to be given the workspace names this user may see, for the
	derived first-workspace guess that ticket 11 removed. Reach is now applied per entry by
	`get_app_entry_set`, which asks the same question about the same user.
	"""
	from frappe.desk.doctype.dock.dock import get_app_entry_set

	app_data = []

	app_rail_host = get_app_rail_host_map()

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

		# The entries this app's dock offers: the rows of the `Dock` record it ships,
		# permission-filtered. This is no longer `get_app_modules`, because an app's dock stopped
		# being every module it owns in some order and became a document its author writes, so a
		# module the record never names is off this rail permanently. Which of these are on the
		# rail, and in what order, is `frappe.boot.dock`.
		dock = get_app_entry_set(app_name)

		app_data.append(
			dict(
				# Whether the app opts into the apps screen via the add_to_apps_screen hook. An app
				# that pins into a host app's dock never takes a slot of its own, even if it still
				# declares add_to_apps_screen from before the dock existed: the pin wins.
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
				# Only what the app declares. The third source used to be an arbitrary workspace
				# picked by `sequence_id`, which was a guess, and a worse one under this model,
				# because that workspace may sit in a module the app's `Dock` record never names,
				# so the icon would land somewhere the rail does not show. The rest of the steps
				# are resolved late on the client, so reordering a rail moves the landing with it
				# (`Sidebar.app_landing_route`).
				app_route=app_info.get("route")
				or (
					frappe.get_hooks("app_home", app_name=app_name)
					and frappe.get_hooks("app_home", app_name=app_name)[0]
				)
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
	"""Return one app's modules that this user can navigate to, in a stable order.

	This used to be the app's dock, which is now the rows of the record the app ships. Three
	readers are left, and all want the same thing: the switcher's list of shells, the manager's
	pool of things to add, and the last step of the landing ladder. Each offers what this returns
	as a destination.

	That is why the filter is narrower than before. It used to filter only blocked modules, which
	was harmless while it fed the rail, since the client silently dropped any row missing from the
	module-sidebars payload, where a disabled app's modules and code-only modules never appear.
	Removing that mask without adding the two checks would offer `Core`, `Custom` and `Desk` as
	destinations that resolve to nothing.

	So it asks the same three questions `get_navigable_modules` asks site-wide, scoped to one app:
	not blocked by this user, not in a disabled app, and not code-only. That is one definition of
	a module you can navigate to.

	The order has two tiers:

	1. `modules.txt` position, the order the app declares its modules in.
	2. Name, for modules that exist only in the database (a `Module Def` added from the UI and
	   never written to `modules.txt`), which follow the declared ones alphabetically.

	Sorting by name alone would alphabetise the trailing set, which changes behaviour.
	"""
	from frappe.utils.modules import get_code_only_modules, get_visible_modules

	modules = get_visible_modules(frappe.get_all("Module Def", filters={"app_name": app_name}, pluck="name"))
	if not modules:
		return []

	disabled = get_disabled_modules()
	code_only = get_code_only_modules()
	modules = [module for module in modules if module not in disabled and module not in code_only]

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

	Which shells exist still comes from walking modules, not `Sidebar` rows (see
	`get_navigable_modules`). What a module owns is whatever `get_sidebar_bases` finds under it,
	and each of those goes to `resolve_sidebar`, which holds every rule that shapes an answer.
	This function picks the set and assembles the payload; it decides nothing about what a shell
	resolves to.

	It is keyed by shell identity: a `Sidebar` document's exact name, or the exact module name
	where the base was computed. Keyed by module, a module's second sidebar was overwritten by its
	first and disappeared with no error. A shell is what the desk shows and what a dock row
	selects, so it is the correct key. The naming rule (`set_default_title`) keeps the two the
	same string unless a sidebar was renamed, so a reader holding a module still indexes straight
	in.

	This is one keyspace, in exact case. The legacy payload was keyed by `title.lower()`, a third
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
	"""Map each entity (`link_to`) to the shell whose sidebar owns it.

	This replaces `default_workspace_map`. It is built from the already-filtered payload and keyed
	the same way, so it can never name a shell or an entity the user cannot see, and what it
	returns indexes straight back into the payload.

	When two sidebars claim the same entity, the last-installed app wins, and two claims from the
	same app are ordered by shell name ascending. Install order follows dependency order wherever
	a dependency exists, since the installer refuses to install an app before its `required_apps`,
	so a claim from the app built on top beats the one underneath, which is how `hrms` claims
	`Employee`. The rule stops here: the desk's `get_modules_linking` orders curations and does
	not use it.

	Two consequences are not visible in the loop below:

	1. Ownership is per-user. The payload is permission-filtered before it gets here, so the
	   winner is the last-installed app among the claims this user can see. Two users may
	   correctly resolve one entity to different shells, and a user who cannot see the winning
	   shell falls to the next claim rather than to nothing.
	2. The losing claim is not reported anywhere: no log, no report, no `after_migrate` line. The
	   problem with the last-write-wins this replaces was that it was arbitrary, over a dict
	   ordered by module name, not that it was quiet. A rule an author can predict from their own
	   install order needs no warning, so please do not add one.
	"""
	# A module placed by `get_module_placement` rather than by a shipped document can name an app
	# that is not installed here, so an unknown app ranks below every installed one instead of
	# raising. Ownership is not worth a broken boot.
	install_index = {app: index for index, app in enumerate(frappe.get_installed_apps())}

	claims = {}
	for shell, sidebar in module_sidebars.items():
		claim = (install_index.get(sidebar.get("app"), -1), shell)
		for item in sidebar["items"]:
			if item.get("link_to") and item.get("is_default_module"):
				claims.setdefault(item["link_to"], []).append(claim)

	# The comparator, in one place: highest install index, then lowest shell name.
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
