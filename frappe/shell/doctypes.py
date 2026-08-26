# Which app owns a doctype, and what it is called in a URL.
#
# #42068: a doctype belongs to the app owning its module, resolved DB-first then
# `modules.txt`, with `frappe` as the floor — an unresolvable module never errors, it
# lands on the framework. Core doctypes stay single-homed at `/apps/desk`.

import frappe
from frappe.cache_manager import reset_metadata_version

OWNER_CACHE_KEY = "shell_doctype_owners"


def slug(doctype: str) -> str:
	"""`CRM Deal` -> `crm-deal`. The address, not the identity."""
	return frappe.scrub(doctype).replace("_", "-")


def build_doctype_owners() -> dict[str, str]:
	"""`{doctype: app}` over every doctype on the site."""
	module_app = frappe.local.module_app or {}
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


def slugs_for_app(app: str) -> dict[str, str]:
	"""`{slug: doctype}` for the doctypes addressable at this app's prefix.

	**Permission-independent, and that is the load-bearing part.** v1's de-slug table
	is keyed on `can_read`, so the address space changes shape per user; two colleagues
	pasting the same URL must not resolve it differently. Access is still refused at
	the record, by ordinary doctype permissions.

	Scoped to one app because a doctype is addressable only inside its owner's prefix
	(#42068), which is also what keeps this small enough to sit in boot.
	"""
	return {slug(doctype): doctype for doctype, owner in get_doctype_owners().items() if owner == app}
