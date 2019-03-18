import frappe

def execute():

	fields = frappe.db.sql("""
			SELECT COLUMN_NAME , TABLE_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
			WHERE DATA_TYPE IN ('INT', 'FLOAT', 'DECIMAL') AND IS_NULLABLE = 'YES'
		""", as_dict=1)

	update_column_table_map = {}

	for field in fields:
		update_column_table_map.setdefault(field.TABLE_NAME, [])

		if field.TABLE_NAME not in ['tabDocPerm', 'tabCustom Field', 'tabWebsite Route Permission']:
			update_column_table_map[field.TABLE_NAME].append(str(field.COLUMN_NAME)+"=COALESCE("+str(field.COLUMN_NAME)+", 0)")

	for table in frappe.db.get_tables():
		if update_column_table_map.get(table):
			frappe.db.sql("""UPDATE `{table}` SET {columns}"""
				.format(table=table, columns=",".join(update_column_table_map.get(table))))

