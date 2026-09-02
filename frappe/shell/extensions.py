# EXTENSION — how one app's rows join another app's rail.
#
# #42364 settled this after taking `mount_on` apart. Desk v1's arrangement was that a
# companion app surrendered its own rail and its apps-screen tile to live inside a host,
# named by one scalar column. That could never say what Payments and Telephony need, since
# each extends ERPNext *or* CRM *or* Helpdesk, and it was unnecessary besides: addresses
# are bench-wide, so a foreign item is an ordinary in-prefix link and nothing has to be
# surrendered to make it work. So an app keeps its own rail and ships one `Rail` record per
# host, each naming that host in `extends` and each able to offer it a different list.
#
# Nothing here reads the database. Every query in this family lives in `navigation.py`, and
# what is left once they are taken out is a list operation: given a host's list and some
# other apps' rows, produce one list. That is worth having on its own, because the ordering
# rules below are where the design actually is.
#
# Two rules carry most of the weight:
#
# 1. Contributed keys are namespaced at merge, `<app>:<key>`, and host keys are untouched.
#    The key is what every user edit is filed against (#42229), so an identity that changed
#    when a second app was installed would silently detach a person's arrangement. Letting
#    the host win and dropping the collision has the same fault from the other side.
#
# 2. An item that cannot be placed is appended, never dropped. An app writes its anchors
#    against a host it does not ship and cannot pin, so a missing anchor is the expected
#    case rather than a broken one. Landing in the wrong place is cosmetic; vanishing is a
#    bug report against the wrong app.
#
# The placement itself is not here. It is `frappe.desk.layers`, beside the layer merge, because
# the overlay endpoints move a person's rows by the same anchors one phase later (#42363) -- and
# `layers.py` is where a list operation with no database under it already lives. What stays here
# is the one thing that differs: how a written name becomes a key, which for a contributed row
# means the host first and this app's own rows second.

from frappe.desk.layers import anchor_attempts, place_by_anchors

# `<app>:<key>`. A colon because it cannot occur in an app name, which is a Python module
# name, and because it reads as a qualifier rather than as part of a slug — `telephony:leads`
# is visibly two things where `telephony-leads` is one.
NAMESPACE = ":"


def namespaced(app: str, key: str) -> str:
	return f"{app}{NAMESPACE}{key}"


def extend(base: list[dict], contributions: list[tuple[str, list[dict]]], *, anchorable: bool) -> list[dict]:
	"""The host's list with every other app's rows merged in.

	`contributions` is `(app, rows)` in installation order, and `base` is the host's own
	list — shipped or derived. The result is the base of the layer merge, not its output:
	the site's arrangement and each person's are laid over this, so a person who reorders a
	host rail gets one row covering the contributed items too (#42364), rather than one row
	per app whose contributions they happened to move.

	`anchorable` says whether the base's keys may be named by an anchor. It is False for a
	*derived* base, whose keys are doctype names nobody authored — an app cannot write an
	anchor against a list the host never wrote down, and a key that looks stable but is a
	side effect of what the reader may see is worse than no key at all. Contributed keys are
	always anchorable, because a contributed row is a shipped row and its key is authored.

	Two passes, and the reason is install order. Placing and anchoring in one pass would
	make an anchor that names another extender's item resolve or not depending on which app
	was installed first, which is a property of a bench and not of either app. So every row
	is placed first, and only then does anything look for a key.
	"""
	merged = [dict(item) for item in base]
	placed = []

	for app, rows in contributions:
		for row in rows:
			item = _contributed(app, row)
			if item is None:
				continue
			merged.append(item)
			placed.append(item)

	if not placed:
		return merged

	targets = {item["key"] for item in placed}
	if anchorable:
		targets |= {item["key"] for item in base if item.get("key")}

	return _anchor(merged, placed, targets)


def _contributed(app: str, row: dict) -> dict | None:
	"""One contributed row, keyed for the merged list.

	`parent_key` is namespaced with the key, so a contributed subtree keeps its own shape and
	travels as a unit. It names a sibling in the app's own list and never a host row: nesting
	*into* the host is what an anchor's `parent_key` is for, and reading one column as
	sometimes-mine-sometimes-theirs would make an app's own hierarchy break the day a host
	happened to ship a row with the same key.

	A row with no key is skipped. `validate_item_keys` already refuses one on any standard
	record, and an extension record is standard — but a keyless row here would namespace to a
	bare `<app>:` that every other keyless row also produced, so it is worth being explicit.
	"""
	key = row.get("key")
	if not key:
		return None

	item = {**row, "key": namespaced(app, key), "app": app}

	if row.get("parent_key"):
		item["parent_key"] = namespaced(app, row["parent_key"])

	return item


def _anchor(merged: list[dict], placed: list[dict], targets: set[str]) -> list[dict]:
	"""Move each contributed root to the first position it asks for that resolves.

	Roots only. A row with a `parent_key` of its own is inside a contributed subtree, and
	where that subtree sits is its root's business -- an anchor on a child would tear the
	subtree apart to satisfy a row that never had a say in the first place.
	"""
	roots = [(item, anchor_attempts(item.get("anchors"))) for item in placed if not item.get("parent_key")]
	roots = [(item, attempts) for item, attempts in roots if attempts]
	if not roots:
		return merged

	return place_by_anchors(merged, roots, key=_key, target_key=_written_then_own(targets))


def _key(item: dict) -> str | None:
	return item.get("key")


def _written_then_own(targets: set[str]):
	"""Resolve a name as written first and as this app's own second.

	Written-first is what makes an anchor aimed at a host resolve to the host, which is the
	case an app is nearly always writing; the own-namespace fallback is what lets an app
	anchor to a row it shipped itself without having to write its own name into its own
	file. It can never shadow a host key, because it is only reached when the host has no
	such key.
	"""

	def target_key(item: dict, name: str) -> str | None:
		if name in targets:
			return name

		own = namespaced(item["app"], name)
		return own if own in targets else None

	return target_key
