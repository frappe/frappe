# The canonical address of a document, for a link generated OUTSIDE a session.
#
# The prefix is a lens: every doctype is addressable under every prefix, so a URL built
# in a request that has no prefix — an email, a notification, a `safe_exec` script —
# has to pick one. It picks the **owner's**, and never redirects (#42210): a prefix the
# reader may not enter answers 403, because an address that changes shape per user is
# not an address.
#
# Every caller of `get_url_to_form` holds `(doctype, name)` and nothing else, which is
# why this can be one function rather than a threading exercise.

import frappe

from . import SHELL_ROOT
from .doctypes import get_address_table, get_doctype_owners
from .registry import declared_prefix, is_modular


def canonical_path(doctype: str, name: str | None = None) -> str:
	"""`/apps/erpnext/accounts/sales-invoice/SI-001` — path only, unquoted.

	Three segments when the owning app declares `app_modular`, two when it does not,
	and the module is the doctype's **own** module either way (#42211).
	"""
	from frappe.utils import quoted

	app = get_doctype_owners().get(doctype, "frappe")
	prefix = declared_prefix(app)

	address = get_address_table()["doctypes"].get(doctype)
	# A doctype the table has never heard of is still addressable: fall back to the
	# slug rule rather than refusing to build a link. The table is keyed on
	# `metadata_version`, so this is the window between creating a doctype and the
	# cache noticing, not a permanent state.
	slug, module = address if address else (frappe.scrub(doctype).replace("_", "-"), "")

	segments = [SHELL_ROOT, prefix]
	if is_modular(app) and module:
		segments.append(module)
	segments.append(quoted(slug))
	if name:
		segments.append(quoted(name))

	return "/" + "/".join(segments)
