# NESTING — how deep a navigation list may go. A rail is flat; in a sidebar the deepest row is
# section > item > child, and an Act row holds no child. `frontend/src/navigation/nesting.ts` asks the same question.

SECTION = "Section"
ACT = "Act"
RAIL = "Rail"


def nesting_errors(items: list, container: str) -> list[str]:
	"""The keys of the rows that sit past the cap."""
	# An item whose parent is not in the list is no depth: the resolver promotes it to the top.
	rows = {row.get("key"): row for row in items if row.get("key")}

	return [key for key, row in rows.items() if _too_deep(row, rows, container)]


def cap_depth(items: list[dict], container: str) -> list[dict]:
	"""The list with every row past the cap lifted to its parent's parent; the order stays."""
	# A lift can leave rows still past the cap, so it repeats; a parent cycle never settles and
	# goes to the top level.
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

	# An action only runs: it opens nothing for a row to sit under.
	if parent.get("item_type") == ACT:
		return True

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
