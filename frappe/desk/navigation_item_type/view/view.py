# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The `View` navigation item type: one view of one doctype, a saved view or a plain view type.

Its payload is `{"view": key}`, and `link_to` is the doctype. The type's three hooks live here:
`can_see` (`navigation_item_resolvers`), `validate_own_row` (`navigation_item_validators`)
and `mark_rows` (`navigation_item_markers`).
"""

import json
import re

import frappe
from frappe import _
from frappe.desk.doctype.doctype_view.key_space import open_views

# `KEY_LENGTH_LIMIT` (60) plus the `-N` suffix `KeySpace.claim` adds; this keeps the payload at 75 B.
KEY_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
KEY_MAX_LENGTH = 64


def can_see(items: list[dict], context) -> list[dict]:
	"""The rows whose doctype the person reads and whose view opens for them: one `Doctype View` query."""
	asked = [(item, (item.get("link_to"), view_key(item.get("payload")))) for item in items]
	asked = [(item, target) for item, target in asked if context.may_read(target[0]) and target[1]]
	opened = open_views([target for _item, target in asked], user=context.user)

	return [item for item, target in asked if target in opened]


def validate_view_row(row: dict, container: str, scope: str, context):
	"""Refuse a row whose view the level cannot show, and store its payload in compact form."""
	label = frappe.bold(row["key"])
	doctype = row.get("link_to")
	key = view_key(row.get("payload"))
	row["payload"] = refuse_a_bad_shape(doctype, row.get("payload"), label)

	if (doctype, key) in open_views([(doctype, key)], user=context.user, own=scope != "site"):
		return

	refuse_an_unopened_view(doctype, key, scope, context.user)


# The hook's contract: the module it names holds `validate_own_row`.
validate_own_row = validate_view_row


def validate_shipped_row(item):
	"""The shape of a View row an app ships; whether its view exists is left alone, as an app's view file can load later."""
	refuse_a_bad_shape(item.link_to, item.payload, frappe.bold(item.key))


def mark_rows(items: list[dict], scope: str) -> dict[str, dict]:
	"""`{key: {"view_deleted": 1}}` for each row whose doctype is gone or whose view no longer opens at `scope`."""
	doctypes = {item.get("link_to") for item in items}
	existing = set(frappe.get_all("DocType", filters={"name": ("in", doctypes)}, pluck="name"))
	targets = [(item.get("link_to"), view_key(item.get("payload"))) for item in items]
	opened = open_views(
		[target for target in targets if target[0] in existing and target[1]], own=scope != "site"
	)

	return {
		item["key"]: {"view_deleted": 1}
		for item, target in zip(items, targets, strict=True)
		if target not in opened
	}


def view_key(payload) -> str | None:
	"""The key in a payload given as text or as an object, or None when there is none."""
	if isinstance(payload, str):
		try:
			payload = json.loads(payload)
		except ValueError:
			return None

	key = payload.get("view") if isinstance(payload, dict) else None
	return key if isinstance(key, str) else None


def refuse_a_bad_shape(doctype: str | None, payload, label: str) -> str:
	"""The payload in compact form, or a refusal: it is exactly `{"view": key}`, and a Single has no views."""
	if isinstance(payload, str):
		try:
			payload = json.loads(payload)
		except ValueError:
			refuse(_("The payload of {0} is not an object.").format(label))

	if not (isinstance(payload, dict) and set(payload) == {"view"}):
		refuse(_("{0} needs a view and nothing else.").format(label))

	key = payload["view"]
	if not (isinstance(key, str) and len(key) <= KEY_MAX_LENGTH and KEY_PATTERN.fullmatch(key)):
		refuse(_("{0} does not name a view.").format(label))

	if doctype and frappe.db.get_value("DocType", doctype, "issingle"):
		refuse(_("A Single doctype has no views."))

	return json.dumps(payload, separators=(",", ":"))


def refuse_an_unopened_view(doctype: str, key: str, scope: str, user: str):
	"""Say why: the maker's own view at the site level, another person's view, or one that is gone."""
	if scope == "site" and (doctype, key) in open_views([(doctype, key)], user=user):
		refuse(_("Publish this view first, so everyone can open it."))

	if frappe.db.exists("Doctype View", {"reference_doctype": doctype, "key": key}):
		refuse(_("You can't open this view."))

	refuse(_("This view no longer exists."))


def refuse(message: str):
	frappe.throw(message, title=_("Not an Arrangement"))
