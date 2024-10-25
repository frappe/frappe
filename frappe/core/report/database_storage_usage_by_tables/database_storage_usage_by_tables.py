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
		},
		as_dict=1,
	)
	return COLUMNS, data


@frappe.whitelist()
def optimize_doctype(doctype_name: str) -> None:
	frappe.only_for("System Manager")
	frappe.enqueue(
		optimize_doctype_job,
		queue="long",
		job_id=f"optimize-{doctype_name}",
		doctype_name=doctype_name,
		deduplicate=True,
	)


def optimize_doctype_job(doctype_name: str) -> None:
	from frappe.utils import get_table_name

	doctype_table = get_table_name(doctype_name, wrap_in_backticks=True)
	if frappe.db.db_type == "mariadb":
		query = f"OPTIMIZE TABLE {doctype_table};"
	else:
		query = f"VACUUM (ANALYZE) {doctype_table};"

	frappe.db.sql(query)
