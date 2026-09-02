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

import json

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
	where that subtree sits is its root's business — an anchor on a child would tear the
	subtree apart to satisfy a row that never had a say in the first place.

	`anchored` is the cycle guard and the whole of it: it records what each moved row was
	moved next to, so an anchor whose target chain leads back to the row being placed is
	refused and the next anchor is tried. Two apps naming each other is the case, and neither
	an exception nor an arbitrary winner would be right — falling through to the next anchor,
	and then to the append, is the same answer the design gives every other unresolvable one.
	"""
	anchored: dict[str, str] = {}

	for item in placed:
		if item.get("parent_key"):
			continue

		attempt = _first_resolving(item, targets, anchored)
		if attempt is None:
			continue

		_place(merged, item, attempt)
		anchored[item["key"]] = attempt["target"]

	return merged


def _first_resolving(item: dict, targets: set[str], anchored: dict[str, str]) -> dict | None:
	"""The first of this row's anchors whose every named key is present and not circular."""
	for anchor in _attempts(item):
		resolved = _resolve(item, anchor, targets, anchored)
		if resolved:
			return resolved

	return None


def _attempts(item: dict) -> list[dict]:
	"""This row's anchors, as an ordered list of well-formed attempts.

	A malformed list is no anchors rather than an error. The rows are authored by an app
	against a host it cannot see, so the reader of any complaint would be the wrong person;
	the row still appears, at the end, which is what an app with no anchors gets anyway.

	An attempt naming both `after` and `before` names two positions and so names none. It is
	dropped rather than resolved by precedence, because picking one would make a typo into a
	silent placement nobody wrote.
	"""
	try:
		anchors = json.loads(item.get("anchors") or "[]")
	except (TypeError, ValueError):
		return []

	if not isinstance(anchors, list):
		return []

	attempts = []

	for anchor in anchors:
		if not isinstance(anchor, dict):
			continue

		after, before, parent = anchor.get("after"), anchor.get("before"), anchor.get("parent_key")
		if after and before:
			continue
		if not (after or before or parent):
			continue

		attempts.append({"after": after, "before": before, "parent_key": parent})

	return attempts


def _resolve(item: dict, anchor: dict, targets: set[str], anchored: dict[str, str]) -> dict | None:
	"""One attempt against the finished list, or None if any key it names is not there.

	A key is read as written first and as this app's own second. Written-first is what makes
	an anchor aimed at a host resolve to the host, which is the case an app is nearly always
	writing; the own-namespace fallback is what lets an app anchor to a row it shipped itself
	without having to write its own name into its own file. It can never shadow a host key,
	because it is only reached when the host has no such key.
	"""
	app = item["app"]
	resolved = {"after": None, "before": None, "parent_key": None, "target": None}

	for field in ("after", "before", "parent_key"):
		name = anchor.get(field)
		if not name:
			continue

		key = _target_key(app, name, targets)
		if key is None:
			return None

		if _leads_back(key, item["key"], anchored):
			return None

		resolved[field] = key

	resolved["target"] = resolved["after"] or resolved["before"] or resolved["parent_key"]
	return resolved


def _target_key(app: str, name: str, targets: set[str]) -> str | None:
	if name in targets:
		return name

	own = namespaced(app, name)
	return own if own in targets else None


def _leads_back(target: str, key: str, anchored: dict[str, str]) -> bool:
	"""Whether following what each row was anchored to gets back to `key`."""
	seen = set()

	while target and target not in seen:
		if target == key:
			return True
		seen.add(target)
		target = anchored.get(target)

	return False


def _place(merged: list[dict], item: dict, anchor: dict):
	"""Move `item` to where the anchor says, and give it the parent that implies.

	`after` and `before` put a row beside another, so it takes that row's parent: beside
	means beside, and a sibling that landed at a different depth would be somewhere else
	entirely. An explicit `parent_key` wins over that, for the app that means *under this
	section, next to that row*.

	A `parent_key` with no `after` or `before` lands the row after the last child that parent
	already has, or immediately after the parent when it has none — the position an app would
	get by appending to that section, which is what it asked for.
	"""
	beside = anchor["after"] or anchor["before"]
	target = _index_of(merged, beside or anchor["parent_key"])
	if target is None:
		# Unreachable as long as an anchor only ever resolves against a key that is in the list,
		# which is what `targets` is. Checked anyway because the caller is boot: an exception here
		# would blank the shell over a misplaced navigation row.
		return

	merged.pop(_position_of(merged, item))

	if beside:
		at = _index_of(merged, beside)
		parent = anchor["parent_key"]
		if parent is None:
			parent = merged[at].get("parent_key")
		item["parent_key"] = parent
		merged.insert(at + 1 if anchor["after"] else at, item)
		return

	item["parent_key"] = anchor["parent_key"]
	merged.insert(_last_child(merged, anchor["parent_key"]) + 1, item)


def _index_of(merged: list[dict], key: str) -> int | None:
	return next((index for index, entry in enumerate(merged) if entry.get("key") == key), None)


def _position_of(merged: list[dict], item: dict) -> int:
	"""Where this exact row is. By identity, not by equality: `list.remove` takes the first row
	that compares equal, which is the right one only for as long as no two rows can match."""
	return next(index for index, entry in enumerate(merged) if entry is item)


def _last_child(merged: list[dict], parent: str) -> int:
	"""The index of `parent`'s last child, or of `parent` itself when it has none."""
	at = _index_of(merged, parent)

	for index, entry in enumerate(merged):
		if entry.get("parent_key") == parent:
			at = index

	return at
