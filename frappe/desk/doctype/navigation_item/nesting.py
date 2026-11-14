# NESTING — how deep a navigation list may go, one rule for the save, the shipped record and the resolver.

# A rail is flat. In a sidebar a `Section` sits at the top level only, and an item sits at the
# top level, in a section, or under an item that is itself at the top level or in a section; an
# item under an item holds nothing. The deepest row is section > item > child.
# `frontend/src/navigation/nesting.ts` asks the same question for the editor, and both suites
# read `frontend/src/navigation/tests/nesting.cases.json`.

# Rows are dicts or documents: a shipped record is checked as the documents it holds.

SECTION = "Section"
RAIL = "Rail"


def nesting_errors(items: list, container: str) -> list[str]:
	"""The keys of the rows that sit past the cap."""
	# A parent that is not in the list is no depth: the resolver promotes such a row to the top.
	rows = {row.get("key"): row for row in items if row.get("key")}

	return [key for key, row in rows.items() if _too_deep(row, rows, container)]


def cap_depth(items: list[dict], container: str) -> list[dict]:
	"""The list with every row past the cap lifted to its parent's parent; the order stays."""
	# A lift can leave the row, or the rows under it, still past the cap, so it repeats; each pass
	# moves a row up, so it ends. A `parent_key` cycle keeps lifting round itself, so whatever
	# is still past the cap after the passes goes to the top level.
	for _pass in range(len(items)):
		past = set(nesting_errors(items, container))
		if not past:
			return items

		items = _lifted(items, past, container)

	past = set(nesting_errors(items, container))
	return [_with_parent(row, None) if row.get("key") in past else row for row in items]


def _too_deep(row, rows: dict, container: str) -> bool:
	if not row.get("parent_key"):
		return False

	if container == RAIL or row.get("item_type") == SECTION:
		return True

	parent = rows.get(row.get("parent_key"))
	if parent is None or parent.get("item_type") == SECTION:
		return False

	# Under an item, which may itself sit only at the top level or in a section.
	grandparent = rows.get(parent.get("parent_key"))
	return grandparent is not None and grandparent.get("item_type") != SECTION


def _lifted(items: list[dict], past: set[str], container: str) -> list[dict]:
	rows = {row.get("key"): row for row in items}

	return [_lift(row, rows, container) if row.get("key") in past else row for row in items]


def _lift(row: dict, rows: dict, container: str) -> dict:
	if container == RAIL or row.get("item_type") == SECTION:
		return _with_parent(row, None)

	grandparent = rows[row.get("parent_key")].get("parent_key")
	return _with_parent(row, None if grandparent == row.get("key") else grandparent)


def _with_parent(row: dict, parent_key: str | None) -> dict:
	return {**row, "parent_key": parent_key}
