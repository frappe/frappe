# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""One page of the merged activity feed, read newest first behind a `(timestamp, key)` cursor."""

from collections.abc import Callable

import frappe
from frappe import _

PAGE_SIZE = 50

# Sorts after every activity key, so a cursor on it keeps every row at that instant.
AFTER_EVERY_KEY = "~"

Position = tuple[str, str]


class ActivityPage:
	def __init__(self, before: str | None, limit: int):
		self.before = parse_cursor(before)
		self.limit = limit
		self.floor: Position | None = None

	def filters(self, column: str = "creation") -> list:
		return [[column, "<=", self.before_timestamp]] if self.before else []

	@property
	def before_timestamp(self) -> str | None:
		return self.before[0] if self.before else None

	@property
	def fetch_size(self) -> int:
		return self.limit + 1

	def trim(self, rows: list, timestamp: Callable[[dict], str]) -> list:
		"""Keep one source's newest `limit` rows; a source cut short raises the page's floor."""
		if len(rows) <= self.limit:
			return rows
		kept, extra = rows[: self.limit], rows[self.limit]
		boundary = timestamp(kept[-1])
		floor = (boundary, "") if timestamp(extra) < boundary else (boundary, AFTER_EVERY_KEY)
		self.floor = max(self.floor or floor, floor)
		return kept

	def build(self, activities: list[dict]) -> dict:
		rows = sorted(filter(self.holds, activities), key=position, reverse=True)
		next_position = self.floor
		if len(rows) > self.limit:
			rows = rows[: self.limit]
			next_position = position(rows[-1])
		rows.reverse()
		return {"activities": rows, "next": format_cursor(next_position)}

	def holds(self, activity: dict) -> bool:
		at = position(activity)
		return (self.before is None or at < self.before) and (self.floor is None or at >= self.floor)


def position(activity: dict) -> Position:
	return (activity.get("timestamp") or "", activity["key"])


def parse_cursor(cursor: str | None) -> Position | None:
	if not cursor:
		return None
	timestamp, separator, key = cursor.partition("|")
	if not separator:
		frappe.throw(_("before is not an activity cursor: {0}").format(cursor))
	return (timestamp, key)


def format_cursor(at: Position | None) -> str | None:
	return f"{at[0]}|{at[1]}" if at else None
