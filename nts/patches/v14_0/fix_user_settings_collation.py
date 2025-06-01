import nts


def execute():
	if nts.db.db_type == "mariadb":
		nts.db.sql(
			"ALTER TABLE __UserSettings CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
		)
