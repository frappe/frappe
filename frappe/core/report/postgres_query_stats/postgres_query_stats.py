# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import re

from psycopg2.errors import ObjectNotInPrerequisiteState

import frappe
from frappe import _
from frappe.modules.utils import get_doctype_app_map
from frappe.utils import cint

# frappe quotes table identifiers, so tables appear as "tabDoctype Name" in the normalized query text
TABLE_IN_QUERY = re.compile(r'"tab([^"]+)"')
SAVE_POINT = "postgres_query_stats"


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

	data = get_query_stats(cint((filters or {}).get("limit")) or 50)

	app_map = get_doctype_app_map()
	for row in data:
		# pg_stat_statements returns "<insufficient privilege>" for queries run by other roles,
		# or NULL if the text was evicted. The datatable eats the angle brackets as an HTML tag,
		# so relabel those so the cell is never blank.
		text = row.get("query") or ""
		row["app"] = _apps_in_query(text, app_map)
		if not text or (text.startswith("<") and text.endswith(">")):
			row["query"] = text.strip("<>") or "(query text unavailable)"

	return get_columns(), data


def get_query_stats(limit: int) -> list[dict]:
	"""Top queries by total execution time, or a message naming the missing setup step."""
	frappe.db.savepoint(SAVE_POINT)
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
	except Exception as exception:
		# postgres aborts the whole transaction on a failed statement. Undo just this query so
		# the checks below, and the caller's error reporting, still have a usable connection --
		# a plain rollback would also discard unrelated work done earlier in the request.
		frappe.db.rollback(save_point=SAVE_POINT)
		_throw_missing_setup_step(exception)
	else:
		frappe.db.release_savepoint(SAVE_POINT)
		return data


def _throw_missing_setup_step(exception: Exception) -> None:
	"""Name the pg_stat_statements setup steps the administrator is missing."""
	if isinstance(exception, ObjectNotInPrerequisiteState):
		frappe.throw(
			_(
				"pg_stat_statements is enabled in this site's database but not loaded on the server. "
				"A PostgreSQL administrator must add 'pg_stat_statements' to shared_preload_libraries "
				"and restart PostgreSQL."
			)
		)

	# Only a missing pg_stat_statements view means the extension isn't enabled. Re-raise
	# anything else (privilege error, connection drop, a future column rename) so it is not
	# misreported as "extension not installed".
	if not frappe.db.is_table_missing(exception):
		raise exception

	# the site role cannot read shared_preload_libraries, so name both steps
	frappe.throw(
		_(
			"pg_stat_statements is not enabled in this site's database. A PostgreSQL superuser must "
			"run CREATE EXTENSION pg_stat_statements; in this database. If 'pg_stat_statements' is "
			"not in shared_preload_libraries yet, also add it there and restart PostgreSQL."
		)
	)


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
