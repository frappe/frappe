import frappe


def execute():
	if frappe.db.has_column("Series", "doctype"):
		return

	if frappe.db.db_type == "mariadb":
		frappe.db.sql_ddl(
			"""ALTER TABLE `tabSeries`
			ADD COLUMN `doctype` varchar(140) NOT NULL DEFAULT '' AFTER `name`,
			DROP PRIMARY KEY,
			ADD PRIMARY KEY (`name`, `doctype`)"""
		)
	elif frappe.db.db_type == "postgres":
		frappe.db.sql_ddl(
			"""ALTER TABLE "tabSeries"
			ADD COLUMN "doctype" varchar(140) NOT NULL DEFAULT '',
			DROP CONSTRAINT "tabSeries_pkey",
			ADD PRIMARY KEY ("name", "doctype")"""
		)
	else:
		frappe.db.sql(
			"""CREATE TABLE "tabSeries_new" (
			"name" varchar(100),
			"doctype" varchar(140) NOT NULL DEFAULT '',
			"current" int NOT NULL DEFAULT 0,
			PRIMARY KEY ("name", "doctype"))"""
		)
		frappe.db.sql(
			'INSERT INTO "tabSeries_new" ("name", "current") SELECT "name", "current" FROM "tabSeries"'
		)
		frappe.db.sql('DROP TABLE "tabSeries"')
		frappe.db.sql('ALTER TABLE "tabSeries_new" RENAME TO "tabSeries"')
