# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""The layer merge, written once for every navigation surface that has layers.

A navigation surface is an ordered list that more than one party gets an opinion about: an app
ships an arrangement, the site lays its own over that, and a person lays theirs over both. The
sidebar and the dock are both that, and the rule they resolve by is the same rule -- later
layers win, on order and on hiding alike, and a layer moves only what it names.

What differs between the two is small enough to be a parameter:

- **what identifies a row.** A sidebar item is identified by `item_key`, which has to cope with
  rows that point nowhere. A dock entry is identified by what it points at, which is the
  degenerate case -- an entry always points somewhere, so there is no stored key to fall back
  on.
- **what a row does to the entry it names.** Both surfaces let a row add an entry, state an
  opinion about one already in the list, or name one that is no longer there at all -- but what
  a row may say differs, so each supplies its own.
- **whether an entry no layer named survives.** The sidebar keeps it, so an app adding an item
  reaches somebody who has already rearranged. The dock drops it: a saved layer *is* the rail,
  and an app's later addition waits in the manager to be added rather than landing on a rail
  somebody has already settled.

None of those is the merge, which is why the merge lives here and they are passed in as
`key`, `apply_row` and `keep_unnamed`.
"""

from collections.abc import Callable
from typing import Any

# A row, or an already-resolved entry. Sidebar rows are child documents and dock rows are plain
# dicts; both answer `.get`, which is all this module asks of either.
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
	"""Fold each layer into the one below it. Later layers win, on order and on hiding alike.

	`base` is the arrangement the layers are laid over -- what an app ships.

	`key` identifies a row and a resolved entry alike, and has to answer the same for both: it
	is what a layer row names when it names an entry, read off whichever side it is handed.

	`apply_row` says what one row does to the entry it names. It is given the row and the entry
	as resolved so far, and returns the entry that takes its place.

	Its two `None`s are unrelated, which is worth reading twice: `None` *in* is a question --
	the list holds no entry under this key, what do you want to do about that? `None` *out* is
	an answer -- skip this row, it says nothing this list can act on.

	Returns the resolved list **and** the hidden map, which spans every layer and is deliberately
	not applied here. Hiding is resolved across all the layers before anybody acts on it, which
	is what makes un-hiding possible at all: a user's `hidden: 0` has to find the entry the site
	hid still in the list to say anything about it. What to do with an entry that is left hidden
	is then the surface's own question -- a sidebar drops it, a dock renders it as hidden.

	`keep_unnamed` says what happens to an entry the layer never mentioned: kept, trailing the
	ones it did (the sidebar), or dropped (the dock). See `apply_layer`.

	**The map is seeded from the base**, so the base hides on the same terms as everything above
	it: an app may ship an entry off by default, and one row above it naming that entry with
	hiding off brings it back. The base used to be the one layer whose hiding was discarded --
	seeding it removes a special case rather than adding a parameter.

	The sidebar opts out by the shape of its own base rather than by a flag here: its rows are
	shaped through a key whitelist (`filter_sidebar_items`) that omits `hidden`, so a sidebar
	base dict never carries one and the seed is always false.
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
	"""One layer's arrangement, applied to `items`. Mutates `hidden`, which spans the layers.

	Both sides are matched by `key`, which reads the same columns off a stored row as off a
	resolved entry -- so a rename that rewrote both leaves them still matching, and neither side
	had to be re-keyed for it.

	A layer that named nothing at all says nothing, whatever `keep_unnamed` is: dropping the tail
	on an empty layer would empty the surface, where what an empty layer means is "no opinion".
	"""
	by_key = {key(item): item for item in items}
	arranged: list[str] = []
	named: set[str] = set()

	for row in rows:
		row_key = key(row)
		# an entry named twice is a client sending the same one twice; the first position wins,
		# because the alternative is rendering it twice
		if row_key in named:
			continue

		entry = apply_row(row, by_key.get(row_key))
		if entry is None:
			# a row naming nothing the list holds -- an item the app has since deleted, or one
			# this user may not see: skipped, never raised, and never conjured into the list
			continue

		by_key[row_key] = entry
		hidden[row_key] = bool(row.get("hidden"))
		arranged.append(row_key)
		named.add(row_key)

	if not named:
		return items

	arranged_items = [by_key[row_key] for row_key in arranged]
	# Entries the layer never named. The sidebar keeps them, trailing the ones it did, so an app
	# adding an item still surfaces for someone who has already rearranged. The dock drops them:
	# a saved layer is exactly the rail, so an app's later addition waits in the manager to be
	# added rather than appearing on a rail somebody has already settled. That costs nothing the
	# layer was already seeing -- a dock layer names *every* entry it was shown, hidden ones
	# included -- and it buys a rail that does not change under you.
	if not keep_unnamed:
		return arranged_items

	return arranged_items + [item for item in items if key(item) not in named]
