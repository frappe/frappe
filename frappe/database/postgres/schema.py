import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.database.schema import DBTable, get_definition

class PostgresTable(DBTable):
	# def __init__(self, doctype, meta=None):
	# 	self.doctype = doctype
	# 	self.table_name = 'tab{}'.format(doctype)
	# 	self.meta = meta or frappe.get_meta(doctype)

	# def sync(self):
	# 	if frappe.db.table_exists(self.doctype):
	# 		print('\n\n\n'+self.doctype+'\n\n\n')
	# 		pass
	# 		#current_table = self.get_as_docfields()
	# 	else:
	# 		self.create_table()

	# def get_as_docfields(self):
	# 	docfields = []
	# 	columns = frappe.db.sql("""select table_name, column_name, data_type, column_default
	# 		from information_schema.columns where table_name='{0}'""".format(self.table_name), as_dict=1)
	# 	for column in columns:
	# 		docfields.append(dict(
	# 			fieldname = column.column_name,
	# 			column_type = column.data_type,
	# 			parent = column.table_name,
	# 			default = column.default
	# 		))
	# 	return docfields

	def create(self):
		add_text = ''

		# columns
		column_defs = self.get_column_definitions()
		if column_defs: add_text += ',\n'.join(column_defs)

		# index
		# index_defs = self.get_index_definitions()
		# TODO: set docstatus length
		# create table
		frappe.db.sql("""create table `%s` (
			name varchar({varchar_len}) not null primary key,
			creation timestamp(6),
			modified timestamp(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus smallint not null default '0',
			parent varchar({varchar_len}),
			parentfield varchar({varchar_len}),
			parenttype varchar({varchar_len}),
			idx bigint not null default '0',
			%s)""".format(varchar_len=frappe.db.VARCHAR_LEN) % (self.table_name, add_text))
			
		frappe.db.commit()

	def alter(self):
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower()))

		query = []

		for col in self.add_column:
			query.append("ADD COLUMN `{}` {}".format(col.fieldname, col.get_definition()))

		for col in self.change_type:
			query.append("ALTER COLUMN `{}` TYPE {}".format(col.fieldname, get_definition(col.fieldtype, precision=col.precision, length=col.length)))

		for col in self.set_default:
			if col.fieldname=="name":
				continue

			if col.fieldtype in ("Check", "Int"):
				col_default = cint(col.default)

			elif col.fieldtype in ("Currency", "Float", "Percent"):
				col_default = flt(col.default)

			elif not col.default:
				col_default = "NULL"

			else:
				col_default = "'{}'".format(col.default.replace("'", "\\'"))

			query.append("ALTER COLUMN `{}` SET DEFAULT {}".format(col.fieldname, col_default))

		create_index_query = ""
		for col in self.add_index:
			# if index key not exists
			create_index_query += "CREATE INDEX IF NOT EXISTS {index_name} ON `{table_name}`(`{field}`);".format(
				index_name=col.fieldname,
				table_name=self.table_name,
				field=col.fieldname)

		drop_index_query = ""
		for col in self.drop_index:
			# primary key
			if col.fieldname != 'name':
				# if index key exists
				if not frappe.db.has_index(self.table_name, col.fieldname):
					drop_index_query += "DROP INDEX IF EXISTS {} ;".format(col.fieldname)

		if query:
			try:
				final_alter_query = "ALTER TABLE `{}` {}".format(self.table_name, ", ".join(query))
				if final_alter_query: frappe.db.sql(final_alter_query)
				if create_index_query: frappe.db.sql(create_index_query)
				if drop_index_query: frappe.db.sql(drop_index_query)
			except Exception as e:
				# sanitize
				if frappe.db.is_duplicate_fieldname(e):
					frappe.throw(str(e))
				elif frappe.db.is_duplicate_entry(e):
					fieldname = str(e).split("'")[-2]
					frappe.throw(_("""{0} field cannot be set as unique in {1},
						as there are non-unique existing values""".format(
						fieldname, self.table_name)))
					raise e
				else:
					raise e



	# def get_column_definitions(self):
	# 	columns_definitions = []
	# 	for field in self.meta.fields:
	# 		columns_definitions.append(self.get_column_definition(field))

	# 	columns_definitions = filter(None, columns_definitions)
	# 	return ', '.join(columns_definitions)

	# def get_column_definition(self, field):
	# 	if field.fieldtype in frappe.db.type_map:
	# 		column_type, default_length = frappe.db.type_map[field.fieldtype]
	# 		length = field.length or default_length
	# 		return self.get_standard_definition(field, column_type, length)
	# 	else:
	# 		return None

	# def get_standard_definition(self, field, column_type, length=None):
	# 	print(field, column_type, length)
	#
	# '"{fieldname}" {column_type}{length} {null} {default}'.format(
	# 		fieldname = field.fieldname,
	# 		column_type = column_type,
	# 		length = '({})'.format(length) if length else '',
	# 		default = 'DEFAULT {}'.format(frappe.db.escape(field.default)) if field.default else '',
	# 		null = 'NOT NULL' if field.reqd else ''
	# 	))
	# 	return '"{fieldname}" {column_type}{length} {null} {default}'.format(
	# 		fieldname = field.fieldname,
	# 		column_type = column_type,
	# 		length = '({})'.format(length) if length and column_type != 'text' else '',
	# 		default = 'DEFAULT {}'.format(frappe.db.escape(field.default)) if field.default else '',
	# 		null = 'NOT NULL' if field.reqd else ''
	# 	)

	# def sync_doctype(self):
	#     pass

	# def get_columns(self):
	#     pass

	# def get_definition(self, fieldtype, precision):
	#     pass

	# def add_column(self, column_name, fieldtype, precision=None):
	#     if column_name in self.get_columns():
	#         # already exists
	#         return

	#     frappe.db.commit()
	#     frappe.db.sql("alter table `tab{0}` add column {1} {2}".format(self.table_name,
	#         column_name, self.get_definition(fieldtype, precision)))