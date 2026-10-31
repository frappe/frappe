# The person's last v2 list, saved view and record visits, read back from `Route History`, which the shell writes.

from datetime import datetime
from typing import NamedTuple
from urllib.parse import unquote

import frappe
from frappe.desk.doctype.doctype_view.key_space import reserved_keys

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
	# A saved view's key; None for anything else.
	view: str | None = None


def latest_visits(limit: int) -> list[Visit]:
	"""The session user's last `limit` distinct `/apps/…` routes, newest first, less any that is no list, view or record."""
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
	"""The app, doctype and record name or view key the row's address names, read as the shell's router reads it."""
	split = split_shell_path(row.route)
	app = split and prefixes.get(split[0])
	if not app:
		return None

	segments = [unquote(segment) for segment in split[1].split("/")]
	if is_modular(app):
		segments = segments[1:]
	if len(segments) == 3 and segments[1] == "view":
		return parse_view_visit(row, app, segments, doctypes)
	if not 1 <= len(segments) <= 2 or not all(segments) or segments[0] not in doctypes:
		return None

	name = segments[1] if len(segments) == 2 else None
	return Visit(row.route, row.visited, app, doctypes[segments[0]], name)


def parse_view_visit(row, app: str, segments: list[str], doctypes: dict[str, str]) -> Visit | None:
	"""A saved view's address, `<doctype>/view/<key>`; a view type's own page is no saved view."""
	slug, _view, key = segments
	if slug not in doctypes or not key or key in reserved_keys():
		return None
	return Visit(row.route, row.visited, app, doctypes[slug], None, key)
