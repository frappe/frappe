import re

import frappe
from frappe.query_builder import DocType

FIXED_WIDTH_PARTS = {"YY": 2, "MM": 2, "DD": 2, "WW": 2, "JJJ": 3, "YYYY": 4}
CHUNK_SIZE = 20000


def execute():
	"""Seed `tabSeries` from names already minted by Document Naming Rules.

	Rules used to keep a single counter on the rule itself. They now share the
	per-prefix counters in `tabSeries`, which start at 1 and would collide with
	existing names unless seeded here.
	"""
	rules = frappe.get_all(
		"Document Naming Rule",
		filters={"disabled": 0},
		fields=["document_type", "prefix", "prefix_digits"],
	)
	for rule in rules:
		if frappe.db.table_exists(rule.document_type):
			seed_series_for_rule(rule)


def seed_series_for_rule(rule):
	pattern = build_name_pattern(rule)
	if not pattern:
		return

	for prefix, current in collect_counters(rule.document_type, pattern).items():
		raise_series(prefix, current)


def build_name_pattern(rule):
	"""Regex for names this rule can mint, capturing the resolved prefix."""
	if not rule.prefix_digits or not rule.prefix:
		return None

	meta = frappe.get_meta(rule.document_type)
	body = "".join(part_pattern(part, meta) for part in rule.prefix.split(".") if part)
	return re.compile(rf"^({body})(\d{{{rule.prefix_digits}}})$")


def part_pattern(part, meta):
	"""Mirror the precedence in parse_naming_series, custom parsers included."""
	if part.startswith("#"):
		return rf"\d{{{len(part)}}}"
	if frappe.get_hooks("naming_series_variables", {}).get(part):
		return ".+?"
	if part in FIXED_WIDTH_PARTS:
		return rf"\d{{{FIXED_WIDTH_PARTS[part]}}}"
	if part == "timestamp" or part.startswith("{") or meta.has_field(part.strip("{}")):
		return ".+?"
	return re.escape(part)


def collect_counters(doctype, pattern):
	counters = {}
	start = 0

	while True:
		names = frappe.get_all(
			doctype, pluck="name", order_by="name", limit_start=start, limit_page_length=CHUNK_SIZE
		)
		if not names:
			return counters

		for name in names:
			record_counter(counters, pattern, name)
		start += CHUNK_SIZE


def record_counter(counters, pattern, name):
	match = pattern.match(name)
	if not match:
		return

	prefix, suffix = match.group(1), int(match.group(2))
	if suffix > counters.get(prefix, 0):
		counters[prefix] = suffix


def raise_series(prefix, current):
	"""Move the series forward, never backward."""
	series = DocType("Series")
	existing = (frappe.qb.from_(series).where(series.name == prefix).select("current")).run()

	if not existing:
		frappe.qb.into(series).insert(prefix, current).run()
	elif (existing[0][0] or 0) < current:
		frappe.qb.update(series).set(series.current, current).where(series.name == prefix).run()
