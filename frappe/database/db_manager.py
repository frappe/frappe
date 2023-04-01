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
		host = host or self.get_current_host()
		password_predicate = f" IDENTIFIED BY '{password}'" if password else ""
		self.db.sql(f"CREATE USER '{user}'@'{host}'{password_predicate}")

	def delete_user(self, target, host=None):
		host = host or self.get_current_host()
		self.db.sql(f"DROP USER IF EXISTS '{target}'@'{host}'")

	def create_database(self, target):
		if target in self.get_database_list():
			self.drop_database(target)
		self.db.sql(f"CREATE DATABASE `{target}`")

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
	def restore_database(target, source, user, password):
		import os
		from shutil import which

		from frappe.utils import make_esc

		esc = make_esc("$ ")
		pv = which("pv")

		if pv:
			pipe = f"{pv} {source} |"
			source = ""
		else:
			pipe = ""
			source = f"< {source}"

		if pipe:
			print("Restoring Database file...")

		args = {
			"pipe": pipe,
			"user": esc(user),
			"password": esc(password),
			"target": esc(target),
			"source": source,
		}

		command = "{pipe} mysql -u {user} -p{password} "
		if frappe.db.socket:
			command += " -S{socket} "
			args["socket"] = esc(frappe.db.socket)
		elif frappe.db.port:
			command += " -h{host} "
			command += " -p{host} "
			args["host"] = esc(frappe.db.host)
			args["port"] = esc(frappe.db.port)
		else:
			command += " -h{host} "
			args["host"] = esc(frappe.db.host)

		command += " {target} {source}"
		os.system(command.format(**args))
