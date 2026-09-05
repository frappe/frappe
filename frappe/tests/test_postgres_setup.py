from unittest.mock import MagicMock, call

from psycopg2 import sql

from frappe.database.postgres.setup_db import _set_database_owner
from frappe.tests import UnitTestCase


class TestPostgresSetup(UnitTestCase):
	def test_database_owner_uses_temporary_membership(self):
		for version in (150001, 160000):
			with self.subTest(version=version):
				root_conn = MagicMock()
				root_conn.sql.side_effect = ([False], [])
				db_name = 'site"database'
				db_user = 'site"user'

				_set_database_owner(root_conn, db_name, db_user, version)

				grant = sql.SQL("GRANT {} TO current_user").format(sql.Identifier(db_user))
				if version >= 160000:
					grant += sql.SQL(" WITH SET TRUE")
				self.assertEqual(
					root_conn.execute_query.call_args_list,
					[
						call(grant),
						call(
							sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
								sql.Identifier(db_name), sql.Identifier(db_user)
							)
						),
						call(sql.SQL("REVOKE {} FROM current_user").format(sql.Identifier(db_user))),
					],
				)

	def test_database_owner_keeps_existing_membership(self):
		for version, privilege in ((150001, "MEMBER"), (160000, "SET")):
			with self.subTest(version=version):
				root_conn = MagicMock()
				root_conn.sql.return_value = [True]

				_set_database_owner(root_conn, "site_database", "site_user", version)

				root_conn.sql.assert_called_once_with(
					"SELECT pg_has_role(current_user, %s, %s)", ("site_user", privilege), pluck=True
				)
				root_conn.execute_query.assert_called_once_with(
					sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
						sql.Identifier("site_database"), sql.Identifier("site_user")
					)
				)

	def test_database_owner_restores_membership_without_set(self):
		for fail in (False, True):
			with self.subTest(fail=fail):
				root_conn = MagicMock()
				root_conn.sql.side_effect = ([False], [1])
				if fail:
					root_conn.execute_query.side_effect = (None, RuntimeError("ownership failed"), None)
					with self.assertRaisesRegex(RuntimeError, "ownership failed"):
						_set_database_owner(root_conn, "site_database", "site_user", 160000)
				else:
					_set_database_owner(root_conn, "site_database", "site_user", 160000)

				grant = sql.SQL("GRANT {} TO current_user").format(sql.Identifier("site_user"))
				self.assertEqual(
					root_conn.execute_query.call_args_list[0], call(grant + sql.SQL(" WITH SET TRUE"))
				)
				self.assertEqual(
					root_conn.execute_query.call_args_list[-1], call(grant + sql.SQL(" WITH SET FALSE"))
				)

	def test_database_owner_revokes_membership_after_failure(self):
		root_conn = MagicMock()
		root_conn.sql.side_effect = ([False], [])
		root_conn.execute_query.side_effect = (None, RuntimeError("ownership failed"), None)

		with self.assertRaisesRegex(RuntimeError, "ownership failed"):
			_set_database_owner(root_conn, "site_database", "site_user", 160000)

		root_conn.execute_query.assert_called_with(
			sql.SQL("REVOKE {} FROM current_user").format(sql.Identifier("site_user"))
		)
