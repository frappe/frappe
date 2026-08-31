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
"""

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

	The map is seeded from the base, so the base hides on the same terms as the layers above it:
	an app may ship an entry off by default, and one row above naming that entry with hiding off
	brings it back. The base used to be the one layer whose hiding was discarded, and seeding it
	removes that special case.

	Both surfaces opt in through the shape of their own base rather than through a flag here. A
	sidebar's rows are built by a key whitelist (`filter_sidebar_items`) that carries `hidden`
	only where a row sets it, so the seed is false for every row that says nothing.
	"""
	resolved = [dict(item) for item in base]
	hidden: dict[str, bool] = {key(item): bool(item.get("hidden")) for item in base}

	for rows in layers:
		resolved = apply_layer(
			resolved, rows, hidden, key=key, apply_row=apply_row, keep_unnamed=keep_unnamed
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

	if not named:
		return items

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
