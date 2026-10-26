# The person's last v2 list and record visits, read back from `Route History`, which the shell writes.

from datetime import datetime
from typing import NamedTuple
from urllib.parse import unquote

import frappe

from . import SHELL_ROOT
from .doctypes import get_address_table
from .registry import get_prefix_registry, is_modular, split_shell_path


class Visit(NamedTuple):
	route: str
	visited: datetime
	app: str
	doctype: str
	# None for a list.
	name: str | None


def latest_visits(limit: int) -> list[Visit]:
	"""The session user's last `limit` distinct `/apps/…` routes, newest first, less any that is no list or record."""
	rows = frappe.get_all(
		"Route History",
		filters={"user": frappe.session.user, "route": ["like", f"/{SHELL_ROOT}/%"]},
		fields=["route", {"MAX": "creation", "as": "visited"}],
		group_by="route",
		order_by="visited desc",
		limit=limit,
	)
	doctypes = {address[0]: doctype for doctype, address in get_address_table()["doctypes"].items()}
	prefixes = get_prefix_registry()

	return [visit for row in rows if (visit := parse_visit(row, prefixes, doctypes))]


def parse_visit(row, prefixes: dict[str, str], doctypes: dict[str, str]) -> Visit | None:
	"""The app, doctype and record name the row's address names, read as the shell's router reads it."""
	split = split_shell_path(row.route)
	app = split and prefixes.get(split[0])
	if not app:
		return None

	segments = [unquote(segment) for segment in split[1].split("/")]
	if is_modular(app):
		segments = segments[1:]
	if not 1 <= len(segments) <= 2 or not all(segments) or segments[0] not in doctypes:
		return None

	name = segments[1] if len(segments) == 2 else None
	return Visit(row.route, row.visited, app, doctypes[segments[0]], name)
