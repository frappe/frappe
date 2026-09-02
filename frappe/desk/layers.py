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

Desk v2 arranges by a fourth rule, `anchored`. Its writer saves a person's move as an *anchor* --
next to this row -- rather than as a position, so a layer names only what moved and everything
else stays where the layer below it put it. The two rules cannot both be right for one surface:
v1's positions the whole list from the rows a layer names, and desk v2's moves the named rows
within a list it otherwise leaves alone. It is a parameter defaulted off, so v1's two callers are
unchanged.

Placement is at the bottom of this file rather than beside the merge, because the layer merge is
not its only caller: `frappe/shell/extensions.py` places one app's rows into another app's rail by
the same anchors, before any layer applies. Those are different phases of one resolution and they
share exactly this -- given a list and some rows that want to sit next to something in it, produce
one list.
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

	`anchored` reads each row's `anchors` and moves only the rows that carry one, leaving the rest
	of the list alone. It supersedes `keep_unnamed`, which has nothing left to decide once an
	unnamed entry simply stays where it is.

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
			# Read off the row rather than the entry. An anchor says where this *layer* wants the
			# item, so it is the layer's own statement and not part of the item -- `apply_row`
			# carries it into the entry only if the layer also declared it an override, which is
			# a site turning a contributed row's anchor off and a different thing entirely.
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
	"""One layer applied by anchors: the list below, updated in place, then the moves.

	The list keeps the order it arrived in. That is the whole difference from `apply_layer`'s
	other half, and it is what makes a newly-shipped item land at its shipped position rather
	than after everything a person has arranged: nothing but an anchored row moves, so an item
	nobody moved is exactly where the layer below it put it.

	A row the layer *added* has no place in that list to keep, so it is appended, in the order
	the layer wrote its rows. Its anchors then move it like any other, and an added row whose
	anchor does not resolve stays at the end -- the one case where the fallback is not a shipped
	position, because it has none.
	"""
	merged = [by_key[key(item)] for item in items]
	merged += [by_key[row_key] for row_key in arranged if row_key not in base_keys]

	placed = [(by_key[row_key], attempts[row_key]) for row_key in arranged if attempts.get(row_key)]
	if not placed:
		return merged

	# An overlay row was written against the very list it is being applied to, so a name it wrote
	# is a key or it is nothing.
	present = {key(item) for item in merged}
	return place_by_anchors(
		merged, placed, key=key, target_key=lambda _item, name: name if name in present else None
	)


# Placement
#
# An anchor is `{"after": key}`, `{"before": key}` or `{"parent_key": key}`, and a row carries an
# ordered list of them: the first that resolves wins, and a row none of whose anchors resolve is
# left where it already is. Two callers, two phases, one rule.
#
# What differs between them is only how a written name becomes a key in the list, so that is the
# parameter. An overlay row names a key as it stands, because it was written against the very list
# it is being applied to. A contributed row was written against a host its app cannot see, so its
# names resolve to the host first and to the app's own namespaced rows second (#42364).


Attempt = dict
# `(item, written name) -> the key in the list it names, or a falsy value if there is none.`
TargetKey = Callable[[Row, str], Any]


def anchor_attempts(raw: Any) -> list[Attempt]:
	"""A row's stored anchors, as an ordered list of well-formed attempts.

	A malformed list is no anchors rather than an error. On a contributed row the reader of any
	complaint would be the wrong person, since an app writes anchors against a host it cannot see;
	on an overlay row the writer is an endpoint, so a malformed one is a bug that shows up as an
	item that did not move rather than as a save that failed. Either way the row still appears.

	An attempt naming both `after` and `before` names two positions and so names none. It is
	dropped rather than resolved by precedence, because picking one would make a typo into a
	silent placement nobody wrote.
	"""
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
	"""Move each row in `placed` to the first position it asks for that resolves.

	`placed` pairs a row that is already in `items` with its ordered attempts. It is a pair rather
	than a read off the row because the two callers store anchors in different places: an
	extension reads them off the contributed row, and a layer reads them off the layer row rather
	than off the entry it resolved to.

	`anchored` is the cycle guard and the whole of it: it records what each moved row was moved
	next to, so an anchor whose target chain leads back to the row being placed is refused and the
	next anchor is tried. Two rows naming each other is the case, and neither an exception nor an
	arbitrary winner would be right -- falling through to the next anchor, and then to leaving the
	row alone, is the same answer this gives every other unresolvable one.
	"""
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
	"""Move `item` and everything under it to where the anchor says.

	The row travels with its **subtree**. The list is flat and the tree is `parent_key`, so
	moving a section on its own leaves its children sitting where they were: the tree is still
	right, since a reader groups by `parent_key`, but the flat order no longer has children
	following their parent -- and that invariant is what every reader of this list assumes,
	including the editor that will read it straight back and draw it in order.

	`after` and `before` put a row beside another, so it takes that row's parent: beside means
	beside, and a sibling that landed at a different depth would be somewhere else entirely. An
	explicit `parent_key` wins over that, for the writer that means *under this section, next to
	that row*.

	A `parent_key` with no `after` or `before` lands the row after the last child that parent
	already has, or immediately after the parent when it has none -- the position appending to
	that section would give, which is what it asked for.
	"""
	beside = anchor["after"] or anchor["before"]
	target = beside or anchor["parent_key"]
	if _index_of(items, target, key=key) is None:
		# Unreachable as long as an anchor only ever resolves against a key that is in the list,
		# which is what `target_key` promises. Checked anyway because one caller is boot: an
		# exception here would blank the shell over a misplaced navigation row.
		return

	block = _subtree(items, item, key=key)

	# An anchor naming a row inside the subtree being moved has nowhere to land, because the
	# target travels with it. Refused rather than resolved, which is what the cycle guard does
	# with the same shape of request one level up.
	if any(entry is not item and key(entry) == target for entry in block):
		return

	for entry in block:
		items.pop(_position_of(items, entry))

	if beside:
		parent = anchor["parent_key"]
		if parent is None:
			parent = items[_index_of(items, beside, key=key)].get("parent_key")
		item["parent_key"] = parent
		# `after` clears the target's own subtree, for the same reason the moving row brings its
		# own: landing between a row and its children is not a position anybody can mean.
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
	"""`root` and every key under it.

	Grown to a fixpoint rather than in one pass, so it does not depend on a parent preceding its
	children -- which is the very invariant this exists to keep, and so is not one to assume
	while keeping it.
	"""
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
	"""Where this exact row is. By identity, not by equality: `list.remove` takes the first row
	that compares equal, which is the right one only for as long as no two rows can match."""
	return next(index for index, entry in enumerate(items) if entry is item)
