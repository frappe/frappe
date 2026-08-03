from pymysql.constants.ER import DUP_ENTRY

import frappe
from frappe import _
<<<<<<< HEAD
from frappe.database.schema import DBTable
=======
from frappe.database.schema import DbColumn, DBTable
from frappe.query_builder.functions import Trim
from frappe.utils.defaults import get_not_null_defaults
>>>>>>> 7f8057d4d3 (fix: repair unconvertible blank values during migrate)


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
		if self.meta.get("istable") or 0:
			additional_definitions += [
				f"parent varchar({varchar_len})",
				f"parentfield varchar({varchar_len})",
				f"parenttype varchar({varchar_len})",
				"index parent(parent)",
			]
		else:
			# parent types
			additional_definitions.append("index modified(modified)")

		# creating sequence(s)
		if not self.meta.issingle and self.meta.autoname == "autoincrement":
			frappe.db.create_sequence(self.doctype, check_not_exists=True)

			# NOTE: not used nextval func as default as the ability to restore
			# database with sequences has bugs in mariadb and gives a scary error.
			# issue link: https://jira.mariadb.org/browse/MDEV-20070
			name_column = "name bigint primary key"

		additional_definitions = ",\n".join(additional_definitions)

		# create table
		query = f"""create table `{self.table_name}` (
			{name_column},
			creation datetime(6),
			modified datetime(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus int(1) not null default '0',
			idx int(8) not null default '0',
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
		columns_to_modify = set(self.change_type + self.set_default)
		modify_column_query = [
			f"MODIFY `{col.fieldname}` {col.get_definition(for_modification=True)}"
			for col in columns_to_modify
		]
		modify_column_query.extend(
			[f"ADD UNIQUE INDEX IF NOT EXISTS {col.fieldname} (`{col.fieldname}`)" for col in self.add_unique]
		)
		add_index_query = [
			f"ADD INDEX `{col.fieldname}_index`(`{col.fieldname}`)"
			for col in self.add_index
			if not frappe.db.get_column_index(self.table_name, col.fieldname, unique=False)
		]

		if self.meta.sort_field == "creation" and not frappe.db.get_column_index(
			self.table_name, "creation", unique=False
		):
			add_index_query.append("ADD INDEX `creation`(`creation`)")

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

<<<<<<< HEAD
		try:
			for query_parts in [add_column_query, drop_index_query, modify_column_query, add_index_query]:
				if query_parts:
					query_body = ", ".join(query_parts)
					query = f"ALTER TABLE `{self.table_name}` {query_body}"
					frappe.db.sql_ddl(query)
=======
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

		self.run_alter(add_column_query)
		self.run_alter(drop_index_query)
		self.run_alter(modify_column_query)
		self.run_alter(add_index_query)

	def run_alter(self, query_parts: list[str], coerce_blanks: bool = True):
		if not query_parts:
			return

		query = f"ALTER TABLE `{self.table_name}` {', '.join(query_parts)}"

		try:
			# nosemgrep
			frappe.db.sql_ddl(query)
>>>>>>> 7f8057d4d3 (fix: repair unconvertible blank values during migrate)

		except Exception as e:
			print(f"Failed to alter schema using query: {query}")

			if e.args[0] == DUP_ENTRY:
				fieldname = str(e).split("'")[-2]
				frappe.throw(
					_(
						"{0} field cannot be set as unique in {1}, as there are non-unique existing values"
					).format(fieldname, self.table_name)
				)

<<<<<<< HEAD
			raise
=======
			if frappe.db.is_data_truncated(e):
				if frappe.flags.in_migrate and coerce_blanks and self.set_blank_values_to_default():
					self.run_alter(query_parts, coerce_blanks=False)
					return

				frappe.throw(
					_(
						"Cannot change field type in {0}: some existing values cannot be converted to the new type"
					).format(self.doctype),
					title=_("Incompatible Values"),
				)

			raise

	def set_blank_values_to_default(self) -> bool:
		"""Blank out values that only fail to cast because they are empty, so the conversion
		can be retried. Returns whether any row was actually updated."""
		updated = False

		for col in self.change_type:
			if col.fieldtype not in frappe.model.numeric_fieldtypes:
				continue

			current_column = self.current_columns.get(col.fieldname.lower())
			if not current_column or not current_column.type.startswith(("varchar", "char", "text")):
				continue

			table = frappe.qb.DocType(self.doctype)
			field = table[col.fieldname]
			is_blank = Trim(field) == ""

			if not frappe.qb.from_(table).select(field).where(is_blank).limit(1).run():
				continue

			frappe.qb.update(table).set(
				col.fieldname, col.default or get_not_null_defaults(col.fieldtype)
			).where(is_blank).run()
			updated = True

		return updated

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
>>>>>>> 7f8057d4d3 (fix: repair unconvertible blank values during migrate)
