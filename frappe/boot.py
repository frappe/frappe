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
from frappe.core.doctype.installed_applications.installed_applications import (
	get_setup_wizard_completed_apps,
)
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo, get_navbar_settings
from frappe.core.doctype.permission_type.permission_type import get_doctype_ptype_map
from frappe.desk.desk_views import DeskViews
from frappe.desk.doctype.changelog_feed.changelog_feed import get_changelog_feed_items
from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons
from frappe.desk.doctype.form_tour.form_tour import get_onboarding_ui_tours
from frappe.desk.doctype.route_history.route_history import frequently_visited_links
from frappe.desk.form.load import get_meta_bundle
from frappe.email.inbox import get_email_accounts
from frappe.integrations.frappe_providers.cloud_settings import (
	get_boot_context as get_cloud_settings_boot_context,
)
from frappe.integrations.frappe_providers.frappecloud_billing import current_site_info, is_fc_site
from frappe.model.base_document import get_controller
from frappe.utils import add_user_info, get_system_timezone
from frappe.utils.caching import redis_cache
from frappe.utils.change_log import get_versions
from frappe.utils.frappecloud import on_frappecloud
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
	bootinfo.desktop_icons = get_desktop_icons(bootinfo=bootinfo)
	bootinfo.letter_heads = get_letter_heads()
	bootinfo.active_domains = frappe.get_active_domains()
	bootinfo.all_domains = frappe.get_all("Domain", pluck="name")
	add_layouts(bootinfo)

<<<<<<< HEAD
	bootinfo.module_app = frappe.local.module_app
	bootinfo.single_types = frappe.get_all("DocType", {"issingle": 1}, pluck="name")
	bootinfo.nested_set_doctypes = frappe.get_all("DocField", {"fieldname": "lft"}, pluck="parent")
=======
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
>>>>>>> 86e08e8 (feat: Don't show up disabled apps, workspaces on desk)
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
	bootinfo.marketplace_apps = get_marketplace_apps()
	bootinfo.is_fc_site = is_fc_site()
	bootinfo.changelog_feed = get_changelog_feed_items()
	bootinfo.cloud_settings = get_cloud_settings_boot_context()
	bootinfo.enable_address_autocompletion = frappe.db.get_single_value(
		"Geolocation Settings", "enable_address_autocompletion"
	)

	if sentry_dsn := get_sentry_dsn():
		bootinfo.sentry_dsn = sentry_dsn

	bootinfo.setup_wizard_completed_apps = get_setup_wizard_completed_apps() or []
	bootinfo.desktop_icon_urls = get_desktop_icon_urls()
	bootinfo.desktop_icon_style = get_icon_style() or "Subtle"
	if bootinfo.is_fc_site:
		bootinfo.site_info = current_site_info()
	return bootinfo


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
	from frappe.core.api.file import get_max_file_size

	bootinfo.max_file_size = get_max_file_size()
	for key in ("developer_mode", "socketio_port", "file_watcher_port"):
		if key in frappe.conf:
			bootinfo[key] = frappe.conf.get(key)


def load_desktop_data(bootinfo):
	allowed_pages = [d.name for d in bootinfo.workspaces.get("pages")]
	bootinfo.workspace_sidebar_item = get_sidebar_items(allowed_pages)
	bootinfo.module_wise_workspaces = get_controller("Workspace").get_module_wise_workspaces()
	bootinfo.app_data = []

	Workspace = frappe.qb.DocType("Workspace")
	Module = frappe.qb.DocType("Module Def")

<<<<<<< HEAD
	for app_name in frappe.get_installed_apps():
=======
	for app_name in frappe.get_active_apps():
>>>>>>> 86e08e8 (feat: Don't show up disabled apps, workspaces on desk)
		# get app details from app_info (/apps)
		apps = frappe.get_hooks("add_to_apps_screen", app_name=app_name)
		app_info = {}
		if apps:
			app_info = apps[0]
			has_permission = app_info.get("has_permission")
			if has_permission and not frappe.get_attr(has_permission)():
				continue

		workspaces = [
			r[0]
			for r in (
				frappe.qb.from_(Workspace)
				.inner_join(Module)
				.on(Workspace.module == Module.name)
				.select(Workspace.name)
				.where(Module.app_name == app_name)
				.run()
			)
			if r[0] in allowed_pages
		]

		bootinfo.app_data.append(
			dict(
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
				app_route=(
					frappe.get_hooks("app_home", app_name=app_name)
					and frappe.get_hooks("app_home", app_name=app_name)[0]
				)
				or (workspaces and "/desk/" + frappe.utils.slug(workspaces[0]))
				or "",
				app_logo_url=app_info.get("logo")
				or frappe.get_hooks("app_logo_url", app_name=app_name)
				or frappe.get_hooks("app_logo_url", app_name="frappe"),
				modules=frappe.get_all("Module Def", dict(app_name=app_name), pluck="name"),
				workspaces=workspaces,
			)
		)


def load_translations(bootinfo):
	from frappe.translate import get_messages_for_boot

	bootinfo["lang"] = frappe.lang
	bootinfo["__messages"] = get_messages_for_boot()


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
	# add routes for readable doctypes
	bootinfo.doctype_layouts = frappe.get_all("DocType Layout", ["name", "route", "document_type"])


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


def get_marketplace_apps():
	import requests

	apps = []
	cache_key = "frappe_marketplace_apps"

	if frappe.conf.developer_mode or not on_frappecloud():
		return apps

	def get_apps_from_fc():
		remote_site = frappe.conf.frappecloud_url or "frappecloud.com"
		request_url = f"https://{remote_site}/api/method/press.api.marketplace.get_marketplace_apps"
		request = requests.get(request_url, timeout=2.0)
		return request.json()["message"]

	try:
		apps = frappe.cache.get_value(cache_key, get_apps_from_fc, shared=True)
		installed_apps = set(frappe.get_installed_apps())
		apps = [app for app in apps if app["name"] not in installed_apps]
	except Exception:
		# Don't retry for a day
		frappe.cache.set_value(cache_key, apps, shared=True, expires_in_sec=24 * 60 * 60)

	return apps


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


<<<<<<< HEAD
def get_sidebar_items(allowed_workspaces):
	from frappe import _
=======
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
	from frappe.app_state import get_disabled_modules
>>>>>>> 86e08e8 (feat: Don't show up disabled apps, workspaces on desk)
	from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import auto_generate_sidebar_from_module

	workspace_sidebars = frappe.get_all(
		"Workspace Sidebar", fields=["name", "header_icon", "module_onboarding"]
	)
	module_sidebars = auto_generate_sidebar_from_module()
	workspace_sidebars.extend(module_sidebars)
	sidebar_items = {}
	disabled_modules = get_disabled_modules()

<<<<<<< HEAD
	for sidebar in workspace_sidebars:
		sidebar_title = sidebar.get("name")
		sidebar_doc = None
		if sidebar_title:
			sidebar_doc = frappe.get_doc("Workspace Sidebar", sidebar_title)
		else:
			sidebar_title = sidebar.title
			sidebar_doc = sidebar
		is_my_workspaces = "My Workspaces" in sidebar_title
		items = []
		for item in sidebar_doc.items:
			workspace_sidebar = {
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
=======
	# Primary source: authored `Workspace.sidebar_items` (the post-merge model). Everything the
	# boot needs is fetched in batch instead of per workspace doc: `get_workspaces()` already
	# carries name/module/app/icon, a single query keys every authored item by workspace (a
	# workspace is "with sidebar" iff it appears there), and one more batches `module_onboarding`.
	workspaces = get_workspaces_with_sidebar()
	items_by_workspace = get_authored_sidebar_items([w.name for w in workspaces])
	module_onboarding = get_workspace_module_onboarding([w.name for w in workspaces])
	for workspace in workspaces:
		if workspace.module in disabled_modules:
			continue
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

	# Fallback: modules without an authored workspace sidebar are generated each boot. That set is
	# built site-wide (and cached), so it carries no per-user context -- drop the user's blocked
	# modules here. It's the same gate an authored workspace's sidebar already passes through
	# (`Workspace.is_permitted` falls back to blocked modules), and it matters more for a generated
	# one: an app that ships no workspaces is navigated by module, so a blocked module left in here
	# would hand the user both a sidebar and a dock entry to reach it by.
	blocked_modules = get_blocked_modules()
	for sidebar in auto_generate_sidebar_from_module():
		if sidebar.title.lower() in sidebar_items or sidebar.module in blocked_modules:
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
>>>>>>> 86e08e8 (feat: Don't show up disabled apps, workspaces on desk)
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
				workspace_sidebar["report"] = {
					"report_type": report_type,
					"ref_doctype": ref_doctype,
				}
			if (
				is_my_workspaces
				or item.type == "Section Break"
				or sidebar_doc.is_item_allowed(item.link_to, item.link_type, allowed_workspaces)
			):
				items.append(workspace_sidebar)

		# A sidebar (and its desktop icon) is shown only if the user can see at least one
		# real item in it, i.e. a non-Section-Break item survived the per-item filter above.
		# This is the single source of truth for sidebar permissions and mirrors
		# Desktop Icon.is_permitted. "My Workspaces" is always shown.
		if not is_my_workspaces and not any(item["type"] != "Section Break" for item in items):
			continue

		sidebar_items[sidebar_title.lower()] = {
			"label": sidebar_title,
			"items": items,
			"header_icon": sidebar.get("header_icon"),
			"module_onboarding": sidebar.get("module_onboarding"),
			"module": sidebar_doc.module,
			"app": sidebar_doc.app,
		}
	add_user_specific_sidebar(sidebar_items)
	return sidebar_items


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


def add_user_specific_sidebar(sidebar_items):
	sidebars_to_remove = []
	for sidebar in sidebar_items.keys():
		if f"-{frappe.session.user.lower()}" in sidebar:
			sidebars_to_remove.append(sidebar)
	for sidebar in sidebars_to_remove:
		try:
			sidebar_name = sidebar.replace(f"-{frappe.session.user.lower()}", "")
			sidebar_items[sidebar]["label"] = sidebar_items[sidebar_name]["label"]
			sidebar_items[sidebar_name] = sidebar_items.pop(sidebar)
		except KeyError:
			pass
