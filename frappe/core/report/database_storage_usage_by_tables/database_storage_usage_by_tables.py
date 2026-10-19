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
			"sqlite": """
				WITH page_usage AS (
					SELECT
						objects.tbl_name AS table_name,
						SUM(CASE WHEN objects.type = 'table' THEN pages.pgsize ELSE 0 END) AS data_bytes,
						SUM(CASE WHEN objects.type = 'index' THEN pages.pgsize ELSE 0 END) AS index_bytes
					FROM dbstat AS pages
					JOIN sqlite_master AS objects ON objects.name = pages.name
					WHERE objects.type IN ('table', 'index')
					GROUP BY objects.tbl_name
				)
				SELECT
					tables.name AS 'table',
					ROUND(COALESCE(page_usage.data_bytes, 0) / (1024.0 * 1024.0), 2) AS 'data_size',
					ROUND(COALESCE(page_usage.index_bytes, 0) / (1024.0 * 1024.0), 2) AS 'index_size',
					ROUND(
						(COALESCE(page_usage.data_bytes, 0) + COALESCE(page_usage.index_bytes, 0))
						/ (1024.0 * 1024.0),
						2
					) AS 'size'
				FROM sqlite_master AS tables
				LEFT JOIN page_usage ON page_usage.table_name = tables.name
				WHERE tables.type = 'table'
				AND tables.name NOT LIKE 'sqlite_%'
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
