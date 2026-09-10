import re

import frappe
from frappe.query_builder import DocType

FIXED_WIDTH_PARTS = {"YY": 2, "MM": 2, "DD": 2, "WW": 2, "JJJ": 3, "YYYY": 4}
CHUNK_SIZE = 20000


def execute():
	"""Seed `tabSeries` from names already minted by Document Naming Rules.

	Disabled rules are seeded too. A rule that minted names before being
	disabled would otherwise restart at 1 whenever it is switched back on.

	Rules used to keep a single counter on the rule itself. They now share the
	per-prefix counters in `tabSeries`, which start at 1 and would collide with
	existing names unless seeded here.
	"""
	for doctype, rules in rules_by_doctype().items():
		if frappe.db.table_exists(doctype):
			seed_doctype(doctype, rules)


def rules_by_doctype():
	rules = frappe.get_all(
		"Document Naming Rule",
		fields=["document_type", "prefix", "prefix_digits"],
		order_by="priority desc",
	)

	grouped = {}
	for rule in rules:
		grouped.setdefault(rule.document_type, []).append(rule)
	return grouped


def seed_doctype(doctype, rules):
	"""Attribute each name to one rule, in the order set_new_name applies them.

	A prefix built only from variables compiles to a pattern that matches any
	name ending in the right number of digits, and splits foreign names at the
	wrong boundary. Letting the first matching rule claim a name keeps those
	patterns away from names a more specific rule already accounts for.
	"""
	patterns = [pattern for pattern in map(build_name_pattern, rules) if pattern]

	for prefix, current in collect_counters(doctype, patterns).items():
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
		return ".*?"
	if part in FIXED_WIDTH_PARTS:
		return rf"\d{{{FIXED_WIDTH_PARTS[part]}}}"
	if part == "timestamp" or part.startswith("{") or meta.has_field(part.strip("{}")):
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
	match = next(filter(None, (pattern.match(name) for pattern in patterns)), None)
	if not match:
		return

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
