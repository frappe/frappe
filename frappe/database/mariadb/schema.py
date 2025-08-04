from pymysql.constants.ER import DUP_ENTRY

import frappe
from frappe import _
from frappe.database.schema import DBTable
from frappe.utils.defaults import get_not_null_defaults


class MariaDBTable(DBTable):
	def create(self):
		additional_definitions = []
		engine = self.meta.get("engine") or "InnoDB"
		varchar_len = frappe.db.VARCHAR_LEN
		name_column = f"name varchar({varchar_len}) primary key"

		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			additional_definitions += column_defs

		# index
		index_defs = self.get_index_definitions()
		if index_defs:
			additional_definitions += index_defs

		# child table columns
		if self.meta.get("istable", default=0):
			additional_definitions += [
				f"parent varchar({varchar_len})",
				f"parentfield varchar({varchar_len})",
				f"parenttype varchar({varchar_len})",
				"index parent(parent)",
			]
		else:
			# parent types
			additional_definitions.append("index creation(creation)")
			if self.meta.sort_field == "modified":
				# Support old doctype default by indexing it, also 2nd popular choice.
				additional_definitions.append("index modified(modified)")

		# creating sequence(s)
		if not self.meta.issingle and self.meta.autoname == "autoincrement":
			frappe.db.create_sequence(self.doctype, check_not_exists=True)

			# NOTE: not used nextval func as default as the ability to restore
			# database with sequences has bugs in mariadb and gives a scary error.
			# issue link: https://jira.mariadb.org/browse/MDEV-20070
			name_column = "name bigint primary key"

		elif not self.meta.issingle and self.meta.autoname == "UUID":
			name_column = "name uuid primary key"

		additional_definitions = ",\n".join(additional_definitions)

		# create table
		query = f"""create table `{self.table_name}` (
			{name_column},
			creation datetime(6),
			modified datetime(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus tinyint not null default '0',
			idx int not null default '0',
			{additional_definitions})
			ENGINE={engine}
			ROW_FORMAT={(self.meta.get("row_format") or "Dynamic").upper()}
			CHARACTER SET=utf8mb4
			COLLATE=utf8mb4_unicode_ci"""

		frappe.db.sql_ddl(query)

	def alter(self):
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower()))

		add_column_query = [f"ADD COLUMN `{col.fieldname}` {col.get_definition()}" for col in self.add_column]
		columns_to_modify = set(self.change_type + self.set_default + self.change_nullability)
		modify_column_query = [
			f"MODIFY `{col.fieldname}` {col.get_definition(for_modification=True)}"
			for col in columns_to_modify
		]
		if alter_pk := self.alter_primary_key():
			modify_column_query.append(alter_pk)

		modify_column_query.extend(
			[f"ADD UNIQUE INDEX IF NOT EXISTS {col.fieldname} (`{col.fieldname}`)" for col in self.add_unique]
		)
		add_index_query = [
			f"ADD INDEX `{col.fieldname}_index`(`{col.fieldname}`)"
			for col in self.add_index
			if not frappe.db.get_column_index(self.table_name, col.fieldname, unique=False)
		]

		if self.meta.sort_field == "modified" and not frappe.db.get_column_index(
			self.table_name, "modified", unique=False
		):
			add_index_query.append("ADD INDEX `modified`(`modified`)")

		drop_index_query = []

		for col in {*self.drop_index, *self.drop_unique}:
			if col.fieldname == "name":
				continue

			current_column = self.current_columns.get(col.fieldname.lower())
			unique_constraint_changed = current_column.unique != col.unique
			if unique_constraint_changed and not col.unique:
				if unique_index := frappe.db.get_column_index(self.table_name, col.fieldname, unique=True):
					drop_index_query.append(f"DROP INDEX `{unique_index.Key_name}`")

			index_constraint_changed = current_column.index != col.set_index
			if index_constraint_changed and not col.set_index:
				if index_record := frappe.db.get_column_index(self.table_name, col.fieldname, unique=False):
					drop_index_query.append(f"DROP INDEX `{index_record.Key_name}`")

		for col in self.change_nullability:
			if col.not_nullable:
				try:
					table = frappe.qb.DocType(self.doctype)
					frappe.qb.update(table).set(
						col.fieldname, col.default or get_not_null_defaults(col.fieldtype)
					).where(table[col.fieldname].isnull()).run()
				except Exception:
					print(f"Failed to update data in {self.table_name} for {col.fieldname}")
					raise
		try:
			for query_parts in [add_column_query, modify_column_query, add_index_query, drop_index_query]:
				if query_parts:
					query_body = ", ".join(query_parts)
					query = f"ALTER TABLE `{self.table_name}` {query_body}"
					# nosemgrep
					frappe.db.sql_ddl(query)

		except Exception as e:
			if query := locals().get("query"):  # this weirdness is to avoid potentially unbounded vars
				print(f"Failed to alter schema using query: {query}")

			if e.args[0] == DUP_ENTRY:
				fieldname = str(e).split("'")[-2]
				frappe.throw(
					_(
						"{0} field cannot be set as unique in {1}, as there are non-unique existing values"
					).format(fieldname, self.table_name)
				)

			raise

	def alter_primary_key(self) -> str | None:
		# If there are no values in table allow migrating to UUID from varchar
		autoname = self.meta.autoname
		if autoname == "UUID" and frappe.db.get_column_type(self.doctype, "name") != "uuid":
			if not frappe.db.get_value(self.doctype, {}, order_by=None):
				return "modify name uuid"
			else:
				frappe.throw(
					_("Primary key of doctype {0} can not be changed as there are existing values.").format(
						self.doctype
					)
				)

		# Reverting from UUID to VARCHAR
		if autoname != "UUID" and frappe.db.get_column_type(self.doctype, "name") == "uuid":
			return f"modify name varchar({frappe.db.VARCHAR_LEN})"
