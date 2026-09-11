import re

import frappe
from frappe.model import child_table_fields, default_fields, optional_fields
from frappe.query_builder import DocType

FIXED_WIDTH_PARTS = {"YY": 2, "MM": 2, "DD": 2, "WW": 2, "JJJ": 3, "YYYY": 4}
STANDARD_FIELDS = frozenset(default_fields + child_table_fields + optional_fields)
CHUNK_SIZE = 20000


def execute():
	"""Seed `tabSeries` from names already minted by Document Naming Rules.

	Rules used to keep a single counter on the rule itself. They now share the
	per-prefix counters in `tabSeries`, which start at 1 and would collide with
	existing names unless seeded here.

	Disabled rules are seeded too. A rule that minted names before being
	disabled would otherwise restart at 1 whenever it is switched back on.
	"""
	for doctype, rules in rules_by_doctype().items():
		if frappe.db.table_exists(doctype):
			seed_doctype(doctype, rules)


def rules_by_doctype():
	rules = frappe.get_all(
		"Document Naming Rule",
		fields=["document_type", "prefix", "prefix_digits"],
	)

	grouped = {}
	for rule in rules:
		grouped.setdefault(rule.document_type, []).append(rule)
	return grouped


def seed_doctype(doctype, rules):
	"""Record what every matching rule makes of a name, not just the first.

	Rules on one doctype can produce overlapping names, and a name alone does
	not say which rule minted it. Picking one rule to own it risks picking
	wrong and leaving the real series unseeded, which mints a duplicate. Every
	rule that matches records its own reading instead: a rule always reads its
	own names correctly, because the trailing digit count fixes where the
	counter starts, so every live series is seeded whoever else matched.

	A reading no rule minted usually seeds a series nothing resolves to, which
	costs a row. Where another rule does resolve to that exact prefix, reading
	test-claim-000100 as test-claim-0 and 00100 for instance, its series moves
	forward and it skips numbers. That is the accepted cost: suppressing such
	a reading means judging which rule owns a name, and a wrong judgement
	there leaves a live series unseeded and mints a duplicate instead.
	"""
	patterns = []
	for rule in rules:
		pattern = build_name_pattern(rule)
		if pattern:
			patterns.append(pattern)

	for prefix, current in collect_counters(doctype, patterns).items():
		raise_series(prefix, current)


def build_name_pattern(rule):
	"""Regex for names this rule can mint, capturing the resolved prefix."""
	if not rule.prefix_digits or not rule.prefix:
		return None

	meta = frappe.get_meta(rule.document_type)
	body = ""
	for part in rule.prefix.split("."):
		if part:
			body += part_pattern(part, meta)

	return re.compile(rf"^({body})(\d{{{rule.prefix_digits}}})$")


def part_pattern(part, meta):
	"""Mirror the precedence in parse_naming_series, custom parsers included."""
	if part.startswith("#"):
		return rf"\d{{{len(part)}}}"
	if frappe.get_hooks("naming_series_variables", {}).get(part):
		return ".*?"
	if part in FIXED_WIDTH_PARTS:
		return rf"\d{{{FIXED_WIDTH_PARTS[part]}}}"
	if part == "timestamp" or part.startswith("{"):
		return ".*?"
	if part in STANDARD_FIELDS or meta.has_field(part):
		return ".*?"
	return re.escape(part)


def collect_counters(doctype, patterns):
	counters = {}
	start = 0

	while True:
		names = frappe.get_all(doctype, pluck="name", order_by="name", offset=start, limit=CHUNK_SIZE)
		if not names:
			return counters

		for name in names:
			record_counter(counters, patterns, name)
		start += CHUNK_SIZE


def record_counter(counters, patterns, name):
	for pattern in patterns:
		match = pattern.match(name)
		if not match:
			continue

		prefix, suffix = match.group(1), int(match.group(2))
		if prefix and suffix > counters.get(prefix, 0):
			counters[prefix] = suffix


def raise_series(prefix, current):
	"""Move the series forward, never backward."""
	series = DocType("Series")
	existing = (frappe.qb.from_(series).where(series.name == prefix).select("current")).run()

	if not existing:
		frappe.qb.into(series).insert(prefix, current).run()
	elif (existing[0][0] or 0) < current:
		frappe.qb.update(series).set(series.current, current).where(series.name == prefix).run()
