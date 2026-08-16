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
- **what a row does to the entry it names.** A sidebar row may add an entry, may state a label
  for one already in the list, and may name one that is no longer there at all. A dock row *is*
  the entry.

Neither of those is the merge, which is why the merge lives here and they are passed in as
`key` and `apply_row`.
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
) -> tuple[list[dict], dict[str, bool]]:
	"""Fold each layer into the one below it. Later layers win, on order and on hiding alike.

	`base` is the arrangement the layers are laid over -- what an app ships. The dock's is empty
	today, because nothing ships one yet; its first layer is the site's.

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
	"""
	resolved = [dict(item) for item in base]
	hidden: dict[str, bool] = {}

	for rows in layers:
		resolved = apply_layer(resolved, rows, hidden, key=key, apply_row=apply_row)

	return resolved, hidden


def apply_layer(
	items: list[dict],
	rows: list[Row],
	hidden: dict[str, bool],
	*,
	key: Key,
	apply_row: ApplyRow,
) -> list[dict]:
	"""One layer's arrangement, applied to `items`. Mutates `hidden`, which spans the layers.

	Both sides are matched by `key`, which reads the same columns off a stored row as off a
	resolved entry -- so a rename that rewrote both leaves them still matching, and neither side
	had to be re-keyed for it.
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

	# Entries the layer never named keep their incoming order and follow the ones it did, so an
	# app adding an entry still surfaces for someone who has already reordered.
	return [by_key[row_key] for row_key in arranged] + [item for item in items if key(item) not in named]
