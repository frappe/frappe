# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""The layer merge, written once for every navigation surface that has layers.

A navigation surface is an ordered list that more than one party can arrange: an app ships an
arrangement, the site lays its own over that, and a user lays theirs over both. The sidebar and
the dock are both such surfaces, and they resolve by the same rule: later layers win, for order
and for hiding, and a layer moves only what it names.

Three things differ between the two, and each is a parameter:

1. What identifies a row. A sidebar item is identified by `item_key`, which has to handle rows
   that point nowhere. A dock entry is identified by what it points at, since an entry always
   points somewhere and there is no stored key to fall back on.
2. What a row does to the entry it names. Both surfaces let a row add an entry, override one
   already in the list, or name one that is no longer there, but what a row may say differs, so
   each supplies its own function.
3. Whether an entry no layer named survives. The sidebar keeps it, so an app adding an item
   reaches a user who has already rearranged. The dock drops it: a saved layer is the rail, so an
   app's later addition waits in the manager to be added rather than appearing on a rail someone
   has already arranged.

None of those is the merge itself, so the merge lives here and they are passed in as `key`,
`apply_row` and `keep_unnamed`.

Desk v2 arranges by a fourth rule, `anchored`: a layer moves only the rows that carry an anchor.
Placement is at the bottom, shared with `frappe/shell/extensions.py`, which places by the same anchors.
"""

import json
from collections.abc import Callable
from typing import Any

# A row, or an already-resolved entry. Sidebar rows are child documents and dock rows are plain
# dicts. Both support `.get`, which is all this module needs.
Row = Any

# `(row, entry_so_far | None) -> entry | None`. See `resolve_layers`.
ApplyRow = Callable[[Row, dict | None], dict | None]

Key = Callable[[Row], str]


def resolve_layers(
	base: list[dict],
	layers: list[list[Row]],
	*,
	key: Key,
	apply_row: ApplyRow,
	keep_unnamed: bool = True,
	anchored: bool = False,
) -> tuple[list[dict], dict[str, bool]]:
	"""Fold each layer into the one below it. Later layers win, for order and for hiding.

	`base` is the arrangement the layers are laid over, which is what an app ships.

	`key` identifies a row and a resolved entry, and must return the same value for both: it is
	what a layer row names when it names an entry, whichever side it is read from.

	`apply_row` says what one row does to the entry it names. It is given the row and the entry as
	resolved so far, and returns the entry that replaces it.

	Its two `None` values mean different things. `None` passed in is a question: the list holds no
	entry under this key, so what should happen? `None` returned is an answer: skip this row,
	because it says nothing this list can act on.

	It returns the resolved list and the hidden map. The map spans every layer and is not applied
	here. Hiding is resolved across all the layers before anything acts on it, which is what makes
	un-hiding possible: a user's `hidden: 0` has to find the entry the site hid still in the list.
	What to do with an entry left hidden is up to the surface: a sidebar drops it, a dock renders
	it as hidden.

	`keep_unnamed` says what happens to an entry the layer never mentioned: kept after the ones it
	did name (the sidebar), or dropped (the dock). See `apply_layer`.

	`anchored` moves only the rows that carry an anchor and supersedes `keep_unnamed`.

	The map is seeded from the base, so the base hides on the same terms as the layers above it:
	an app may ship an entry off by default, and one row above naming that entry with hiding off
	brings it back. The base used to be the one layer whose hiding was discarded, and seeding it
	removes that special case.

	The sidebar opts out through the shape of its own base rather than a flag here. Its rows are
	built through a key whitelist (`filter_sidebar_items`) that omits `hidden`, so a sidebar base
	dict never carries one and the seed is always false.
	"""
	resolved = [dict(item) for item in base]
	hidden: dict[str, bool] = {key(item): bool(item.get("hidden")) for item in base}

	for rows in layers:
		resolved = apply_layer(
			resolved,
			rows,
			hidden,
			key=key,
			apply_row=apply_row,
			keep_unnamed=keep_unnamed,
			anchored=anchored,
		)

	return resolved, hidden


def apply_layer(
	items: list[dict],
	rows: list[Row],
	hidden: dict[str, bool],
	*,
	key: Key,
	apply_row: ApplyRow,
	keep_unnamed: bool = True,
	anchored: bool = False,
) -> list[dict]:
	"""Apply one layer's arrangement to `items`. Mutates `hidden`, which spans the layers.

	Both sides are matched by `key`, which reads the same columns from a stored row as from a
	resolved entry, so a rename that rewrote both leaves them matching and neither side needs
	re-keying.

	A layer that named nothing says nothing, whatever `keep_unnamed` is. Dropping the tail on an
	empty layer would empty the surface, but an empty layer means no opinion.
	"""
	by_key = {key(item): item for item in items}
	# Captured before the loop, which writes added rows into `by_key`. Used to tell an
	# arrangement from a set of appends, below.
	base_keys = set(by_key)
	arranged: list[str] = []
	named: set[str] = set()
	attempts: dict[str, list[dict]] = {}

	for row in rows:
		row_key = key(row)
		# An entry named twice means the client sent it twice. The first position wins, because
		# the alternative is rendering it twice.
		if row_key in named:
			continue

		entry = apply_row(row, by_key.get(row_key))
		if entry is None:
			# The row names nothing the list holds: an item the app deleted, or one this user
			# cannot see. Skip it rather than raising or inventing an entry.
			continue

		by_key[row_key] = entry
		hidden[row_key] = bool(row.get("hidden"))
		arranged.append(row_key)
		named.add(row_key)

		if anchored:
			# Off the row, not the entry: an anchor is the layer's own statement, not part of the item.
			attempts[row_key] = anchor_attempts(row.get("anchors"))

	if not named:
		return items

	if anchored:
		return anchor_layer(items, by_key, base_keys, arranged, attempts, key=key)

	arranged_items = [by_key[row_key] for row_key in arranged]
	# Entries the layer never named. The sidebar keeps them after the ones it did name, so an app
	# adding an item still reaches someone who has already rearranged. The dock drops them,
	# because a saved layer is the rail, so an app's later addition waits in the manager rather
	# than appearing on a rail someone has already arranged. Nothing the layer was shown is lost,
	# since a dock layer names every entry it was shown, hidden ones included, and the result is a
	# rail that does not change on its own.
	if not keep_unnamed:
		return arranged_items

	unnamed = [item for item in items if key(item) not in named]

	# A layer whose every row is an addition the base does not hold is not an arrangement, it is a
	# set of appends, and an append belongs at the end.
	#
	# The distinction matters because the two writers produce different shapes. Saving an
	# arrangement names every row it was shown, so it positions the whole surface and the rule
	# above is right. `add_site_sidebar_item` names one row, and reading that as an arrangement
	# put the row first: creating a shared workspace moved it to the top of its module's sidebar
	# for the whole site, and, because a module opens on the first item of its sidebar, silently
	# changed what the module opened on.
	#
	# A layer that names even one base row is an arrangement again, so a row appended to a layer
	# somebody arranged stays where `append` put it, which is last among the rows it names.
	if arranged and all(row_key not in base_keys for row_key in arranged):
		return unnamed + arranged_items

	return arranged_items + unnamed


def anchor_layer(
	items: list[dict],
	by_key: dict[str, dict],
	base_keys: set[str],
	arranged: list[str],
	attempts: dict[str, list[dict]],
	*,
	key: Key,
) -> list[dict]:
	"""One layer applied by anchors: the list below, updated in place, then the moves."""
	# Nothing but an anchored row moves, so a newly shipped item lands at its shipped position.
	# An added row has no place to keep, so it is appended, then moved like any other.
	merged = [by_key[key(item)] for item in items]
	merged += [by_key[row_key] for row_key in arranged if row_key not in base_keys]

	placed = [(by_key[row_key], attempts[row_key]) for row_key in arranged if attempts.get(row_key)]
	if not placed:
		return merged

	# An overlay row was written against this very list, so a name it wrote is a key or nothing.
	present = {key(item) for item in merged}
	return place_by_anchors(
		merged, placed, key=key, target_key=lambda _item, name: name if name in present else None
	)


# Placement
#
# An anchor is `{"after": key}`, `{"before": key}` or `{"parent_key": key}`; the first that
# resolves wins. The callers differ only in how a written name becomes a key, so that is the parameter.


Attempt = dict
# `(item, written name) -> the key in the list it names, or a falsy value if there is none.`
TargetKey = Callable[[Row, str], Any]


def anchor_attempts(raw: Any) -> list[Attempt]:
	"""A row's stored anchors, as an ordered list of well-formed attempts; malformed is no anchors."""
	# An attempt naming both `after` and `before` names two positions and so names none.
	try:
		anchors = json.loads(raw or "[]") if isinstance(raw, str) else (raw or [])
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


def place_by_anchors(
	items: list[dict],
	placed: list[tuple[dict, list[Attempt]]],
	*,
	key: Key,
	target_key: TargetKey,
) -> list[dict]:
	"""Move each row in `placed` to the first position it asks for that resolves."""
	# `anchored` is the cycle guard: an anchor whose target chain leads back to the row being
	# placed is refused and the next attempt is tried.
	anchored: dict[str, str] = {}

	for item, attempts in placed:
		attempt = _first_resolving(item, attempts, key=key, target_key=target_key, anchored=anchored)
		if attempt is None:
			continue

		_place(items, item, attempt, key=key)
		anchored[key(item)] = attempt["target"]

	return items


def _first_resolving(
	item: dict, attempts: list[Attempt], *, key: Key, target_key: TargetKey, anchored: dict[str, str]
) -> dict | None:
	"""The first of this row's anchors whose every named key is present and not circular."""
	for attempt in attempts:
		resolved = _resolve(item, attempt, key=key, target_key=target_key, anchored=anchored)
		if resolved:
			return resolved

	return None


def _resolve(
	item: dict, attempt: Attempt, *, key: Key, target_key: TargetKey, anchored: dict[str, str]
) -> dict | None:
	"""One attempt against the finished list, or None if any key it names is not there."""
	resolved = {"after": None, "before": None, "parent_key": None, "target": None}

	for field in ("after", "before", "parent_key"):
		name = attempt.get(field)
		if not name:
			continue

		target = target_key(item, name)
		if not target:
			return None

		if _leads_back(target, key(item), anchored):
			return None

		resolved[field] = target

	resolved["target"] = resolved["after"] or resolved["before"] or resolved["parent_key"]
	return resolved


def _leads_back(target: str, key: str, anchored: dict[str, str]) -> bool:
	"""Whether following what each row was anchored to gets back to `key`."""
	seen = set()

	while target and target not in seen:
		if target == key:
			return True
		seen.add(target)
		target = anchored.get(target)

	return False


def _place(items: list[dict], item: dict, anchor: dict, *, key: Key):
	"""Move `item` and everything under it to where the anchor says."""
	# The subtree travels too: the list is flat, and every reader assumes children follow their parent.
	# Beside means beside, so `after`/`before` take the target's parent; an explicit `parent_key` wins.
	beside = anchor["after"] or anchor["before"]
	target = beside or anchor["parent_key"]
	if _index_of(items, target, key=key) is None:
		# Unreachable while `target_key` keeps its promise; checked because one caller is boot.
		return

	block = _subtree(items, item, key=key)

	# An anchor naming a row inside the moving subtree has nowhere to land.
	if any(entry is not item and key(entry) == target for entry in block):
		return

	for entry in block:
		items.pop(_position_of(items, entry))

	if beside:
		parent = anchor["parent_key"]
		if parent is None:
			parent = items[_index_of(items, beside, key=key)].get("parent_key")
		item["parent_key"] = parent
		# `after` clears the target's own subtree: landing between a row and its children is no position.
		at = _end_of(items, beside, key=key) + 1 if anchor["after"] else _index_of(items, beside, key=key)
	else:
		item["parent_key"] = anchor["parent_key"]
		# Appending to a section is landing after everything already in it.
		at = _end_of(items, anchor["parent_key"], key=key) + 1

	items[at:at] = block


def _subtree(items: list[dict], item: dict, *, key: Key) -> list[dict]:
	"""`item` and every row beneath it, in the order they already sit in."""
	inside = _beneath(items, key(item), key=key)

	return [entry for entry in items if key(entry) in inside]


def _end_of(items: list[dict], root: str, *, key: Key) -> int:
	"""The index of the last row in `root`'s subtree, or of `root` itself when it has none."""
	inside = _beneath(items, root, key=key)

	return max(index for index, entry in enumerate(items) if key(entry) in inside)


def _beneath(items: list[dict], root: str, *, key: Key) -> set[str]:
	"""`root` and every key under it, grown to a fixpoint so a parent need not precede its children."""
	inside = {root}

	while True:
		found = {
			key(entry) for entry in items if entry.get("parent_key") in inside and key(entry) not in inside
		}
		if not found:
			break
		inside |= found

	return inside


def _index_of(items: list[dict], name: str, *, key: Key) -> int | None:
	return next((index for index, entry in enumerate(items) if key(entry) == name), None)


def _position_of(items: list[dict], item: dict) -> int:
	"""Where this exact row is, by identity: `list.remove` takes the first row that compares equal."""
	return next(index for index, entry in enumerate(items) if entry is item)
