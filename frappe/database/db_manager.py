import frappe
from frappe import _


class DbManager:
	def __init__(self, db):
		"""
		Pass root_conn here for access to all databases.
		"""
		if db:
			self.db = db

	def get_current_host(self):
		return self.db.sql("select user()")[0][0].split("@")[1]

	def create_user(self, user, password, host=None):
		host = host or self.get_current_host()
		password_predicate = f" IDENTIFIED BY '{password}'" if password else ""
		self.db.sql(f"CREATE USER IF NOT EXISTS '{user}'@'{host}'{password_predicate}")

	def delete_user(self, target, host=None):
		host = host or self.get_current_host()
		self.db.sql(f"DROP USER IF EXISTS '{target}'@'{host}'")

	def create_database(self, target):
		if target in self.get_database_list():
			self.drop_database(target)
		self.db.sql(f"CREATE DATABASE `{target}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

	def drop_database(self, target):
		self.db.sql_ddl(f"DROP DATABASE IF EXISTS `{target}`")

	def grant_all_privileges(self, target, user, host=None):
		host = host or self.get_current_host()
		permissions = (
			(
				"SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, "
				"CREATE TEMPORARY TABLES, CREATE VIEW, EVENT, TRIGGER, SHOW VIEW, "
				"CREATE ROUTINE, ALTER ROUTINE, EXECUTE, LOCK TABLES"
			)
			if frappe.conf.rds_db
			else "ALL PRIVILEGES"
		)
		self.db.sql(f"GRANT {permissions} ON `{target}`.* TO '{user}'@'{host}'")

	def flush_privileges(self):
		self.db.sql("FLUSH PRIVILEGES")

	def get_database_list(self):
		return self.db.sql("SHOW DATABASES", pluck=True)

	@staticmethod
	def restore_database(verbose, target, source, user, password):
		import shlex
		from shutil import which

		from frappe.database import get_command
		from frappe.utils import execute_in_shell

		command = ["set -o pipefail;"]

		if source.endswith(".gz"):
			if gzip := which("gzip"):
				command.extend([gzip, "-cd", source, "|"])
				source = []
			else:
				raise Exception("`gzip` not installed")

		else:
			source = ["<", source]

		bin, args, bin_name = get_command(
			socket=frappe.conf.db_socket,
			host=frappe.conf.db_host,
			port=frappe.conf.db_port,
			user=user,
			password=password,
			db_name=target,
		)
		if not bin:
			frappe.throw(
				_("{} not found in PATH! This is required to restore the database.").format(bin_name),
				exc=frappe.ExecutableNotFound,
			)
		command.append(bin)
		command.append(shlex.join(args))
		command.extend(source)
		execute_in_shell(" ".join(command), check_exit_code=True, verbose=verbose)
		frappe.cache.delete_keys("")  # Delete all keys associated with this site.
