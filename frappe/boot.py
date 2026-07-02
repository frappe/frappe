# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
bootstrap client session
"""

import os

import frappe
import frappe.defaults
import frappe.desk.desk_page
from frappe.core.doctype.installed_applications.installed_applications import (
	get_setup_wizard_completed_apps,
)
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo, get_navbar_settings
from frappe.core.doctype.permission_type.permission_type import get_doctype_ptype_map
from frappe.desk.desk_views import DeskViews
from frappe.desk.doctype.form_tour.form_tour import get_onboarding_ui_tours
from frappe.desk.doctype.route_history.route_history import frequently_visited_links
from frappe.desk.form.load import get_meta_bundle
from frappe.desk.utils import is_item_allowed
from frappe.email.inbox import get_email_accounts
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

	bootinfo.server_date = frappe.utils.nowdate()

	if frappe.session["user"] != "Guest":
		bootinfo.user_info = get_user_info()

	bootinfo.modules = {}
	bootinfo.module_list = []
	desk_views = DeskViews()
	desk_views.build_entities()
	desk_views.add_to_boot(bootinfo)
	load_desktop_data(bootinfo)
	bootinfo.letter_heads = get_letter_heads()
	bootinfo.active_domains = frappe.get_active_domains()
	bootinfo.all_domains = frappe.get_all("Domain", pluck="name")
	add_layouts(bootinfo)

	bootinfo.module_app = frappe.local.module_app
	bootinfo.single_types = frappe.get_all("DocType", {"issingle": 1}, pluck="name")
	bootinfo.nested_set_doctypes = frappe.get_all("DocField", {"fieldname": "lft"}, pluck="parent")
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
	bootinfo.enable_address_autocompletion = frappe.db.get_single_value(
		"Geolocation Settings", "enable_address_autocompletion"
	)

	if sentry_dsn := get_sentry_dsn():
		bootinfo.sentry_dsn = sentry_dsn

	bootinfo.json_request_apps = get_json_request_apps()
	bootinfo.setup_wizard_completed_apps = get_setup_wizard_completed_apps() or []
	bootinfo.desktop_icon_urls = get_desktop_icon_urls()
	bootinfo.desktop_icon_style = get_icon_style() or "Subtle"
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
	for key in ("developer_mode", "socketio_port", "file_watcher_port"):
		if key in frappe.conf:
			bootinfo[key] = frappe.conf.get(key)


def load_desktop_data(bootinfo):
	from frappe.desk.desktop import get_user_workspaces

	allowed_pages = [d.name for d in bootinfo.workspaces.get("pages")]
	# The user's curated workspace selection (`User.workspaces`), ordered. Kept separate from
	# `bootinfo.workspaces` (which holds every permitted workspace link) so the workspace selector
	# can prefer it when set, without it affecting the full workspace listing.
	bootinfo.user_workspaces = get_user_workspaces()
	bootinfo.workspace_sidebar_item = get_sidebar_items()
	bootinfo.default_workspace_map = build_default_workspace_map(bootinfo.workspace_sidebar_item)
	bootinfo.module_wise_workspaces = get_controller("Workspace").get_module_wise_workspaces()
	bootinfo.app_data = []

	Workspace = frappe.qb.DocType("Workspace")
	Module = frappe.qb.DocType("Module Def")

	for app_name in frappe.get_installed_apps():
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
				bootinfo.app_data.append(
					dict(
						on_apps_screen=False,
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
		# left join so module-less custom workspaces aren't dropped, and keep only public ones --
		# private workspaces are surfaced separately by the selector's private listing.
		workspaces = [
			r[0]
			for r in (
				frappe.qb.from_(Workspace)
				.left_join(Module)
				.on(Workspace.module == Module.name)
				.select(Workspace.name)
				.where(
					((Module.app_name == app_name) | (Workspace.app == app_name)) & (Workspace.public == 1)
				)
				.run()
			)
			if r[0] in allowed_pages
		]

		bootinfo.app_data.append(
			dict(
				# whether the app opts into the apps screen via the add_to_apps_screen hook
				on_apps_screen=bool(apps),
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
				modules=frappe.get_all("Module Def", dict(app_name=app_name), pluck="name"),
				workspaces=workspaces,
			)
		)


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

	return link_preview_doctypes


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
	return frappe.get_cached_doc("Notification Settings", frappe.session.user)


def get_link_title_doctypes():
	dts = frappe.get_all("DocType", {"show_title_field_in_link": 1})
	custom_dts = frappe.get_all(
		"Property Setter",
		{"property": "show_title_field_in_link", "value": "1"},
		["doc_type as name"],
	)
	return [d.name for d in dts + custom_dts if d]


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
	return frappe.get_all("DocType", {"default_view": "Tree"}, pluck="name")


def add_subscription_conf():
	try:
		return frappe.conf.subscription
	except Exception:
		return ""


def get_sentry_dsn():
	if not frappe.get_system_settings("enable_telemetry"):
		return

	return os.getenv("FRAPPE_SENTRY_DSN")


def get_authored_sidebar_items(workspace_names):
	"""Authored `Workspace Sidebar Item` rows grouped by parent workspace.

	A single query (`parenttype = "Workspace"`, `parent in workspace_names`) replaces
	loading each workspace's child table individually. Rows are returned in `idx` order
	and de-duplicated per workspace, so repeated rows (e.g. left behind by a re-run
	migration) collapse to a single item.
	"""
	items_by_workspace = {}
	if not workspace_names:
		return items_by_workspace

	seen = {}
	for item in frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parenttype": "Workspace", "parent": ["in", workspace_names]},
		fields=[
			"parent",
			"idx",
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
		key = (item.type, item.label, item.link_type, item.link_to)
		if key in seen.setdefault(item.parent, set()):
			continue
		seen[item.parent].add(key)
		items_by_workspace.setdefault(item.parent, []).append(item)

	return items_by_workspace


def get_sidebar_items():
	"""Build the per-workspace sidebar payload (`bootinfo.workspace_sidebar_item`).

	The authored `Workspace.sidebar_items` table is the source of truth. Modules without an
	authored workspace sidebar fall back to one generated on the fly. The legacy
	`Workspace Sidebar` doctype is no longer read here.
	"""
	from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import auto_generate_sidebar_from_module

	# `is_item_allowed` lives on `DeskViews`, which `Workspace` extends. Use one throwaway
	# `Workspace` instance as a shared permission context for filtering every item.
	perm_ctx = frappe.new_doc("Workspace")
	sidebar_items = {}

	# Primary source: authored `Workspace.sidebar_items` (the post-merge model). Everything the
	# boot needs is fetched in batch instead of per workspace doc: `get_workspaces()` already
	# carries name/module/app/icon, a single query keys every authored item by workspace (a
	# workspace is "with sidebar" iff it appears there), and one more batches `module_onboarding`.
	workspaces = get_workspaces_with_sidebar()
	items_by_workspace = get_authored_sidebar_items([w.name for w in workspaces])
	module_onboarding = get_workspace_module_onboarding([w.name for w in workspaces])
	for workspace in workspaces:
		add_sidebar_entry(
			sidebar_items,
			title=workspace.name,
			items=items_by_workspace.get(workspace.name, []),
			module=workspace.module,
			app=workspace.app,
			header_icon=workspace.icon,
			module_onboarding=module_onboarding.get(workspace.name),
			perm_ctx=perm_ctx,
		)

	# Fallback: modules without an authored workspace sidebar are generated each boot.
	for sidebar in auto_generate_sidebar_from_module():
		if sidebar.title.lower() in sidebar_items:
			continue
		add_sidebar_entry(
			sidebar_items,
			title=sidebar.title,
			items=sidebar.items,
			module=sidebar.module,
			app=sidebar.get("app"),
			header_icon=sidebar.get("header_icon"),
			module_onboarding=sidebar.get("module_onboarding"),
			from_module=sidebar.get("from_module"),
			perm_ctx=perm_ctx,
		)

	return sidebar_items


def build_default_workspace_map(sidebar_items):
	"""Map each entity (`link_to`) to the title of the workspace that owns it.

	An entity can appear in several workspace sidebars; the item flagged
	`default_workspace` marks its owning workspace, so the desk can route the doctype to that
	workspace's sidebar on navigation. Built from the already-filtered `sidebar_items` payload
	so it only ever references workspaces/items the user is allowed to see.
	"""
	default_map = {}
	for sidebar in sidebar_items.values():
		for item in sidebar["items"]:
			if item.get("link_to") and item.get("default_workspace"):
				default_map[item["link_to"]] = sidebar["label"]
	return default_map


def get_workspaces_with_sidebar():
	"""Workspaces the user may see that carry authored sidebar items.

	Reuses `get_workspaces()` so the workspace selector shares a single
	visibility/order/hidden source of truth with the desk workspace listing, then keeps
	only the workspaces that have authored sidebar items (preserving order).

	Membership is resolved with a single existence query against `Workspace Sidebar Item`
	rather than loading each visible workspace's doc, so this stays flat on the boot path
	regardless of how many workspaces the user can see.
	"""
	from frappe.desk.desktop import get_workspaces

	pages = get_workspaces()["pages"]
	if not pages:
		return []

	with_sidebar = set(
		frappe.get_all(
			"Workspace Sidebar Item",
			filters={"parenttype": "Workspace", "parent": ["in", [page.name for page in pages]]},
			distinct=True,
			pluck="parent",
		)
	)
	return [page for page in pages if page.name in with_sidebar]


def get_workspace_module_onboarding(workspace_names):
	"""Map each workspace name to its `module_onboarding` link, in one query.

	Batched so `get_sidebar_items` doesn't load a workspace doc just to read this one field.
	"""
	if not workspace_names:
		return {}

	return {
		w.name: w.module_onboarding
		for w in frappe.get_all(
			"Workspace",
			filters={"name": ["in", workspace_names]},
			fields=["name", "module_onboarding"],
		)
	}


def add_sidebar_entry(
	sidebar_items,
	*,
	title,
	items,
	module,
	app,
	header_icon,
	module_onboarding,
	perm_ctx,
	from_module=0,
):
	"""Add one workspace's permission-filtered sidebar to `sidebar_items`, keyed by title."""
	from frappe import _

	filtered_items = []
	for item in items:
		entry = {
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
			entry["report"] = {
				"report_type": report_type,
				"ref_doctype": ref_doctype,
			}
		if item.type == "Section Break" or is_item_allowed(item.link_to, item.link_type, perm_ctx):
			filtered_items.append(entry)

	# A sidebar (and its desktop icon) is shown only if the user can see at least one
	# real item in it, i.e. a non-Section-Break item survived the per-item filter above.
	# This is the single source of truth for sidebar permissions and mirrors
	# Desktop Icon.is_permitted.
	if not any(i["type"] != "Section Break" for i in filtered_items):
		return

	sidebar_items[title.lower()] = {
		"label": title,
		"items": filtered_items,
		"header_icon": header_icon,
		"module_onboarding": module_onboarding,
		"module": module,
		"app": app,
		"from_module": from_module,
	}


def get_desktop_icon_urls():
	icons_map = {}

	for app in frappe.get_installed_apps():
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
