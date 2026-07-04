# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import re
from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.modules.utils import get_doctype_app_map
from frappe.utils import cint

# columns never worth suggesting a standalone index on: the primary key, the child-table linkage
# columns frappe already covers, and the standard ordering/audit columns that appear in almost
# every query's ORDER BY and would otherwise drown out the meaningful filter columns.
SKIP_COLUMNS = {
	"name",
	"parent",
	"parenttype",
	"parentfield",
	"docstatus",
	"idx",
	"creation",
	"modified",
	"modified_by",
	"owner",
}
FROM_TABLE = re.compile(r'FROM\s+"(tab[^"]+)"', re.IGNORECASE)
PREDICATE = re.compile(r'"(\w+)"\s*(?:=|<|>|<=|>=|!=|<>|\bIN\b|\bLIKE\b|\bBETWEEN\b)', re.IGNORECASE)
ORDER_BY = re.compile(r'ORDER BY\s+"(\w+)"', re.IGNORECASE)


def get_columns():
	return [
		{"label": _("Table"), "fieldname": "table_name", "fieldtype": "Data", "width": 260},
		{"label": _("App"), "fieldname": "app", "fieldtype": "Data", "width": 110},
		{"label": _("Rows"), "fieldname": "rows", "fieldtype": "Int", "width": 100},
		{"label": _("Seq Scans"), "fieldname": "seq_scan", "fieldtype": "Int", "width": 100},
		{"label": _("Rows / Seq Scan"), "fieldname": "rows_per_seq_scan", "fieldtype": "Int", "width": 120},
		{"label": _("Index Scans"), "fieldname": "idx_scan", "fieldtype": "Int", "width": 100},
		{"label": _("Suggested Columns"), "fieldname": "suggestion", "fieldtype": "Data", "width": 300},
	]


def execute(filters=None):
	frappe.only_for("System Manager")
	if frappe.db.db_type != "postgres":
		frappe.throw(_("This report is only available on PostgreSQL sites."))

	min_rows = cint((filters or {}).get("min_rows")) or 10000
	# pg_stat_user_tables is always available (no extension). Tables read mostly via sequential
	# scans -- and big enough to matter -- are the ones that most likely need an index.
	data = frappe.db.sql(
		"""
		SELECT
			relname AS table_name,
			n_live_tup AS rows,
			seq_scan,
			(seq_tup_read / nullif(seq_scan, 0))::bigint AS rows_per_seq_scan,
			coalesce(idx_scan, 0) AS idx_scan
		FROM pg_stat_user_tables
		WHERE seq_scan > coalesce(idx_scan, 0)
			AND n_live_tup >= %(min_rows)s
			AND seq_tup_read > 0
		ORDER BY seq_tup_read DESC
		LIMIT 50
		""",
		{"min_rows": min_rows},
		as_dict=True,
	)

	suggestions = _suggested_columns({row["table_name"] for row in data})
	app_map = get_doctype_app_map()
	for row in data:
		table = row["table_name"]
		columns = suggestions.get(table)
		row["suggestion"] = _("Consider indexing: {0}").format(", ".join(columns)) if columns else ""
		# relname is the physical table (e.g. "tabSales Invoice"); map it back to the owning app
		row["app"] = app_map.get(table[3:]) if table.startswith("tab") else None

	return get_columns(), data


def _suggested_columns(tables: set) -> dict:
	"""For each table, the columns its queries most often filter or sort on that aren't already an
	index's leading key -- mined from pg_stat_statements. Empty if the extension isn't enabled."""
	try:
		statements = frappe.db.sql(
			"""
			SELECT query, calls
			FROM pg_stat_statements s
			JOIN pg_database d ON d.oid = s.dbid
			WHERE d.datname = current_database()
			"""
		)
	except Exception:
		# pg_stat_statements not installed -- fall back to no column-level suggestions.
		frappe.db.rollback()
		return {}

	indexed = _leading_indexed_columns(tables)
	usage = defaultdict(Counter)
	for query, calls in statements:
		# Only single-table queries: a column in a JOIN can't be attributed to one table reliably.
		if " JOIN " in f" {query.upper()} ":
			continue
		match = FROM_TABLE.search(query)
		if not match or match.group(1) not in tables:
			continue
		table = match.group(1)
		referenced = set(PREDICATE.findall(query)) | set(ORDER_BY.findall(query))
		for column in referenced - SKIP_COLUMNS - indexed.get(table, set()):
			usage[table][column] += calls or 1

	return {table: [column for column, _count in counter.most_common(3)] for table, counter in usage.items()}


def _leading_indexed_columns(tables: set) -> dict:
	"""The columns already usable as an index's leading key, per table -- so we don't re-suggest them."""
	indexed = defaultdict(set)
	if not tables:
		return indexed
	rows = frappe.db.sql(
		"""
		SELECT t.relname AS table_name, a.attname AS column_name
		FROM pg_index ix
		JOIN pg_class t ON t.oid = ix.indrelid
		JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ix.indkey[0]
		WHERE t.relname IN %(tables)s
		""",
		{"tables": tuple(tables)},
	)
	for table_name, column_name in rows:
		indexed[table_name].add(column_name)
	return indexed
