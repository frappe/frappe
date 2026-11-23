"""Traversal helpers for the print format builder's layout JSON.

A layout is ``{"header": zone, "sections": [zone, ...], "footer": zone}`` where a
zone is ``{"columns": [{"fields": [df, ...]}, ...]}``. Everything that walks it
goes through here so each consumer sees the same nodes in the same order:
header, body sections, footer."""

import json
from collections.abc import Iterator

from frappe import _

ZONE_SHOW_ON = ("every_page", "first_page", "last_page", "after_first_page")


def zone_show_on(layout: dict, kind: str) -> str | None:
	"""The pages the header or footer prints on; None follows Print Settings."""
	zone = layout.get(kind)
	show_on = zone.get("show_on") if isinstance(zone, dict) else None
	return show_on if show_on in ZONE_SHOW_ON else None


def zone_repeats(layout: dict, kind: str, repeat_header_footer: int, in_preview: bool = False) -> bool:
	"""Whether the header or footer belongs in the per-page frame.

	A first-page header prints once in the body, so later pages get its space back.
	A browser's repeating frame cannot vary by page, so the preview also prints a
	last-page footer once."""
	show_on = zone_show_on(layout, kind)
	if not show_on:
		return bool(repeat_header_footer)
	printed_once = "first_page" if kind == "header" else "last_page" if in_preview else None
	return show_on != printed_once


def has_page_specific_zone(format_data: str | None) -> bool:
	"""Whether a saved layout prints its header or footer on some pages only."""
	try:
		layout = json.loads(format_data or "{}")
	except ValueError:
		return False
	return isinstance(layout, dict) and any(
		zone_show_on(layout, kind) not in (None, "every_page") for kind in ("header", "footer")
	)


def iter_zones(layout: dict) -> Iterator[tuple[str, dict]]:
	"""Yield (where, zone) for the header, each body section and the footer, in print order."""
	header = layout.get("header")
	if isinstance(header, dict):
		yield _("Header"), header
	for section in layout.get("sections") or []:
		if isinstance(section, dict):
			yield section.get("label") or _("Section"), section
	footer = layout.get("footer")
	if isinstance(footer, dict):
		yield _("Footer"), footer


def iter_columns(zone: dict) -> Iterator[dict]:
	"""Yield the column dicts of one zone, skipping anything that is not a dict."""
	columns = zone.get("columns")
	for column in columns if isinstance(columns, list) else []:
		if isinstance(column, dict):
			yield column


def iter_fields(zone: dict) -> Iterator[dict]:
	"""Yield every field dict in a zone, column by column."""
	for column in iter_columns(zone):
		fields = column.get("fields")
		for df in fields if isinstance(fields, list) else []:
			if isinstance(df, dict):
				yield df


def iter_layout_columns(layout: dict) -> Iterator[dict]:
	"""Yield every column dict across all zones; callers mutate the dicts in place."""
	for _where, zone in iter_zones(layout):
		yield from iter_columns(zone)


def iter_nodes(layout: dict) -> Iterator[tuple[str, dict]]:
	"""Yield (where, node) for every zone and then each of its fields."""
	for where, zone in iter_zones(layout):
		yield where, zone
		for df in iter_fields(zone):
			yield where, df
