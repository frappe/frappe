import frappe

def execute():
	if not 'published' in frappe.db.get_db_table_columns('__global_search'):
		frappe.db.sql('''alter table __global_search
			add column `title` varchar(140)''')

		frappe.db.sql('''alter table __global_search
			add column `route` varchar(140)''')

		frappe.db.sql('''alter table __global_search
			add column `published` int(1) not null default 0''')
