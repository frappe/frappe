import frappe
from pymysql import InternalError

# This patch deletes all the duplicate indexes created for same column
# The patch only checks for indexes with UNIQUE constraints

def execute():
	if frappe.db.db_type != 'mariadb':
		return

	all_tables = frappe.db.get_tables()
	final_deletion_map = frappe._dict()

	for table in all_tables:
		indexes_to_keep_map = frappe._dict()
		indexes_to_delete = []
		index_info = frappe.db.sql("""
			SELECT
				column_name,
				index_name,
				non_unique
			FROM information_schema.STATISTICS
			WHERE table_name=%s
			AND column_name!='name'
			AND non_unique=0
			ORDER BY index_name;
		""", table, as_dict=1)

		for index in index_info:
			if not indexes_to_keep_map.get(index.column_name):
				indexes_to_keep_map[index.column_name] = index
			else:
				indexes_to_delete.append(index.index_name)
		if indexes_to_delete:
			final_deletion_map[table] = indexes_to_delete

	# build drop index query
	for (table_name, index_list) in final_deletion_map.items():
		query_list = []
		alter_query = "ALTER TABLE `{}`".format(table_name)

		for index in index_list:
			query_list.append("{} DROP INDEX `{}`".format(alter_query, index))

		for query in query_list:
			try:
				frappe.db.sql(query)
			except InternalError:
				pass
