# Which app owns a doctype, and what it is called in a URL.

# A doctype belongs to the app owning its module, with `frappe` as the floor: an unresolvable
# module never errors, it lands on the desk.

import frappe
from frappe import _
from frappe.boot import get_boot_module_app
from frappe.cache_manager import reset_metadata_version
from frappe.utils.caching import http_cache

OWNER_CACHE_KEY = "shell_doctype_owners"
ADDRESS_CACHE_KEY = "shell_address_table"


def slug(doctype: str) -> str:
	"""`CRM Deal` -> `crm-deal`. The address, not the identity."""
	return frappe.scrub(doctype).replace("_", "-")


def build_doctype_owners() -> dict[str, str]:
	"""`{doctype: app}` over every doctype on the site."""
	# `get_boot_module_app`, not the raw `module_app`: a Module Def created from the UI is in
	# no modules.txt, and the raw map would drop its doctype to the `frappe` floor.
	module_app = get_boot_module_app()
	owners = {}

	# `istable=0`: a child table has no page and no address.
	for name, module in frappe.get_all(
		"DocType", filters={"istable": 0}, fields=["name", "module"], as_list=True
	):
		owners[name] = module_app.get(frappe.scrub(module or ""), "frappe")

	return owners


def get_doctype_owners() -> dict[str, str]:
	"""Cached on `metadata_version`, the framework's own schema-change signal."""
	# Not a `doc_events` hook: `frappe.delete_doc("DocType", ...)` never reaches one, and
	# `reset_metadata_version()` is already on every schema-change path.
	version = frappe.client_cache.get_value("metadata_version") or reset_metadata_version()
	cached = frappe.client_cache.get_value(OWNER_CACHE_KEY)

	if isinstance(cached, dict) and cached.get("version") == version:
		return cached["owners"]

	owners = build_doctype_owners()
	frappe.client_cache.set_value(OWNER_CACHE_KEY, {"version": version, "owners": owners})
	return owners


def clear_doctype_owners():
	frappe.client_cache.delete_value(OWNER_CACHE_KEY)


def metadata_version() -> str:
	"""The framework's own schema-change signal; every cache here hangs off it."""
	return frappe.client_cache.get_value("metadata_version") or reset_metadata_version()


def build_address_table() -> dict:
	"""`{doctype: [slug, module_slug]}` over the whole bench, plus the module names."""
	# Full-bench, so the table is byte-identical for every user and prefix and can leave boot.
	# The module *slug*, so the client never re-implements `frappe.scrub`.
	doctypes = {}
	modules = {}

	for name, module in frappe.get_all(
		"DocType", filters={"istable": 0}, fields=["name", "module"], as_list=True
	):
		module = module or ""
		module_slug = slug(module) if module else ""
		if module_slug:
			modules[module_slug] = module
		doctypes[name] = [slug(name), module_slug]

	return {"doctypes": doctypes, "modules": modules}


def get_address_table() -> dict:
	"""Cached on `metadata_version`, exactly as the owner registry is."""
	version = metadata_version()
	cached = frappe.client_cache.get_value(ADDRESS_CACHE_KEY)

	if isinstance(cached, dict) and cached.get("version") == version:
		return cached["table"]

	table = build_address_table()
	frappe.client_cache.set_value(ADDRESS_CACHE_KEY, {"version": version, "table": table})
	return table


def clear_address_table():
	frappe.client_cache.delete_value(ADDRESS_CACHE_KEY)


@frappe.whitelist(methods=["GET"])
@http_cache(max_age=31536000)
def get_addresses(v: str | None = None) -> dict:
	"""The address table, fetched separately from boot and cached for a year on `metadata_version`."""
	# `methods=["GET"]` is not decoration: `http_cache` only sets its header on a GET.

	# Whitelist excludes only Guest, and this enumerates every doctype; the gate is "may this
	# session enter any prefix", because addressability is permission-independent.
	from .permissions import has_app_permission
	from .registry import get_prefix_registry

	if not any(has_app_permission(app) for app in set(get_prefix_registry().values())):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return get_address_table()


def get_readable_doctypes() -> set[str]:
	"""Every doctype this user may read, in one pass; the single input both filters share."""
	# One bulk read, not per-doctype `has_permission`: that was 3,594 ms against 25 ms, and
	# it imports every controller, so one broken app took down every rail.

	# Shares too: `has_permission` with no doc is True for a doctype shared with the user.
	from frappe.permissions import get_doctypes_with_read
	from frappe.share import get_shared_doctypes

	return set(get_doctypes_with_read()) | set(get_shared_doctypes())


def contents_for_app(app: str, module: str | None = None) -> list[dict]:
	"""What an app contains: its own doctypes, permission-filtered, optionally to one module."""
	# Not the address table: addressability is full-bench and permission-independent;
	# contents are per-app and filtered. Nothing reconciles this with the authored rail.
	table = get_address_table()
	owners = get_doctype_owners()
	readable = get_readable_doctypes()
	entries = []

	for doctype, owner in owners.items():
		if owner != app:
			continue
		address = table["doctypes"].get(doctype)
		if not address:
			continue
		if module and address[1] != module:
			continue
		if doctype not in readable:
			continue

		entries.append({"doctype": doctype, "slug": address[0], "module": address[1]})

	entries.sort(key=lambda entry: entry["doctype"])
	return entries


@frappe.whitelist(methods=["GET"])
def get_contents(app: str, module: str | None = None) -> list[dict]:
	"""An app's contents, or one module's, fetched on arrival at the page that shows them."""
	from .permissions import has_app_permission
	from .registry import get_prefix_registry

	# frappe accepts JSON bodies, so `app` can arrive as a list or a dict and reach `get_hooks`.
	if not isinstance(app, str) or not isinstance(module, str | None):
		frappe.throw(_("Invalid arguments"), frappe.ValidationError)

	# Checked against the registry before `has_app_permission` passes it to `get_hooks(app_name=)`,
	# an importlib call on a caller-supplied name.
	if app not in set(get_prefix_registry().values()):
		frappe.throw(_("No app named {0} is installed").format(app), frappe.DoesNotExistError)

	if not has_app_permission(app):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return contents_for_app(app, module)
