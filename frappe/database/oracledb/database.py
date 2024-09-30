import re
import itertools

from typing import Iterable, Sequence, Any

import oracledb

import frappe
from frappe.database.database import Database, INDEX_PATTERN
from frappe.database.db_manager import DbManager
from frappe.database.utils import EmptyQueryValues, LazyDecode
from frappe.utils import cstr, get_table_name, get_datetime, UnicodeWithAttrs
from frappe.database.oracledb.schema import OracleDBTable


class OracleDbManager(DbManager):
	@staticmethod
	def restore_database(verbose: bool, target: str, source: str, user: str,
						 password: str, service_name: str) -> None:

		"""
		Function to restore the given SQL file to the target database.
		:param target: The database to restore to.
		:param source: The SQL dump to restore
		:param user: The database username
		:param password: The database password
		:return: Nothing
		"""

		import shlex
		from shutil import which

		from frappe.database import get_command
		from frappe.utils import execute_in_shell

		# Ensure that the entire process fails if any part of the pipeline fails
		command: list[str] = ["set -o pipefail;"]

		# Handle gzipped backups
		if source.endswith(".gz"):
			if gzip := which("gzip"):
				command.extend([gzip, "-cd", source, "|"])
			else:
				raise Exception("`gzip` not installed")
		else:
			command.extend(["cat", source, "|"])

		# Newer versions of MariaDB add in a line that'll break on older versions, so remove it
		command.extend(["sed", r"'/\/\*M\{0,1\}!999999\\- enable the sandbox mode \*\//d'", "|"])

		# Generate the restore command
		bin, args, bin_name = get_command(
			host=frappe.conf.db_host,
			port=frappe.conf.db_port,
			user=user or frappe.conf.db_name,
			password=password or frappe.conf.db_password,
			db_name=target or frappe.conf.db_name,
			service_name=service_name or frappe.conf.db_service_name
		)
		if not bin:
			return frappe.throw(
				"{} not found in PATH! This is required to restore the database.".format(bin_name),
				exc=frappe.ExecutableNotFound,
			)
		command.append(bin)
		command.append(shlex.join(args))

		execute_in_shell(" ".join(command), check_exit_code=True, verbose=verbose)
		frappe.cache.delete_keys("")  # Delete all keys associated with this site.


class OracleDBExceptionUtil:
	ProgrammingError = oracledb.ProgrammingError
	TableMissingError = oracledb.ProgrammingError
	OperationalError = oracledb.OperationalError
	InternalError = oracledb.InternalError
	DataError = oracledb.DataError
	InterfaceError = oracledb.InterfaceError

	@staticmethod
	def is_deadlocked(e: oracledb.Error) -> bool:
		return 'ORA-00060' in str(e)  # deadlock detected

	@staticmethod
	def is_timedout(e: oracledb.Error) -> bool:
		return 'ORA-01013' in str(e)  # user requested cancel of current operation

	@staticmethod
	def is_read_only_mode_error(e: oracledb.Error) -> bool:
		return 'ORA-16000' in str(e)  # database open for read-only access

	@staticmethod
	def is_table_missing(e: oracledb.Error) -> bool:
		return 'ORA-00942' in str(e)  # table or view does not exist

	@staticmethod
	def is_missing_column(e: oracledb.Error) -> bool:
		return 'ORA-00904' in str(e)  # invalid identifier

	@staticmethod
	def is_duplicate_fieldname(e: oracledb.Error) -> bool:
		return 'ORA-00957' in str(e)  # duplicate column name

	@staticmethod
	def is_duplicate_entry(e: oracledb.Error) -> bool:
		return 'ORA-00001' in str(e)  # unique constraint violated

	@staticmethod
	def is_access_denied(e: oracledb.Error) -> bool:
		return 'ORA-01031' in str(e)  # insufficient privileges

	@staticmethod
	def cant_drop_field_or_key(e: oracledb.Error) -> bool:
		return 'ORA-02449' in str(e)  # cannot drop, column being used

	@staticmethod
	def is_syntax_error(e: oracledb.Error) -> bool:
		return 'ORA-00900' in str(e)  # invalid SQL statement

	@staticmethod
	def is_statement_timeout(e: oracledb.Error) -> bool:
		return 'ORA-01013' in str(e)  # user requested cancel of current operation

	@staticmethod
	def is_data_too_long(e: oracledb.Error) -> bool:
		return 'ORA-01401' in str(e)  # inserted value too large for column

	@staticmethod
	def is_db_table_size_limit(e: oracledb.Error) -> bool:
		return 'ORA-01438' in str(
			e)  # value larger than specified precision allowed for this column

	@staticmethod
	def is_primary_key_violation(e: oracledb.Error) -> bool:
		return OracleDBDatabase.is_duplicate_entry(e)

	@staticmethod
	def is_unique_key_violation(e: oracledb.Error) -> bool:
		return OracleDBDatabase.is_duplicate_entry(e)


class OracleDBConnectionUtil:
	def get_connection(self):
		if hasattr(self, "db_conn"):
			return self.db_conn

		if not hasattr(self, "db_dsn"):
			self.db_dsn = "{}:{}/{}".format(
				self.host, self.port, self.service_name
			)

		conn = oracledb.connect(
			dsn=self.db_dsn,
			user=self.user,
			password=self.password
		)
		self.db_conn = conn

		return self.db_conn

	def get_cursor(self):
		return self.get_connection().cursor()


class OracleDBDatabase(OracleDBExceptionUtil, OracleDBConnectionUtil, Database):
	REGEX_CHARACTER: str = "regexp"
	CONVERSION_MAP: dict = {
		oracledb.DB_TYPE_NUMBER: float,
		oracledb.DB_TYPE_TIMESTAMP: get_datetime,
		UnicodeWithAttrs: oracledb.makedsn,
	}
	default_port = "1521"  # Default OracleDB port

	def setup_type_map(self):
		self.db_type = "oracledb"
		self.type_map = {
			"Currency": ("NUMBER", "21,9"),
			"Int": ("NUMBER", "10"),
			"Long Int": ("NUMBER", "20"),
			"Float": ("NUMBER", "21,9"),
			"Percent": ("NUMBER", "21,9"),
			# todo: Could this be boolean?
			"Check": ("NUMBER", "3,0"),
			"Small Text": ("VARCHAR2", "4000"),
			"Long Text": ("VARCHAR2", "4000"),
			"Code": ("VARCHAR2", "4000"),
			"Text Editor": ("VARCHAR2", "4000"),
			"Markdown Editor": ("VARCHAR2", "4000"),
			"HTML Editor": ("VARCHAR2", "4000"),
			"Date": ("DATE", ""),
			"Datetime": ("TIMESTAMP", "6"),
			"Time": ("TIMESTAMP", "6"),
			"Text": ("VARCHAR2", "4000"),
			"Data": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Link": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Dynamic Link": ("VARCHAR2", self.VARCHAR_LEN, '4000'),
			"Password": ("VARCHAR2", "4000"),
			"Select": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Rating": ("NUMBER", "3,2"),
			"Read Only": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Attach": ("VARCHAR2", "4000"),
			"Attach Image": ("VARCHAR2", "4000"),
			"Signature": ("VARCHAR2", ""),
			"Color": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Barcode": ("VARCHAR2", "4000"),
			"Geolocation": ("VARCHAR2", "4000"),
			"Duration": ("NUMBER", "21,9"),
			"Icon": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Phone": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"Autocomplete": ("VARCHAR2", self.VARCHAR_LEN or '4000'),
			"JSON": ("VARCHAR2", "4000"),
		}

	def get_tables(self, cached=True):

		to_query = not cached

		if cached:
			tables = frappe.cache.get_value("db_tables")
			to_query = not tables

		if to_query:
			table_instance = frappe.qb.Table('all_tables')

			query = frappe.qb.from_(table_instance).select(table_instance.table_name).where(
				table_instance.tablespace_name.notin(["SYSTEM", "SYSAUX"]))

			tables = query.run(pluck=True)
			frappe.cache.set_value("db_tables", tables)

		return tables

	def _create_table_oracle(self, table_name: str, query: str) -> None:
		self.sql_ddl(
			f"""
			BEGIN
				DECLARE
					v_count NUMBER := 0;
				BEGIN
					SELECT COUNT(*)
					INTO v_count
					FROM USER_TABLES
					WHERE TABLE_NAME = '{table_name}';
					IF v_count = 0 THEN
						EXECUTE IMMEDIATE '{query}';
					ELSE
						DBMS_OUTPUT.PUT_LINE('Table {table_name} already exists.');
					END IF;
				END;
			END;
			"""
		)

	def create_auth_table(self) -> None:
		self._create_table_oracle(
			"__Auth",
			"""
			CREATE TABLE "__Auth" (
							"doctype" VARCHAR2(140) NOT NULL,
							"name" VARCHAR2(255) NOT NULL,
							"fieldname" VARCHAR2(140) NOT NULL,
							"password" VARCHAR2(255) NOT NULL,
							"encrypted" NUMBER(1) DEFAULT 0 NOT NULL,
							PRIMARY KEY ("doctype", "name", "fieldname"))
			"""
		)

	# self.sql_ddl("""
	# 	CREATE TABLE "__Auth" (
	# 	"doctype" VARCHAR2(140) NOT NULL,
	# 	"name" VARCHAR2(255) NOT NULL,
	# 	"fieldname" VARCHAR2(140) NOT NULL,
	# 	"password" VARCHAR2(255) NOT NULL,
	# 	"encrypted" NUMBER(1) DEFAULT 0 NOT NULL,
	# 	PRIMARY KEY ("doctype", "name", "fieldname")
	# 	)
	# 	""")

	def create_global_search_table(self) -> None:
		if "__global_search" not in self.get_tables():
			self.sql("""
				CREATE TABLE "__global_search" (
				"doctype" VARCHAR2(100),
				"name" VARCHAR2(255),
				"title" VARCHAR2(255),
				"content" VARCHAR2(255),
				"route" VARCHAR2(255),
				"published" NUMBER(1) DEFAULT 0 NOT NULL,
				CONSTRAINT "doctype_name" UNIQUE ("doctype", "name")
				)
				""")

	def create_user_settings_table(self) -> None:
		self._create_table_oracle(
			"__UserSettings",
			"""CREATE TABLE "__UserSettings" (
				"user" VARCHAR2(180) NOT NULL,
				"doctype" VARCHAR2(180) NOT NULL,
				"data" VARCHAR2(4000),
				UNIQUE("user", "doctype"))
		""")

	def get_table_columns_description(self, table_name: str):
		# TODO: Below Query written by Mayank, which is not logically same with other database queries.
		return self.sql(
			f"""
			SELECT column_name AS "name",
			table_name AS "table",
			data_type AS "type",
			CASE WHEN (nullable = 'N') THEN 1 ELSE 0 end AS "not_nullable",
			data_default AS "default",
						CASE WHEN (SELECT CASE WHEN uc.constraint_type = 'U' THEN 1 ELSE 0 end
								FROM user_cons_columns ucc INNER JOIN user_constraints uc
								ON ucc.constraint_name = uc.constraint_name
								WHERE ucc.table_name = utc.table_name
								AND ucc.column_name = utc.column_name
								AND uc.constraint_type != 'C'
							) = 1 THEN 1 ELSE 0 END AS "unique",
							CASE WHEN (SELECT CASE WHEN uic.column_position = 1 THEN 1 ELSE 0 end
								FROM user_ind_columns uic
								JOIN user_indexes ui
								ON uic.index_name = ui.index_name
								WHERE ui.uniqueness = 'NONUNIQUE'
								AND uic.column_name = utc.COLUMN_NAME
								AND uic.table_name = utc.TABLE_NAME
							) = 1 THEN 'true' ELSE 'false' end AS "index"
			FROM user_tab_columns utc
			WHERE utc.table_name = '{table_name}'""", as_dict=True)

	def updatedb(self, doctype, meta=None):
		"""
		Syncs a `DocType` to the table
		* creates if required
		* updates columns
		* updates indices"""
		res = self.sql('SELECT "issingle" FROM {}."tabDocType" WHERE "name" = {}'.format(
			frappe.conf.db_name.upper(), f"'{doctype}'"), []
		)
		if not res:
			raise Exception(f'Wrong doctype {doctype} in updatedb')

		if not res[0][0]:
			db_table = OracleDBTable(doctype, meta)
			db_table.validate()
			db_table.sync()
			self.commit()

	def escape(self, s, percent=True):
		if isinstance(s, bytes):
			s = s.decode("utf-8")
		if percent:
			s = s.replace('%', '%%')
		if s == "":
			return "NULL"
		return "'" + s + "'"

	def get_db_table_columns(self, table) -> list[str]:
		columns = frappe.cache.hget("table_columns", table)
		if columns is None:
			user_tab_columns = frappe.qb.Table("user_tab_columns")

			columns = (
				frappe.qb.from_(user_tab_columns)
				.select(user_tab_columns.column_name)
				.where(user_tab_columns.table_name == table)
				.run(pluck=True)
			)

			if columns:
				frappe.cache.hset("table_columns", table, columns)

		return columns

	def add_index(self, doctype: str, fields: list, index_name: str = None):
		table_name = get_table_name(doctype)
		index_name = index_name or table_name + '_' + "_".join(fields) + "_index"
		index_name = INDEX_PATTERN.sub(r"", index_name)
		if not self.has_index(table_name, index_name, fields):
			self.commit()
			fields = ['"' + i + '"' for i in fields]
			self.sql(f'CREATE INDEX "{index_name}" ON "{table_name}" ({", ".join(fields)})')

	def has_index(self, table_name, index_name, fields=None):
		"""
		Check if a table has a specific index.
		"""
		if not fields:
			result = self.sql(f"""
			SELECT index_name from USER_IND_COLUMNS
			WHERE table_name = '{table_name}' AND index_name = '{index_name}'
			""")
		else:
			if len(fields) == 1:
				field_string = f" = '{fields[0]}'  "
			else:
				field_string = f' IN {tuple(fields)}  '
			result = self.sql("""
			SELECT count(column_name)
			FROM USER_IND_COLUMNS WHERE column_name """ + field_string +
							  f"""AND table_name = '{table_name}'
			GROUP  BY index_name, table_name
			""", pluck=True)
		print(f'Index check {result}')
		return bool(result)

	def add_unique(self, doctype, fields, constraint_name=None):
		table_name = get_table_name(doctype)
		constraint_name = constraint_name or "unique_" + "_".join(fields)
		fields = ['"' + i + '"' for i in fields]
		fields_sql = ', '.join(fields)
		if not self.sql(f"""
		SELECT CONSTRAINT_NAME FROM user_constraints
		WHERE table_name = '{table_name}' AND CONSTRAINT_TYPE = 'U' AND CONSTRAINT_NAME = '{constraint_name}'
		"""):
			self.commit()
			self.sql(
				f'ALTER TABLE "{table_name}" ADD CONSTRAINT "{constraint_name}" UNIQUE ({fields_sql})')

	def bulk_insert(
		self,
		doctype: str,
		fields: list[str],
		values: Iterable[Sequence[Any]],
		ignore_duplicates=False,
		*,
		chunk_size=3,
	):


		"""
		Insert multiple records at a time

		:param doctype: Doctype name
		:param fields: list of fields
		:params values: iterable of values
		"""
		table = frappe.qb.DocType(doctype)

		query = frappe.qb.into(table).columns(fields)

		if ignore_duplicates:
			# Pypika does not have same api for ignoring duplicates
			if frappe.conf.db_type == "mariadb":
				query = query.ignore()
			elif frappe.conf.db_type == "postgres":
				query = query.on_conflict().do_nothing()

		value_iterator = iter(values)
		_fields = ",".join(f'"{i}"' for i in fields)
		while value_chunk := tuple(itertools.islice(value_iterator, chunk_size)):
			insert_bulk_query = """
			INSERT ALL
			 {}
			 SELECT * FROM DUAL
			 """.format(" ".join(
				f'INTO {frappe.conf.db_name.upper()}."{query._insert_table.alias}" ({_fields}) VALUES ({",".join([self.check_dateformat(value) for value in row])}) '
				for row in value_chunk
			))

			frappe.db.sql(
				insert_bulk_query,
				[]
			)
			# query.insert(*(
			# tuple([self.check_dateformat(value) for value in row])
			# for row in value_chunk
			# )).run()

	@staticmethod
	def check_dateformat(value):
		if value is None:
			return 'NULL'
		if not isinstance(value, str):
			return str(value)
		if re.search('\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+', value):  # noqa: W605
			return f"to_timestamp('{value}', 'yyyy-mm-dd hh24:mi:ss.ff6')"
		elif re.search('\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', value):  # noqa: W605
			return f"to_timestamp('{value}', 'yyyy-mm-dd hh24:mi:ss')"
		return "'{}'".format(value.replace("'", "''"))
