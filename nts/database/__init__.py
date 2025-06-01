# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# Database Module
# --------------------
from shutil import which

from nts.database.database import savepoint


def setup_database(force, verbose=None, mariadb_user_host_login_scope=None):
	import nts

	if nts.conf.db_type == "postgres":
		import nts.database.postgres.setup_db

		return nts.database.postgres.setup_db.setup_database()
	else:
		import nts.database.mariadb.setup_db

		return nts.database.mariadb.setup_db.setup_database(force, verbose, mariadb_user_host_login_scope)


def bootstrap_database(verbose=None, source_sql=None):
	import nts

	if nts.conf.db_type == "postgres":
		import nts.database.postgres.setup_db

		return nts.database.postgres.setup_db.bootstrap_database(verbose, source_sql)
	else:
		import nts.database.mariadb.setup_db

		return nts.database.mariadb.setup_db.bootstrap_database(verbose, source_sql)


def drop_user_and_database(db_name, root_login=None, root_password=None):
	import nts

	if nts.conf.db_type == "postgres":
		import nts.database.postgres.setup_db

		return nts.database.postgres.setup_db.drop_user_and_database(db_name, root_login, root_password)
	else:
		import nts.database.mariadb.setup_db

		return nts.database.mariadb.setup_db.drop_user_and_database(db_name, root_login, root_password)


def get_db(host=None, user=None, password=None, port=None, cur_db_name=None, socket=None):
	import nts

	if nts.conf.db_type == "postgres":
		import nts.database.postgres.database

		return nts.database.postgres.database.PostgresDatabase(
			host, user, password, port, cur_db_name, socket
		)
	else:
		import nts.database.mariadb.database

		return nts.database.mariadb.database.MariaDBDatabase(
			host, user, password, port, cur_db_name, socket
		)


def get_command(
	host=None, port=None, user=None, password=None, db_name=None, extra=None, dump=False, socket=None
):
	import nts

	if nts.conf.db_type == "postgres":
		if dump:
			bin, bin_name = which("pg_dump"), "pg_dump"
		else:
			bin, bin_name = which("psql"), "psql"

		if socket and password:
			conn_string = f"postgresql://{user}:{password}@/{db_name}?host={socket}"
		elif socket:
			conn_string = f"postgresql://{user}@/{db_name}?host={socket}"
		elif password:
			conn_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
		else:
			conn_string = f"postgresql://{user}@{host}:{port}/{db_name}"

		command = [conn_string]

		if extra:
			command.extend(extra)

	else:
		if dump:
			bin, bin_name = which("mariadb-dump") or which("mysqldump"), "mariadb-dump"
		else:
			bin, bin_name = which("mariadb") or which("mysql"), "mariadb"

		command = [f"--user={user}"]
		if socket:
			command.append(f"--socket={socket}")
		elif host and port:
			command.append(f"--host={host}")
			command.append(f"--port={port}")

		if password:
			command.append(f"--password={password}")

		if dump:
			command.extend(
				[
					"--single-transaction",
					"--quick",
					"--lock-tables=false",
				]
			)
		else:
			command.extend(
				[
					"--pager=less -SFX",
					"--safe-updates",
					"--no-auto-rehash",
				]
			)

		command.append(db_name)

		if extra:
			command.extend(extra)

	return bin, command, bin_name
