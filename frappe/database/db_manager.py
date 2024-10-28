import os

import frappe


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
		# Create user if it doesn't exist.
		if not host:
			host = self.get_current_host()

		if password:
			self.db.sql("CREATE USER '%s'@'%s' IDENTIFIED BY '%s';" % (user, host, password))
		else:
			self.db.sql("CREATE USER '%s'@'%s';" % (user, host))

	def delete_user(self, target, host=None):
		if not host:
			host = self.get_current_host()
		try:
			self.db.sql("DROP USER '%s'@'%s';" % (target, host))
		except Exception as e:
			if e.args[0] == 1396:
				pass
			else:
				raise

	def create_database(self, target):
		if target in self.get_database_list():
			self.drop_database(target)

		self.db.sql("CREATE DATABASE `%s` ;" % target)

	def drop_database(self, target):
		self.db.sql("DROP DATABASE IF EXISTS `%s`;" % target)

	def grant_all_privileges(self, target, user, host=None):
		if not host:
			host = self.get_current_host()

		if frappe.conf.get("rds_db", 0) == 1:
			self.db.sql(
				"GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, CREATE TEMPORARY TABLES, CREATE VIEW, EVENT, TRIGGER, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, EXECUTE, LOCK TABLES ON `%s`.* TO '%s'@'%s';"
				% (target, user, host)
			)
		else:
			self.db.sql("GRANT ALL PRIVILEGES ON `%s`.* TO '%s'@'%s';" % (target, user, host))

	def flush_privileges(self):
		self.db.sql("FLUSH PRIVILEGES")

	def get_database_list(self):
		"""get list of databases"""
		return [d[0] for d in self.db.sql("SHOW DATABASES")]

	@staticmethod
	def restore_database(target, source, user, password):
		from shutil import which

		from frappe import _
		from frappe.utils import execute_in_shell, make_esc

		esc = make_esc("$ ")

		# Ensure that the entire process fails if any part of the pipeline fails
		command = ["set -o pipefail;"]

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
		bin = (
			"mysql -u {user} -p{password} -h{host} " + ("-P{port}" if frappe.db.port else "") + " {target}"
		)
		bin = bin.format(
			user=esc(user),
			password=esc(password),
			host=esc(frappe.db.host),
			target=esc(target),
			port=frappe.db.port,
		)

		command.append(bin)

		execute_in_shell(" ".join(command), check_exit_code=True, verbose=False)
