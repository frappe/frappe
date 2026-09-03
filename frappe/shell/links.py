# The canonical address of a document for a link built outside a session: the owner's prefix.
# It never redirects; an address that changes shape per user is not an address.

import frappe

from . import SHELL_ROOT
from .doctypes import get_address_table, get_doctype_owners
from .registry import declared_prefix, is_modular


def canonical_path(doctype: str, name: str | None = None) -> str:
	"""`/apps/erpnext/accounts/sales-invoice/SI-001` — path only, unquoted."""
	from frappe.utils import quoted

	app = get_doctype_owners().get(doctype, "frappe")
	prefix = declared_prefix(app)

	address = get_address_table()["doctypes"].get(doctype)
	# A doctype not yet in the table still gets a link: the cache lags a new DocType until the version resets.
	slug, module = address if address else (frappe.scrub(doctype).replace("_", "-"), "")

	segments = [SHELL_ROOT, prefix]
	if is_modular(app) and module:
		segments.append(module)
	segments.append(quoted(slug))
	if name:
		segments.append(quoted(name))

	return "/" + "/".join(segments)
