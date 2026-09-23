# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""One page of the merged activity feed, read newest first behind a `(timestamp, key)` cursor."""

from collections.abc import Callable

import frappe
from frappe import _
from frappe.utils import get_datetime

PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

Position = tuple[str, str]


class ActivityPage:
	def __init__(self, before: str | None, limit: int):
		self.before = parse_cursor(before)
		self.limit = min(max(limit, 1), MAX_PAGE_SIZE)
		self.floor: Position | None = None

	def filters(self, column: str = "creation") -> list:
		return [[column, *self.before_condition]] if self.before else []

	@property
	def before_condition(self) -> tuple[str, str] | None:
		"""Up to the cursor's instant, or short of it when the empty key keeps none of it."""
		if not self.before:
			return None
		timestamp, key = self.before
		return ("<=" if key else "<", timestamp)

	@property
	def fetch_size(self) -> int:
		return self.limit + 1

	def trim(self, rows: list, timestamp: Callable[[dict], str], read_instant: Callable[[str], list]) -> list:
		"""Keep one source's newest `limit` rows and all of its oldest instant; a cut raises the floor."""
		if len(rows) <= self.limit:
			return rows
		kept, extra = rows[: self.limit], rows[self.limit]
		boundary = timestamp(kept[-1])
		if timestamp(extra) == boundary:
			kept = [row for row in kept if timestamp(row) != boundary] + read_instant(boundary)
		self.floor = max(self.floor or (boundary, ""), (boundary, ""))
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
	timestamp, separator, key = cursor.partition("|") if isinstance(cursor, str) else ("", "", "")
	at = read_timestamp(timestamp) if separator else None
	if not at:
		frappe.throw(_("before is not an activity cursor: {0}").format(cursor))
	return (str(at), key)


def read_timestamp(timestamp: str):
	try:
		return get_datetime(timestamp)
	except (ValueError, OverflowError):
		return None


def format_cursor(at: Position | None) -> str | None:
	return f"{at[0]}|{at[1]}" if at else None
