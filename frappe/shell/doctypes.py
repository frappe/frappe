# Which app owns a doctype, and what it is called in a URL.
#
# #42068: a doctype belongs to the app owning its module, resolved DB-first then
# `modules.txt`, with `frappe` as the floor — an unresolvable module never errors, it
# lands on the framework. Core doctypes stay single-homed at `/apps/desk`.

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
	# `get_boot_module_app`, not the raw `frappe.local.module_app`. A Module Def created
	# from the UI to host a custom doctype carries its app in `app_name` and never
	# appears in any modules.txt, so the raw map misses it and the doctype would fall to
	# the `frappe` floor — addressable at /apps/desk instead of its owner's prefix. The
	# helper exists for exactly this question; its docstring names resolving a routed
	# doctype's owning app as the reason.
	module_app = get_boot_module_app()
	owners = {}

	# `istable=0`: a child table has no page and no address, so carrying one would be
	# pure boot weight — and the framework's own prefix has ~320 doctypes, where that
	# weight lands hardest.
	for name, module in frappe.get_all(
		"DocType", filters={"istable": 0}, fields=["name", "module"], as_list=True
	):
		# `frappe` is the floor, deliberately: a doctype whose module cannot be
		# resolved is still addressable, just from the desk.
		owners[name] = module_app.get(frappe.scrub(module or ""), "frappe")

	return owners


def get_doctype_owners() -> dict[str, str]:
	"""Cached, and keyed on the framework's own schema-change signal.

	Invalidation is *not* wired to `doc_events` on DocType, and that is deliberate:
	`frappe.delete_doc("DocType", ...)` never reaches a `doc_events` handler here
	(verified — an `after_delete` hook does not fire on that path), so a deleted
	doctype would stay addressable until the cache lapsed on its own. Nor is
	`frappe.clear_cache(doctype=...)` enough: it clears `client_cache` only for the
	literal doctype "DocType" (`cache_manager.py:311-313`).

	`reset_metadata_version()` is on both of those paths already, so hanging the cache
	off it means every schema change invalidates this for free — including the ones a
	hook of our own would have missed.
	"""
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
	"""The framework's own schema-change signal, and the key everything here hangs off.

	Not a `doc_events` hook on DocType: `frappe.delete_doc("DocType", ...)` never
	reaches one (verified), and `frappe.clear_cache(doctype=...)` clears `client_cache`
	only for the literal doctype "DocType" (`cache_manager.py:311-313`).
	`reset_metadata_version()` is on both paths already.
	"""
	return frappe.client_cache.get_value("metadata_version") or reset_metadata_version()


def build_address_table() -> dict:
	"""`{doctype: [slug, module_slug]}` over the WHOLE bench, plus the module names.

	Full-bench and not per-app, because the prefix is a **lens**: every doctype is
	addressable under every prefix (#42210). That is also what makes this table
	byte-identical for every user and every prefix, which is what lets it leave boot
	for a cacheable fetch.

	The module slug rides beside the doctype slug because a modular app addresses
	`/apps/<app>/<module>/<doctype>/<name>` (#42211). It is the *slug*, not the module
	name, so the client never re-implements `frappe.scrub` and the two halves of the
	address cannot disagree. Names come back separately in `modules`, which is 37
	entries on this bench against 531 doctypes — display data, not address data.

	`istable=0`: a child table has no page and no address.
	"""
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
	"""The address table, fetched separately from boot and cached for a year.

	`#42070`'s translations treatment, for the same reason: the payload varies with
	the site's schema and with nothing else, so `metadata_version` in the query string
	is the only thing that may ever invalidate it. Measured on this bench: 19,235 B as
	`{doctype: slug}`, 25,530 B widened (+33%) — comfortable on a fetch and
	unaffordable inside a 40 KB boot.

	`methods=["GET"]` is not decoration: `http_cache` only sets its header on a GET,
	so a POST would silently answer uncached forever.

	`@frappe.whitelist()` excludes Guest and nobody else, and this enumerates every
	doctype on the site — which desk v1 never handed a Website User. So it carries its
	own gate, at the only grain that is true of a table with no app in it: **may this
	session enter any prefix at all.** Filtering the table itself is not available,
	addressability being permission-independent on purpose — two colleagues must
	resolve a pasted URL identically (#42068).
	"""
	from .permissions import has_app_permission
	from .registry import get_prefix_registry

	if not any(has_app_permission(app) for app in set(get_prefix_registry().values())):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return get_address_table()


def get_readable_doctypes() -> set[str]:
	"""Every doctype this user may read, in ONE pass. The single input both filters share.

	Measured on this bench for an ordinary System User: **3,594 ms** for 553 per-doctype
	`has_permission` calls against **25 ms** for this. The per-doctype loop looked free
	only because it was first measured as Administrator, who short-circuits every check
	— 6 ms, and nothing like what a real user pays. The rail loads on every page, so that
	was 3.6 s of worker time per load.

	It also removes a failure mode outright rather than guarding it: `has_permission`
	imports each doctype's controller, so one app's un-importable module took down the
	rail for *every* app. This reads DocPerm and Custom DocPerm and imports nothing.

	Roles are not the whole answer. `has_permission(doctype, "read")` returns True with
	**no doc passed** when at least one document of that type is shared with the user
	(`permissions.py:206`), so a role-only set silently drops every doctype a user
	reaches purely by sharing. `get_shared_doctypes` is the framework's own bulk answer
	to that question — one query, `user = me OR everyone = 1` — so it costs a query
	rather than a per-doctype check.

	The two sets agree for a user with no shares, which is why the first measurement
	missed this. They differ for Administrator by three doctypes carrying *zero* DocPerm
	rows, which nobody but Administrator could ever read; not offering those is the
	intended reading of "what is offered", and they stay fully addressable.

	This lives here, and `shell/navigation.py` derives an unconverted app's rail from it,
	because two answers to "may this user read this doctype" is exactly the divergence
	#42231 exists to close. Filtering an app's *authored* rows against their declared
	permission bucket is the other half of that rule and belongs to the walking skeleton
	(#42233), which is where authored rows first exist to be filtered.
	"""
	from frappe.permissions import get_doctypes_with_read
	from frappe.share import get_shared_doctypes

	return set(get_doctypes_with_read()) | set(get_shared_doctypes())


def contents_for_app(app: str, module: str | None = None) -> list[dict]:
	"""What an app CONTAINS — its own doctypes, permission-filtered.

	The counterpart of the address table, and deliberately a different list. #42210
	split what `boot.doctype_slugs` conflated: **addressability** is full-bench and
	permission-independent, **contents** are per-app and filtered. A doctype you cannot
	read is still addressable (you get refused at the record, by ordinary doctype
	permissions); it is simply not offered to you.

	`module` narrows it further, for the module landing page a modular app's address
	space now walks up to (#42211 §6).

	This used to be called `navigation_for_app`, and it used to feed the rail. It no
	longer does: the rail is authored navigation, resolved into boot by
	`shell/navigation.py`, while this stays the derived list of what is *in* an app.
	#42357 settled that those are two lists and nothing reconciles them — measured
	across ERPNext, 107 doctypes sit on a module page and not in that module's sidebar
	while 101 sidebar links point outside the module. The app home and the module page
	answer *what does this contain*; the rail answers *what do you do here*.
	"""
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
	"""An app's contents, or one module's, fetched on arrival at the page that shows them.

	Kept as a fetch rather than folded into boot, where the rail went. A module page is a
	destination, and paying one request on arrival is ordinary; a rail click must cost
	none, which is why only the rail moved (#42357).
	"""
	from .permissions import has_app_permission
	from .registry import get_prefix_registry

	# Validate the TYPE at the trust boundary, not merely the value. frappe accepts
	# JSON bodies, so `app` can arrive as a list or a dict and reach `get_hooks`.
	if not isinstance(app, str) or not isinstance(module, str | None):
		frappe.throw(_("Invalid arguments"), frappe.ValidationError)

	# And validate it against the registry BEFORE it reaches `has_app_permission`,
	# which passes it to `get_hooks(app_name=)` — an importlib call on a
	# caller-supplied name. An app that serves no prefix has no contents to ask
	# about, so this costs nothing real.
	if app not in set(get_prefix_registry().values()):
		frappe.throw(_("No app named {0} is installed").format(app), frappe.DoesNotExistError)

	if not has_app_permission(app):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return contents_for_app(app, module)
