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
	"""Group rules per doctype, enabled ones first, then by priority.

	set_new_name only ever offers a name to enabled rules, so a disabled rule
	must not claim one ahead of them. It still gets a turn afterwards, for the
	names it minted before it was switched off.
	"""
	rules = frappe.get_all(
		"Document Naming Rule",
		fields=["document_type", "prefix", "prefix_digits"],
		order_by="disabled asc, priority desc",
	)

	grouped = {}
	for rule in rules:
		grouped.setdefault(rule.document_type, []).append(rule)
	return grouped


def seed_doctype(doctype, rules):
	"""Attribute each name to one rule, most specific pattern first.

	A prefix built only from variables compiles to a pattern that matches any
	name ending in the right number of digits, and splits foreign names at the
	wrong boundary. Ranking by the number of literal characters a pattern pins
	down keeps such a pattern away from any name a narrower rule accounts for,
	whichever of the two is enabled. Rules that pin down the same amount keep
	the order they were read in, enabled ahead of disabled.
	"""
	ranked = []
	for position, rule in enumerate(rules):
		built = build_name_pattern(rule)
		if built:
			pattern, literals = built
			ranked.append((-literals, position, pattern))

	ranked.sort()
	patterns = [pattern for _, _, pattern in ranked]

	for prefix, current in collect_counters(doctype, patterns).items():
		raise_series(prefix, current)


def build_name_pattern(rule):
	"""Regex for names this rule can mint, plus the literal characters it pins."""
	if not rule.prefix_digits or not rule.prefix:
		return None

	meta = frappe.get_meta(rule.document_type)
	body = ""
	literals = 0
	for part in rule.prefix.split("."):
		if not part:
			continue
		fragment, pinned = part_pattern(part, meta)
		body += fragment
		literals += pinned

	return re.compile(rf"^({body})(\d{{{rule.prefix_digits}}})$"), literals


def part_pattern(part, meta):
	"""Mirror the precedence in parse_naming_series, custom parsers included."""
	if part.startswith("#"):
		return rf"\d{{{len(part)}}}", 0
	if frappe.get_hooks("naming_series_variables", {}).get(part):
		return ".*?", 0
	if part in FIXED_WIDTH_PARTS:
		return rf"\d{{{FIXED_WIDTH_PARTS[part]}}}", 0
	if part == "timestamp" or part.startswith("{") or meta.has_field(part.strip("{}")):
		return ".*?", 0
	return re.escape(part), len(part)


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
		return


def raise_series(prefix, current):
	"""Move the series forward, never backward."""
	series = DocType("Series")
	existing = (frappe.qb.from_(series).where(series.name == prefix).select("current")).run()

	if not existing:
		frappe.qb.into(series).insert(prefix, current).run()
	elif (existing[0][0] or 0) < current:
		frappe.qb.update(series).set(series.current, current).where(series.name == prefix).run()
