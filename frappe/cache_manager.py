# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

common_default_keys = ["__default", "__global"]

doctypes_for_mapping = {
	"Energy Point Rule",
	"Assignment Rule",
	"Milestone Tracker",
	"Document Naming Rule",
}


def get_doctype_map_key(doctype):
	return frappe.scrub(doctype) + "_map"


doctype_map_keys = tuple(map(get_doctype_map_key, doctypes_for_mapping))

bench_cache_keys = ("assets_json",)

global_cache_keys = (
	"app_hooks",
	"installed_apps",
	"all_apps",
	"app_modules",
	"installed_app_modules",
	"module_app",
	"module_installed_app",
	"system_settings",
	"scheduler_events",
	"time_zone",
	"webhooks",
	"active_domains",
	"active_modules",
	"assignment_rule",
	"server_script_map",
	"wkhtmltopdf_version",
	"domain_restricted_doctypes",
	"domain_restricted_pages",
	"information_schema:counts",
	"db_tables",
	"server_script_autocompletion_items",
	*doctype_map_keys,
)

user_cache_keys = (
	"bootinfo",
	"user_recent",
	"roles",
	"user_doc",
	"lang",
	"defaults",
	"user_permissions",
	"home_page",
	"linked_with",
	"desktop_icons",
	"portal_menu_items",
	"user_perm_can_read",
	"has_role:Page",
	"has_role:Report",
	"desk_sidebar_items",
	"contacts",
)

doctype_cache_keys = (
	"doctype_meta",
	"doctype_form_meta",
	"table_columns",
	"last_modified",
	"linked_doctypes",
	"notifications",
	"workflow",
	"data_import_column_header_map",
)


def clear_user_cache(user=None):
	from frappe.desk.notifications import clear_notifications

	# this will automatically reload the global cache
	# so it is important to clear this first
	clear_notifications(user)

	if user:
		frappe.cache.hdel_names(user_cache_keys, user)
		frappe.cache.delete_keys("user:" + user)
		clear_defaults_cache(user)
	else:
		frappe.cache.delete_key(user_cache_keys)
		clear_defaults_cache()
		clear_global_cache()


def clear_domain_cache(user=None):
	domain_cache_keys = ("domain_restricted_doctypes", "domain_restricted_pages")
	frappe.cache.delete_value(domain_cache_keys)


def clear_global_cache():
	from frappe.website.utils import clear_website_cache

	clear_doctype_cache()
	clear_website_cache()
	frappe.cache.delete_value(global_cache_keys + bench_cache_keys)
	frappe.setup_module_map()


def clear_defaults_cache(user=None):
	if user:
		frappe.cache.hdel("defaults", [user, *common_default_keys])
	elif frappe.flags.in_install != "frappe":
		frappe.cache.delete_value("defaults")


def clear_doctype_cache(doctype=None):
	clear_controller_cache(doctype)

	_clear_doctype_cache_from_redis(doctype)
	if hasattr(frappe.db, "after_commit"):
		frappe.db.after_commit.add(lambda: _clear_doctype_cache_from_redis(doctype))
		frappe.db.after_rollback.add(lambda: _clear_doctype_cache_from_redis(doctype))


def _clear_doctype_cache_from_redis(doctype: str | None = None):
	from frappe.desk.notifications import delete_notification_count_for

	to_del = ["is_table", "doctype_modules"]

	if doctype:

		def clear_single(dt):
			frappe.clear_document_cache(dt)
			frappe.cache.hdel_names(doctype_cache_keys, dt)

		clear_single(doctype)

		# clear all parent doctypes
		for dt in frappe.get_all(
			"DocField", "parent", dict(fieldtype=["in", frappe.model.table_fields], options=doctype)
		):
			clear_single(dt.parent)

		# clear all parent doctypes
		if not frappe.flags.in_install:
			for dt in frappe.get_all(
				"Custom Field", "dt", dict(fieldtype=["in", frappe.model.table_fields], options=doctype)
			):
				clear_single(dt.dt)

		# clear all notifications
		delete_notification_count_for(doctype)

	else:
		# clear all
		to_del += doctype_cache_keys
		to_del += frappe.cache.get_keys("document_cache::")

	frappe.cache.delete_value(to_del)


def clear_controller_cache(doctype=None):
	if not doctype:
		frappe.controllers.pop(frappe.local.site, None)
		return

	if site_controllers := frappe.controllers.get(frappe.local.site):
		site_controllers.pop(doctype, None)


def get_doctype_map(doctype, name, filters=None, order_by=None):
	return frappe.cache.hget(
		get_doctype_map_key(doctype),
		name,
		lambda: frappe.get_all(doctype, filters=filters, order_by=order_by, ignore_ddl=True),
	)


def clear_doctype_map(doctype, name):
	frappe.cache.hdel(frappe.scrub(doctype) + "_map", name)


def build_table_count_cache():
	if (
		frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
	):
		return

	table_name = frappe.qb.Field("table_name").as_("name")
	table_rows = frappe.qb.Field("table_rows").as_("count")
	information_schema = frappe.qb.Schema("information_schema")

	data = (frappe.qb.from_(information_schema.tables).select(table_name, table_rows)).run(as_dict=True)
	counts = {d.get("name").replace("tab", "", 1): d.get("count", None) for d in data}
	frappe.cache.set_value("information_schema:counts", counts)

	return counts


def build_domain_restricted_doctype_cache(*args, **kwargs):
	if (
		frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
	):
		return
	active_domains = frappe.get_active_domains()
	doctypes = frappe.get_all("DocType", filters={"restrict_to_domain": ("IN", active_domains)})
	doctypes = [doc.name for doc in doctypes]
	frappe.cache.set_value("domain_restricted_doctypes", doctypes)

	return doctypes


def build_domain_restricted_page_cache(*args, **kwargs):
	if (
		frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
	):
		return
	active_domains = frappe.get_active_domains()
	pages = frappe.get_all("Page", filters={"restrict_to_domain": ("IN", active_domains)})
	pages = [page.name for page in pages]
	frappe.cache.set_value("domain_restricted_pages", pages)

	return pages
