import frappe

def execute():
	from frappe.website.router import get_doctypes_with_web_view
	from frappe.utils.global_search import rebuild_for_doctype

	if not 'published' in frappe.db.get_db_table_columns('__global_search'):
		frappe.db.sql('''alter table __global_search
			add column `title` varchar(140)''')

		frappe.db.sql('''alter table __global_search
			add column `route` varchar(140)''')

		frappe.db.sql('''alter table __global_search
			add column `published` int(1) not null default 0''')

	for doctype in get_doctypes_with_web_view():
		rebuild_for_doctype(doctype)

