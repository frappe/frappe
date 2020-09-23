#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

class TestDB(unittest.TestCase):
	def test_get_value(self):
		self.assertEqual(frappe.db.get_value("User", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEqual(frappe.db.get_value("User", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertNotEquals(frappe.db.get_value("User", {"name": ["!=", "Guest"]}), "Guest")
		self.assertEqual(frappe.db.get_value("User", {"name": ["<", "B"]}), "Administrator")
		self.assertEqual(frappe.db.get_value("User", {"name": ["<=", "Administrator"]}), "Administrator")

		self.assertEqual(frappe.db.sql("""SELECT name FROM `tabUser` WHERE name > 's' ORDER BY MODIFIED DESC""")[0][0],
			frappe.db.get_value("User", {"name": [">", "s"]}))

		self.assertEqual(frappe.db.sql("""SELECT name FROM `tabUser` WHERE name >= 't' ORDER BY MODIFIED DESC""")[0][0],
			frappe.db.get_value("User", {"name": [">=", "t"]}))

	def test_set_value(self):
		todo1 = frappe.get_doc(dict(doctype='ToDo', description = 'test_set_value 1')).insert()
		todo2 = frappe.get_doc(dict(doctype='ToDo', description = 'test_set_value 2')).insert()

		frappe.db.set_value('ToDo', todo1.name, 'description', 'test_set_value change 1')
		self.assertEqual(frappe.db.get_value('ToDo', todo1.name, 'description'), 'test_set_value change 1')

		# multiple set-value
		frappe.db.set_value('ToDo', dict(description=('like', '%test_set_value%')),
			'description', 'change 2')

		self.assertEqual(frappe.db.get_value('ToDo', todo1.name, 'description'), 'change 2')
		self.assertEqual(frappe.db.get_value('ToDo', todo2.name, 'description'), 'change 2')


	def test_escape(self):
		frappe.db.escape("香港濟生堂製藥有限公司 - IT".encode("utf-8"))

	def test_get_single_value(self):
		frappe.db.set_value('System Settings', 'System Settings', 'backup_limit', 5)
		frappe.db.commit()

		limit = frappe.db.get_single_value('System Settings', 'backup_limit')
		self.assertEqual(limit, 5)

	def test_log_touched_tables(self):
		frappe.flags.in_migrate = True
		frappe.flags.touched_tables = set()
		frappe.db.set_value('System Settings', 'System Settings', 'backup_limit', 5)
		self.assertIn('tabSingles', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		todo = frappe.get_doc({'doctype': 'ToDo', 'description': 'Random Description'})
		todo.save()
		self.assertIn('tabToDo', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		todo.description = "Another Description"
		todo.save()
		self.assertIn('tabToDo', frappe.flags.touched_tables)

		if frappe.db.db_type != "postgres":
			frappe.flags.touched_tables = set()
			frappe.db.sql("UPDATE tabToDo SET description = 'Updated Description'")
			self.assertNotIn('tabToDo SET', frappe.flags.touched_tables)
			self.assertIn('tabToDo', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		todo.delete()
		self.assertIn('tabToDo', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		create_custom_field('ToDo', {'label': 'ToDo Custom Field'})

		self.assertIn('tabToDo', frappe.flags.touched_tables)
		self.assertIn('tabCustom Field', frappe.flags.touched_tables)
		frappe.flags.in_migrate = False
		frappe.flags.touched_tables.clear()


	def test_db_keywords_as_fields(self):
		"""Tests if DB keywords work as docfield names. If they're wrapped with grave accents."""
		all_keywords = {
			"mariadb": ["ADD", "ALL", "ALTER", "ANALYZE", "AND", "AS", "ASC", "AUTO_INCREMENT", "BDB", "BERKELEYDB", "BETWEEN", "BIGINT", "BINARY", "BLOB", "BOTH", "BTREE", "BY", "CASCADE", "CASE", "CHANGE", "CHAR", "CHARACTER", "CHECK", "COLLATE", "COLUMN", "COLUMNS", "CONSTRAINT", "CREATE", "CROSS", "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP", "DATABASE", "DATABASES", "DAY_HOUR", "DAY_MINUTE", "DAY_SECOND", "DEC", "DECIMAL", "DEFAULT", "DELAYED", "DELETE", "DESC", "DESCRIBE", "DISTINCT", "DISTINCTROW", "DIV", "DOUBLE", "DROP", "ELSE", "ENCLOSED", "ERRORS", "ESCAPED", "EXISTS", "EXPLAIN", "FALSE", "FIELDS", "FLOAT", "FOR", "FORCE", "FOREIGN", "FROM", "FULLTEXT", "FUNCTION", "GEOMETRY", "GRANT", "GROUP", "HASH", "HAVING", "HELP", "HIGH_PRIORITY", "HOUR_MINUTE", "HOUR_SECOND", "IF", "IGNORE", "IN", "INDEX", "INFILE", "INNER", "INNODB", "INSERT", "INT", "INTEGER", "INTERVAL", "INTO", "IS", "JOIN", "KEY", "KEYS", "KILL", "LEADING", "LEFT", "LIKE", "LIMIT", "LINES", "LOAD", "LOCALTIME", "LOCALTIMESTAMP", "LOCK", "LONG", "LONGBLOB", "LONGTEXT", "LOW_PRIORITY", "MASTER_SERVER_ID", "MATCH", "MEDIUMBLOB", "MEDIUMINT", "MEDIUMTEXT", "MIDDLEINT", "MINUTE_SECOND", "MOD", "MRG_MYISAM", "NATURAL", "NOT", "NULL", "NUMERIC", "ON", "OPTIMIZE", "OPTION", "OPTIONALLY", "OR", "ORDER", "OUTER", "OUTFILE", "PRECISION", "PRIMARY", "PRIVILEGES", "PROCEDURE", "PURGE", "READ", "REAL", "REFERENCES", "REGEXP", "RENAME", "REPLACE", "REQUIRE", "RESTRICT", "RETURNS", "REVOKE", "RIGHT", "RLIKE", "RTREE", "SELECT", "SET", "SHOW", "SMALLINT", "SOME", "SONAME", "SPATIAL", "SQL_BIG_RESULT", "SQL_CALC_FOUND_ROWS", "SQL_SMALL_RESULT", "SSL", "STARTING", "STRAIGHT_JOIN", "STRIPED", "TABLE", "TABLES", "TERMINATED", "THEN", "TINYBLOB", "TINYINT", "TINYTEXT", "TO", "TRAILING", "TRUE", "TYPES", "UNION", "UNIQUE", "UNLOCK", "UNSIGNED", "UPDATE", "USAGE", "USE", "USER_RESOURCES", "USING", "VALUES", "VARBINARY", "VARCHAR", "VARCHARACTER", "VARYING", "WARNINGS", "WHEN", "WHERE", "WITH", "WRITE", "XOR", "YEAR_MONTH", "ZEROFILL"],
			"postgres": ["ABORT", "ABS", "ABSOLUTE", "ACCESS", "ACTION", "ADA", "ADD", "ADMIN", "AFTER", "AGGREGATE", "ALIAS", "ALL", "ALLOCATE", "ALTER", "ANALYSE", "ANALYZE", "AND", "ANY", "ARE", "ARRAY", "AS", "ASC", "ASENSITIVE", "ASSERTION", "ASSIGNMENT", "ASYMMETRIC", "AT", "ATOMIC", "AUTHORIZATION", "AVG", "BACKWARD", "BEFORE", "BEGIN", "BETWEEN", "BIGINT", "BINARY", "BIT", "BITVAR", "BIT_LENGTH", "BLOB", "BOOLEAN", "BOTH", "BREADTH", "BY", "CACHE", "CALL", "CALLED", "CARDINALITY", "CASCADE", "CASCADED", "CASE", "CAST", "CATALOG", "CATALOG_NAME", "CHAIN", "CHAR", "CHARACTER", "CHARACTERISTICS", "CHARACTER_LENGTH", "CHARACTER_SET_CATALOG", "CHARACTER_SET_NAME", "CHARACTER_SET_SCHEMA", "CHAR_LENGTH", "CHECK", "CHECKED", "CHECKPOINT", "CLASS", "CLASS_ORIGIN", "CLOB", "CLOSE", "CLUSTER", "COALESCE", "COBOL", "COLLATE", "COLLATION", "COLLATION_CATALOG", "COLLATION_NAME", "COLLATION_SCHEMA", "COLUMN", "COLUMN_NAME", "COMMAND_FUNCTION", "COMMAND_FUNCTION_CODE", "COMMENT", "COMMIT", "COMMITTED", "COMPLETION", "CONDITION_NUMBER", "CONNECT", "CONNECTION", "CONNECTION_NAME", "CONSTRAINT", "CONSTRAINTS", "CONSTRAINT_CATALOG", "CONSTRAINT_NAME", "CONSTRAINT_SCHEMA", "CONSTRUCTOR", "CONTAINS", "CONTINUE", "CONVERSION", "CONVERT", "COPY", "CORRESPONDING", "COUNT", "CREATE", "CREATEDB", "CREATEUSER", "CROSS", "CUBE", "CURRENT", "CURRENT_DATE", "CURRENT_PATH", "CURRENT_ROLE", "CURRENT_TIME", "CURRENT_TIMESTAMP", "CURRENT_USER", "CURSOR", "CURSOR_NAME", "CYCLE", "DATA", "DATABASE", "DATE", "DATETIME_INTERVAL_CODE", "DATETIME_INTERVAL_PRECISION", "DAY", "DEALLOCATE", "DEC", "DECIMAL", "DECLARE", "DEFAULT", "DEFERRABLE", "DEFERRED", "DEFINED", "DEFINER", "DELETE", "DELIMITER", "DELIMITERS", "DEPTH", "DEREF", "DESC", "DESCRIBE", "DESCRIPTOR", "DESTROY", "DESTRUCTOR", "DETERMINISTIC", "DIAGNOSTICS", "DICTIONARY", "DISCONNECT", "DISPATCH", "DISTINCT", "DO", "DOMAIN", "DOUBLE", "DROP", "DYNAMIC", "DYNAMIC_FUNCTION", "DYNAMIC_FUNCTION_CODE", "EACH", "ELSE", "ENCODING", "ENCRYPTED", "END", "EQUALS", "ESCAPE", "EVERY", "EXCEPT", "EXCEPTION", "EXCLUSIVE", "EXEC", "EXECUTE", "EXISTING", "EXISTS", "EXPLAIN", "EXTERNAL", "EXTRACT", "FALSE", "FETCH", "FINAL", "FIRST", "FLOAT", "FOR", "FORCE", "FOREIGN", "FORTRAN", "FORWARD", "FOUND", "FREE", "FREEZE", "FROM", "FULL", "FUNCTION", "GENERAL", "GENERATED", "GET", "GLOBAL", "GO", "GOTO", "GRANT", "GRANTED", "GROUP", "GROUPING", "HANDLER", "HAVING", "HIERARCHY", "HOLD", "HOST", "HOUR", "IDENTITY", "IGNORE", "ILIKE", "IMMEDIATE", "IMMUTABLE", "IMPLEMENTATION", "IMPLICIT", "IN", "INCREMENT", "INDEX", "INDICATOR", "INFIX", "INHERITS", "INITIALIZE", "INITIALLY", "INNER", "INOUT", "INPUT", "INSENSITIVE", "INSERT", "INSTANCE", "INSTANTIABLE", "INSTEAD", "INT", "INTEGER", "INTERSECT", "INTERVAL", "INTO", "INVOKER", "IS", "ISNULL", "ISOLATION", "ITERATE", "JOIN", "KEY", "KEY_MEMBER", "KEY_TYPE", "LANCOMPILER", "LANGUAGE", "LARGE", "LAST", "LATERAL", "LEADING", "LEFT", "LENGTH", "LESS", "LEVEL", "LIKE", "LIMIT", "LISTEN", "LOAD", "LOCAL", "LOCALTIME", "LOCALTIMESTAMP", "LOCATION", "LOCATOR", "LOCK", "LOWER", "MAP", "MATCH", "MAX", "MAXVALUE", "MESSAGE_LENGTH", "MESSAGE_OCTET_LENGTH", "MESSAGE_TEXT", "METHOD", "MIN", "MINUTE", "MINVALUE", "MOD", "MODE", "MODIFIES", "MODIFY", "MODULE", "MONTH", "MORE", "MOVE", "MUMPS", "NAME", "NAMES", "NATIONAL", "NATURAL", "NCHAR", "NCLOB", "NEW", "NEXT", "NO", "NOCREATEDB", "NOCREATEUSER", "NONE", "NOT", "NOTHING", "NOTIFY", "NOTNULL", "NULL", "NULLABLE", "NULLIF", "NUMBER", "NUMERIC", "OBJECT", "OCTET_LENGTH", "OF", "OFF", "OFFSET", "OIDS", "OLD", "ON", "ONLY", "OPEN", "OPERATION", "OPERATOR", "OPTION", "OPTIONS", "OR", "ORDER", "ORDINALITY", "OUT", "OUTER", "OUTPUT", "OVERLAPS", "OVERLAY", "OVERRIDING", "OWNER", "PAD", "PARAMETER", "PARAMETERS", "PARAMETER_MODE", "PARAMETER_NAME", "PARAMETER_ORDINAL_POSITION", "PARAMETER_SPECIFIC_CATALOG", "PARAMETER_SPECIFIC_NAME", "PARAMETER_SPECIFIC_SCHEMA", "PARTIAL", "PASCAL", "PASSWORD", "PATH", "PENDANT", "PLACING", "PLI", "POSITION", "POSTFIX", "PRECISION", "PREFIX", "PREORDER", "PREPARE", "PRESERVE", "PRIMARY", "PRIOR", "PRIVILEGES", "PROCEDURAL", "PROCEDURE", "PUBLIC", "READ", "READS", "REAL", "RECHECK", "RECURSIVE", "REF", "REFERENCES", "REFERENCING", "REINDEX", "RELATIVE", "RENAME", "REPEATABLE", "REPLACE", "RESET", "RESTRICT", "RESULT", "RETURN", "RETURNED_LENGTH", "RETURNED_OCTET_LENGTH", "RETURNED_SQLSTATE", "RETURNS", "REVOKE", "RIGHT", "ROLE", "ROLLBACK", "ROLLUP", "ROUTINE", "ROUTINE_CATALOG", "ROUTINE_NAME", "ROUTINE_SCHEMA", "ROW", "ROWS", "ROW_COUNT", "RULE", "SAVEPOINT", "SCALE", "SCHEMA", "SCHEMA_NAME", "SCOPE", "SCROLL", "SEARCH", "SECOND", "SECTION", "SECURITY", "SELECT", "SELF", "SENSITIVE", "SEQUENCE", "SERIALIZABLE", "SERVER_NAME", "SESSION", "SESSION_USER", "SET", "SETOF", "SETS", "SHARE", "SHOW", "SIMILAR", "SIMPLE", "SIZE", "SMALLINT", "SOME", "SOURCE", "SPACE", "SPECIFIC", "SPECIFICTYPE", "SPECIFIC_NAME", "SQL", "SQLCODE", "SQLERROR", "SQLEXCEPTION", "SQLSTATE", "SQLWARNING", "STABLE", "START", "STATE", "STATEMENT", "STATIC", "STATISTICS", "STDIN", "STDOUT", "STORAGE", "STRICT", "STRUCTURE", "STYLE", "SUBCLASS_ORIGIN", "SUBLIST", "SUBSTRING", "SUM", "SYMMETRIC", "SYSID", "SYSTEM", "SYSTEM_USER", "TABLE", "TABLE_NAME", "TEMP", "TEMPLATE", "TEMPORARY", "TERMINATE", "THAN", "THEN", "TIME", "TIMESTAMP", "TIMEZONE_HOUR", "TIMEZONE_MINUTE", "TO", "TOAST", "TRAILING", "TRANSACTION", "TRANSACTIONS_COMMITTED", "TRANSACTIONS_ROLLED_BACK", "TRANSACTION_ACTIVE", "TRANSFORM", "TRANSFORMS", "TRANSLATE", "TRANSLATION", "TREAT", "TRIGGER", "TRIGGER_CATALOG", "TRIGGER_NAME", "TRIGGER_SCHEMA", "TRIM", "TRUE", "TRUNCATE", "TRUSTED", "TYPE", "UNCOMMITTED", "UNDER", "UNENCRYPTED", "UNION", "UNIQUE", "UNKNOWN", "UNLISTEN", "UNNAMED", "UNNEST", "UNTIL", "UPDATE", "UPPER", "USAGE", "USER", "USER_DEFINED_TYPE_CATALOG", "USER_DEFINED_TYPE_NAME", "USER_DEFINED_TYPE_SCHEMA", "USING", "VACUUM", "VALID", "VALIDATOR", "VALUE", "VALUES", "VARCHAR", "VARIABLE", "VARYING", "VERBOSE", "VERSION", "VIEW", "VOLATILE", "WHEN", "WHENEVER", "WHERE", "WITH", "WITHOUT", "WORK", "WRITE", "YEAR", "ZONE"]
		}
		all_doctypes = []
		fieldnames = all_keywords[frappe.conf.db_type]

		def batch(iterable, n=1):
			total = len(iterable)
			for ndx in range(0, total, n):
				yield iterable[ndx:min(ndx + n, total)]

		for i, fields in enumerate(batch(fieldnames, n=20)):
			new_doctype = frappe.get_doc({
				"doctype": "DocType",
				"name": "Keywords Test {0}".format(i + 1),
				"module": "Custom",
				"custom": 1,
				"fields": []
			})

			for field in fields:
				new_doctype.fields.append({
					"label": field.title(),
					"fieldname": field.lower(),
					"fieldtype": "Data"
				})

			new_doctype.insert()
			all_doctypes.append(new_doctype.name)

		for doctype in all_doctypes:
			frappe.delete_doc("DocType", doctype)

