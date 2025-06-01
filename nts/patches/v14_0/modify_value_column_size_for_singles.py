import nts


def execute():
	if nts.db.db_type == "mariadb":
		nts.db.sql_ddl("alter table `tabSingles` modify column `value` longtext")
