# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.modules.utils import get_doctype_app_map
from frappe.utils import cint

# frappe quotes table identifiers, so tables appear as "tabDoctype Name" in the normalized query text
TABLE_IN_QUERY = re.compile(r'"tab([^"]+)"')


def get_columns():
	return [
		{"label": _("Query"), "fieldname": "query", "fieldtype": "Data", "width": 520},
		{"label": _("App"), "fieldname": "app", "fieldtype": "Data", "width": 110},
		{"label": _("Calls"), "fieldname": "calls", "fieldtype": "Int", "width": 90},
		{"label": _("Total (ms)"), "fieldname": "total_ms", "fieldtype": "Float", "width": 120},
		{"label": _("Mean (ms)"), "fieldname": "mean_ms", "fieldtype": "Float", "width": 110},
		{"label": _("Rows"), "fieldname": "rows", "fieldtype": "Int", "width": 90},
		{"label": _("Cache Hit %"), "fieldname": "cache_hit_pct", "fieldtype": "Percent", "width": 110},
	]


def execute(filters=None):
	frappe.only_for("System Manager")
	if frappe.db.db_type != "postgres":
		frappe.throw(_("This report is only available on PostgreSQL sites."))

	limit = cint((filters or {}).get("limit")) or 50
	try:
		# scope to current_database() so a shared cluster only shows this site's queries
		data = frappe.db.sql(
			"""
			SELECT
				query,
				calls,
				round(total_exec_time::numeric, 2) AS total_ms,
				round(mean_exec_time::numeric, 2) AS mean_ms,
				rows,
				round(100.0 * shared_blks_hit
					/ nullif(shared_blks_hit + shared_blks_read, 0), 1) AS cache_hit_pct
			FROM pg_stat_statements s
			JOIN pg_database d ON d.oid = s.dbid
			WHERE d.datname = current_database()
			ORDER BY total_exec_time DESC
			LIMIT %(limit)s
			""",
			{"limit": limit},
			as_dict=True,
		)
	except Exception as e:
		frappe.db.rollback()
		# Only a missing pg_stat_statements view means the extension isn't enabled. Re-raise
		# anything else (privilege error, connection drop, a future column rename) so it is not
		# misreported as "extension not installed".
		if not frappe.db.is_table_missing(e):
			raise
		# CREATE EXTENSION is per-database, so a cluster can have the library preloaded yet the
		# view missing on this site's DB. Point the admin at the exact missing step.
		preloaded = "pg_stat_statements" in (frappe.db.sql("SHOW shared_preload_libraries")[0][0] or "")
		if preloaded:
			frappe.throw(
				_(
					"pg_stat_statements is loaded on the server but not enabled in this site's "
					"database. A PostgreSQL superuser must run, connected to THIS database:"
				)
				+ "\n\n    CREATE EXTENSION pg_stat_statements;"
			)
		frappe.throw(
			_(
				"pg_stat_statements is not enabled. A PostgreSQL superuser must add "
				"'pg_stat_statements' to shared_preload_libraries, restart PostgreSQL, then run "
				"CREATE EXTENSION pg_stat_statements; in this site's database."
			)
		)

	app_map = get_doctype_app_map()
	for row in data:
		# pg_stat_statements returns "<insufficient privilege>" for queries run by other roles
		# (grant pg_read_all_stats to see them), or NULL if the text was evicted. The datatable
		# eats the angle brackets as an HTML tag, so relabel those so the cell is never blank.
		text = row.get("query") or ""
		row["app"] = _apps_in_query(text, app_map)
		if not text or (text.startswith("<") and text.endswith(">")):
			row["query"] = text.strip("<>") or "(query text unavailable)"

	return get_columns(), data


def _apps_in_query(query: str, app_map: dict) -> str:
	"""Best-effort: the app(s) owning the frappe tables a query touches, joined for display."""
	apps = {app_map.get(doctype) for doctype in TABLE_IN_QUERY.findall(query)}
	return ", ".join(sorted(app for app in apps if app))


@frappe.whitelist()
def reset_stats():
	frappe.only_for("System Manager")
	if frappe.db.db_type == "postgres":
		# Scope the reset to THIS site's database -- the unqualified reset wipes stats for every
		# database in the cluster, clobbering other sites. Scoped form needs PostgreSQL 12+.
		frappe.db.sql(
			"SELECT pg_stat_statements_reset(0, (SELECT oid FROM pg_database WHERE datname = current_database()), 0)"
		)
