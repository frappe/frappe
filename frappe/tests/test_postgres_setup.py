from unittest.mock import MagicMock, call

from psycopg2 import sql

from frappe.database.postgres.setup_db import _set_database_owner
from frappe.tests import UnitTestCase


class TestPostgresSetup(UnitTestCase):
	def test_database_owner_uses_temporary_membership(self):
		root_conn = MagicMock()
		root_conn.sql.return_value = [False]
		db_name = 'site"database'
		db_user = 'site"user'

		_set_database_owner(root_conn, db_name, db_user, 160000)

		self.assertEqual(
			root_conn.method_calls,
			[
				call.sql(
					"SELECT pg_has_role(current_user, %s, %s)",
					(db_user, "SET"),
					pluck=True,
				),
				call.execute_query(sql.SQL("GRANT {} TO current_user").format(sql.Identifier(db_user))),
				call.execute_query(
					sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
						sql.Identifier(db_name),
						sql.Identifier(db_user),
					)
				),
				call.execute_query(sql.SQL("REVOKE {} FROM current_user").format(sql.Identifier(db_user))),
			],
		)

	def test_database_owner_keeps_existing_membership(self):
		root_conn = MagicMock()
		root_conn.sql.return_value = [True]

		_set_database_owner(root_conn, "site_database", "site_user", 150001)

		self.assertEqual(
			root_conn.method_calls,
			[
				call.sql(
					"SELECT pg_has_role(current_user, %s, %s)",
					("site_user", "MEMBER"),
					pluck=True,
				),
				call.execute_query(
					sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
						sql.Identifier("site_database"),
						sql.Identifier("site_user"),
					)
				),
			],
		)

	def test_database_owner_revokes_membership_after_failure(self):
		root_conn = MagicMock()
		root_conn.sql.return_value = [False]
		root_conn.execute_query.side_effect = (None, RuntimeError("ownership failed"), None)

		with self.assertRaisesRegex(RuntimeError, "ownership failed"):
			_set_database_owner(root_conn, "site_database", "site_user", 160000)

		self.assertEqual(
			root_conn.method_calls,
			[
				call.sql(
					"SELECT pg_has_role(current_user, %s, %s)",
					("site_user", "SET"),
					pluck=True,
				),
				call.execute_query(sql.SQL("GRANT {} TO current_user").format(sql.Identifier("site_user"))),
				call.execute_query(
					sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
						sql.Identifier("site_database"),
						sql.Identifier("site_user"),
					)
				),
				call.execute_query(
					sql.SQL("REVOKE {} FROM current_user").format(sql.Identifier("site_user"))
				),
			],
		)
