# EXTENSION — how one app's rows join another app's rail; a list operation with no database.

# Contributed keys are namespaced `<app>:<key>` and host keys are untouched: the key is what
# every user edit is filed against, so an identity that moved would detach an arrangement.

# An item whose anchor does not resolve is appended, never dropped: an app cannot pin a host
# it does not ship, so a missing anchor is the expected case.

from frappe.desk.layers import anchor_attempts, place_by_anchors

# A colon cannot occur in an app name, which is a Python module name.
NAMESPACE = ":"


def namespaced(app: str, key: str) -> str:
	return f"{app}{NAMESPACE}{key}"


def extend(base: list[dict], contributions: list[tuple[str, list[dict]]], *, anchorable: bool) -> list[dict]:
	"""The host's list with every other app's rows merged in, as the base of the layer merge."""
	# Place every row first, then anchor: one pass would make an anchor naming another
	# extender's item resolve or not by install order.
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
	# A derived base has keys nobody authored, so an anchor may not name them.
	if anchorable:
		targets |= {item["key"] for item in base if item.get("key")}

	return _anchor(merged, placed, targets)


def _contributed(app: str, row: dict) -> dict | None:
	"""One contributed row, keyed for the merged list."""
	key = row.get("key")
	# A keyless row would namespace to a bare `<app>:` shared with every other keyless row.
	if not key:
		return None

	item = {**row, "key": namespaced(app, key), "app": app}

	# `parent_key` names a sibling in this app's own list, never a host row; nesting into
	# the host is what an anchor's `parent_key` is for.
	if row.get("parent_key"):
		item["parent_key"] = namespaced(app, row["parent_key"])

	return item


def _anchor(merged: list[dict], placed: list[dict], targets: set[str]) -> list[dict]:
	"""Move each contributed root to the first position it asks for that resolves."""
	# Roots only: where a contributed subtree sits is its root's business.
	roots = [(item, anchor_attempts(item.get("anchors"))) for item in placed if not item.get("parent_key")]
	roots = [(item, attempts) for item, attempts in roots if attempts]
	if not roots:
		return merged

	return place_by_anchors(merged, roots, key=_key, target_key=_written_then_own(targets))


def _key(item: dict) -> str | None:
	return item.get("key")


def _written_then_own(targets: set[str]):
	"""Resolve a name as written first and as this app's own second."""
	# Written first, so an anchor aimed at a host resolves to the host; own is only reached
	# when the host has no such key, so it can never shadow one.

	def target_key(item: dict, name: str) -> str | None:
		if name in targets:
			return name

		own = namespaced(item["app"], name)
		return own if own in targets else None

	return target_key
