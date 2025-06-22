# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

common_default_keys = ["__default", "__global"]

doctypes_for_mapping = {
	"Assignment Rule",
	"Milestone Tracker",
	"Document Naming Rule",
}


def get_doctype_map_key(doctype, name="*") -> str:
	return frappe.scrub(doctype) + f"_map::{name}"


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
	"last_modified",
	"linked_doctypes",
	"workflow",
	"data_import_column_header_map",
)

wildcard_keys = (
	"document_cache::*",
	"table_columns::*",
	*doctype_map_keys,
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
		for key in [user, *common_default_keys]:
			frappe.client_cache.delete_value(f"defaults::{key}")
	elif frappe.flags.in_install != "frappe":
		frappe.client_cache.delete_keys("defaults::*")


def clear_doctype_cache(doctype=None):
	clear_controller_cache(doctype)
	frappe.client_cache.erase_persistent_caches(doctype=doctype)

	_clear_doctype_cache_from_redis(doctype)
	if hasattr(frappe.db, "after_commit"):
		frappe.db.after_commit.add(lambda: _clear_doctype_cache_from_redis(doctype))
		frappe.db.after_rollback.add(lambda: _clear_doctype_cache_from_redis(doctype))


def _clear_doctype_cache_from_redis(doctype: str | None = None):
	from frappe.desk.notifications import delete_notification_count_for
	from frappe.email.doctype.notification.notification import clear_notification_cache
	from frappe.model.meta import clear_meta_cache

	to_del = ["is_table", "doctype_modules"]

	if doctype:

		def clear_single(dt):
			frappe.clear_document_cache(dt)
			# Wild card for all keys containing this doctype.
			# this can be excessive but this function isn't called often... ideally.
			frappe.client_cache.delete_keys(f"*{dt}*")
			frappe.cache.hdel_names(doctype_cache_keys, dt)
			clear_meta_cache(dt)

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
		for pattern in wildcard_keys:
			to_del += frappe.cache.get_keys(pattern)
		clear_meta_cache()

	clear_notification_cache()
	frappe.cache.delete_value(to_del)


def clear_controller_cache(doctype=None, *, site=None):
	if not doctype:
		frappe.controllers.pop(site or frappe.local.site, None)
		frappe.lazy_controllers.pop(site or frappe.local.site, None)
		return

	if site_controllers := frappe.controllers.get(site or frappe.local.site):
		site_controllers.pop(doctype, None)

	if lazy_site_controllers := frappe.lazy_controllers.get(site or frappe.local.site):
		lazy_site_controllers.pop(doctype, None)


def get_doctype_map(doctype, name, filters=None, order_by=None):
	return frappe.client_cache.get_value(
		get_doctype_map_key(doctype, name),
		generator=lambda: frappe.get_all(doctype, filters=filters, order_by=order_by, ignore_ddl=True),
	)


def clear_doctype_map(doctype, name="*"):
	frappe.client_cache.delete_keys(get_doctype_map_key(doctype, name))


def build_table_count_cache():
	if (
		frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
	):
		return

	if frappe.db.db_type != "sqlite":
		table_name = frappe.qb.Field("table_name").as_("name")
		table_rows = frappe.qb.Field("table_rows").as_("count")
		information_schema = frappe.qb.Schema("information_schema")

		data = (frappe.qb.from_(information_schema.tables).select(table_name, table_rows)).run(as_dict=True)
		counts = {d.get("name").replace("tab", "", 1): d.get("count", None) for d in data}
		frappe.cache.set_value("information_schema:counts", counts)
	else:
		counts = {}
		name = frappe.qb.Field("name")
		type = frappe.qb.Field("type")
		sqlite_master = frappe.qb.Schema("sqlite_master")
		data = frappe.qb.from_(sqlite_master).select(name).where(type == "table").run(as_dict=True)
		for table in data:
			count = frappe.db.sql(f"SELECT COUNT(*) FROM `{table.name}`")[0][0]
			counts[table.name.replace("tab", "", 1)] = count
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


def clear_cache(user: str | None = None, doctype: str | None = None):
	"""Clear **User**, **DocType** or global cache.

	:param user: If user is given, only user cache is cleared.
	:param doctype: If doctype is given, only DocType cache is cleared."""
	import frappe.cache_manager
	import frappe.utils.caching
	from frappe.website.router import clear_routing_cache

	if doctype:
		frappe.cache_manager.clear_doctype_cache(doctype)
		reset_metadata_version()
	elif user:
		frappe.cache_manager.clear_user_cache(user)
	else:  # everything
		# Delete ALL keys associated with this site.
		keys_to_delete = set(frappe.cache.get_keys(""))
		for key in frappe.get_hooks("persistent_cache_keys"):
			keys_to_delete.difference_update(frappe.cache.get_keys(key))
		frappe.cache.delete_value(list(keys_to_delete), make_keys=False)

		reset_metadata_version()
		frappe.local.cache = {}
		frappe.local.new_doc_templates = {}

		for fn in frappe.get_hooks("clear_cache"):
			frappe.get_attr(fn)()

	if (not doctype and not user) or doctype == "DocType":
		frappe.utils.caching._SITE_CACHE.clear()
		frappe.client_cache.clear_cache()

	frappe.local.role_permissions = {}
	if hasattr(frappe.local, "request_cache"):
		frappe.local.request_cache.clear()
	if hasattr(frappe.local, "system_settings"):
		del frappe.local.system_settings
	if hasattr(frappe.local, "website_settings"):
		del frappe.local.website_settings

	clear_routing_cache()


def reset_metadata_version():
	"""Reset `metadata_version` (Client (Javascript) build ID) hash."""
	v = frappe.generate_hash()
	frappe.client_cache.set_value("metadata_version", v)
	return v
