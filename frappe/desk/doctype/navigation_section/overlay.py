# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""How a user's personal overlay of a shared Navigation Section resolves against it."""

"""What an overlay row may say about the shared row it deltas, beyond where it sits.
An empty value is not an override — it is a row that never named one, which is every
row a drag wrote."""
OVERRIDABLE = ("label", "icon")


def apply_overlay(shared_rows, overlay_rows):
	"""The section's rows as one user sees them, in order."""
	if not overlay_rows:
		return [{**row, "hidden": hidden_flag(row), "own": 0} for row in by_idx(shared_rows)]

	return [
		own_row(delta) if shared is None else resolve(shared, delta)
		for shared, delta in arranged_rows(shared_rows, overlay_rows)
	]


def resolve(shared, delta):
	"""One shared row under its owner's delta."""
	if not delta:
		return {**shared, "hidden": hidden_flag(shared), "own": 0}

	overridden = {field: delta[field] for field in OVERRIDABLE if delta.get(field)}
	return {**shared, **overridden, "hidden": hidden_flag(delta), "own": 0}


def own_row(row):
	"""An item the user added to the section themselves."""
	return {**row, "hidden": hidden_flag(row), "own": 1}


def arranged_rows(shared_rows, overlay_rows):
	"""The rows to render, in the user's order, as `(shared row, overlay row)` pairs."""
	rows_by_name = {row.get("name"): row for row in shared_rows}
	mentioned = {row.get("overrides") for row in overlay_rows}

	arranged = [
		(rows_by_name.get(row["overrides"]), row) if row.get("overrides") else (None, row)
		for row in by_idx(overlay_rows)
		if not row.get("overrides") or row["overrides"] in rows_by_name
	]
	added = [(row, None) for row in by_idx(shared_rows) if row.get("name") not in mentioned]
	return arranged + added


def by_idx(rows):
	return sorted(rows, key=lambda row: row.get("idx") or 0)


def hidden_flag(row):
	return 1 if row.get("hidden") else 0
