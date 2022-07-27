import frappe
from frappe import _
from frappe.database.schema import DBTable
from frappe.model import log_types


class MariaDBTable(DBTable):
	def create(self):
		additional_definitions = ""
		engine = self.meta.get("engine") or "InnoDB"
		varchar_len = frappe.db.VARCHAR_LEN
		name_column = f"name varchar({varchar_len}) primary key"

		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			additional_definitions += ",\n".join(column_defs) + ",\n"

		# index
		index_defs = self.get_index_definitions()
		if index_defs:
			additional_definitions += ",\n".join(index_defs) + ",\n"

		# child table columns
		if self.meta.get("istable") or 0:
			additional_definitions += (
				",\n".join(
					(
						f"parent varchar({varchar_len})",
						f"parentfield varchar({varchar_len})",
						f"parenttype varchar({varchar_len})",
						"index parent(parent)",
					)
				)
				+ ",\n"
			)

		# creating sequence(s)
		if (
			not self.meta.issingle and self.meta.autoname == "autoincrement"
		) or self.doctype in log_types:

			frappe.db.create_sequence(self.doctype, check_not_exists=True, cache=frappe.db.SEQUENCE_CACHE)

			# NOTE: not used nextval func as default as the ability to restore
			# database with sequences has bugs in mariadb and gives a scary error.
			# issue link: https://jira.mariadb.org/browse/MDEV-20070
			name_column = "name bigint primary key"

		# create table
		query = f"""create table `{self.table_name}` (
			{name_column},
			creation datetime(6),
			modified datetime(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus int(1) not null default '0',
			idx int(8) not null default '0',
			{additional_definitions}
			index modified(modified))
			ENGINE={engine}
			ROW_FORMAT=DYNAMIC
			CHARACTER SET=utf8mb4
			COLLATE=utf8mb4_unicode_ci"""

		frappe.db.sql(query)

	def alter(self):
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower()))

		add_column_query = []
		modify_column_query = []
		add_index_query = []
		drop_index_query = []

		columns_to_modify = set(self.change_type + self.add_unique + self.set_default)

		for col in self.add_column:
			add_column_query.append(f"ADD COLUMN `{col.fieldname}` {col.get_definition()}")

		for col in columns_to_modify:
			modify_column_query.append(f"MODIFY `{col.fieldname}` {col.get_definition()}")

		for col in self.add_index:
			# if index key does not exists
			if not frappe.db.has_index(self.table_name, col.fieldname + "_index"):
				add_index_query.append(f"ADD INDEX `{col.fieldname}_index`(`{col.fieldname}`)")

		for col in self.drop_index + self.drop_unique:
			if col.fieldname != "name":  # primary key
				current_column = self.current_columns.get(col.fieldname.lower())
				unique_constraint_changed = current_column.unique != col.unique
				if unique_constraint_changed and not col.unique:
					# nosemgrep
					unique_index_record = frappe.db.sql(
						"""
						SHOW INDEX FROM `{}`
						WHERE Key_name=%s
						AND Non_unique=0
					""".format(
							self.table_name
						),
						(col.fieldname),
						as_dict=1,
					)
					if unique_index_record:
						drop_index_query.append(f"DROP INDEX `{unique_index_record[0].Key_name}`")
				index_constraint_changed = current_column.index != col.set_index
				# if index key exists
				if index_constraint_changed and not col.set_index:
					# nosemgrep
					index_record = frappe.db.sql(
						"""
						SHOW INDEX FROM `{}`
						WHERE Key_name=%s
						AND Non_unique=1
					""".format(
							self.table_name
						),
						(col.fieldname + "_index"),
						as_dict=1,
					)
					if index_record:
						drop_index_query.append(f"DROP INDEX `{index_record[0].Key_name}`")

		try:
			for query_parts in [add_column_query, modify_column_query, add_index_query, drop_index_query]:
				if query_parts:
					query_body = ", ".join(query_parts)
					query = f"ALTER TABLE `{self.table_name}` {query_body}"
					frappe.db.sql(query)

		except Exception as e:
			# sanitize
			if e.args[0] == 1060:
				frappe.throw(str(e))
			elif e.args[0] == 1062:
				fieldname = str(e).split("'")[-2]
				frappe.throw(
					_("{0} field cannot be set as unique in {1}, as there are non-unique existing values").format(
						fieldname, self.table_name
					)
				)
			elif e.args[0] == 1067:
				frappe.throw(str(e.args[1]))
			else:
				raise e
