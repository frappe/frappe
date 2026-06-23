# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe

COLUMNS = [
	{"label": "Table", "fieldname": "table", "fieldtype": "Data", "width": 200},
	{"label": "Size (MB)", "fieldname": "size", "fieldtype": "Float"},
	{"label": "Data (MB)", "fieldname": "data_size", "fieldtype": "Float"},
	{"label": "Index (MB)", "fieldname": "index_size", "fieldtype": "Float"},
]


def execute(filters=None):
	frappe.only_for("System Manager")

	data = frappe.db.multisql(
		{
			"mariadb": """
				SELECT table_name AS `table`,
						round(((data_length + index_length) / 1024 / 1024), 2) `size`,
						round((data_length / 1024 / 1024), 2) as data_size,
						round((index_length / 1024 / 1024), 2) as index_size
				FROM information_schema.TABLES
				WHERE table_schema = DATABASE()
				ORDER BY (data_length + index_length) DESC;
			""",
			"postgres": """
				SELECT
				  table_name as "table",
				  round(pg_total_relation_size(quote_ident(table_name)) / 1024 / 1024, 2) as "size",
				  round(pg_relation_size(quote_ident(table_name)) / 1024 / 1024, 2) as "data_size",
				  round(pg_indexes_size(quote_ident(table_name)) / 1024 / 1024, 2) as "index_size"
				FROM information_schema.tables
				WHERE table_schema = 'public'
				ORDER BY 2 DESC;
			""",
			# dbstat is a virtual table that materialises by scanning every page, so the
			# previous per-table correlated subqueries scanned it once per table (O(tables
			# x pages), ~minutes on a real DB). Scan it once into the `stat` CTE, map every
			# table/index to its owning table, then aggregate with a single GROUP BY.
			"sqlite": """
				WITH
					ps AS (SELECT CAST(page_size AS FLOAT) AS size FROM PRAGMA_page_size()),
					stat AS (SELECT name, SUM(pgsize) AS bytes FROM dbstat GROUP BY name),
					owner AS (
						SELECT name AS obj, name AS tbl FROM sqlite_master
						WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
						UNION ALL
						SELECT name AS obj, tbl_name AS tbl FROM sqlite_master WHERE type = 'index'
					),
					agg AS (
						SELECT o.tbl,
							SUM(CASE WHEN o.obj = o.tbl THEN COALESCE(stat.bytes, 0) ELSE 0 END) AS data_bytes,
							SUM(CASE WHEN o.obj <> o.tbl THEN COALESCE(stat.bytes, 0) ELSE 0 END) AS idx_bytes
						FROM owner o
						LEFT JOIN stat ON stat.name = o.obj
						GROUP BY o.tbl
					)
				SELECT
					tbl AS 'table',
					ROUND(CAST(data_bytes * ps.size / (1024.0 * 1024.0 * 1024.0) AS FLOAT), 2) AS 'data_size',
					ROUND(CAST(idx_bytes * ps.size / (1024.0 * 1024.0 * 1024.0) AS FLOAT), 2) AS 'index_size',
					ROUND(CAST((data_bytes + idx_bytes) * ps.size / (1024.0 * 1024.0 * 1024.0) AS FLOAT), 2) AS 'size'
				FROM agg
				CROSS JOIN ps
				ORDER BY size DESC;""",
		},
		as_dict=1,
	)
	return COLUMNS, data


@frappe.whitelist()
def optimize_doctype(doctype_name: str):
	frappe.only_for("System Manager")
	frappe.enqueue(
		optimize_doctype_job,
		queue="long",
		job_id=f"optimize-{doctype_name}",
		doctype_name=doctype_name,
		deduplicate=True,
	)


def optimize_doctype_job(doctype_name: str):
	from frappe.utils import get_table_name

	doctype_table = get_table_name(doctype_name, wrap_in_backticks=True)
	if frappe.db.db_type == "mariadb":
		query = f"OPTIMIZE TABLE {doctype_table};"
	else:
		query = f"VACUUM (ANALYZE) {doctype_table};"

	frappe.db.sql(query)
