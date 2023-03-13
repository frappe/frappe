import os

import frappe
from frappe.utils import add_to_date, today


def execute():
	"""Due to large size of log tables on old sites some table cleanups never
	finished during daily log clean up. This patch discards such data by using
	"big delete" code.


	This is "special" version of generic patch found in v14

	https://github.com/frappe/frappe/blob/develop/frappe/patches/v14_0/clear_long_pending_stale_logs.py
	"""

	retention = get_current_setting("clear_email_queue_after") or 30

	if not is_log_cleanup_stuck("Email Queue", retention):
		return

	clear_log_table("Email Queue", retention)
	clear_log_table("Email Queue Recipient", retention)


def clear_log_table(doctype, days=90):
	"""If any logtype table grows too large then clearing it with DELETE query
	is not feasible in reasonable time. This command copies recent data to new
	table and replaces current table with new smaller table.
	ref: https://mariadb.com/kb/en/big-deletes/#deleting-more-than-half-a-table
	"""
	from frappe.utils import get_table_name

	original = get_table_name(doctype)
	temporary = f"{original} temp_table"
	backup = f"{original} backup_table"

	try:
		frappe.db.sql_ddl(f"CREATE TABLE `{temporary}` LIKE `{original}`")

		# Copy all recent data to new table
		frappe.db.sql(
			f"""INSERT INTO `{temporary}`
				SELECT * FROM `{original}`
				WHERE `{original}`.`modified` > NOW() - INTERVAL '{days}' DAY"""
		)
		frappe.db.sql_ddl(f"RENAME TABLE `{original}` TO `{backup}`, `{temporary}` TO `{original}`")
	except Exception:
		frappe.db.rollback()
		frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{temporary}`")
		raise
	else:
		frappe.db.sql_ddl(f"DROP TABLE `{backup}`")


def is_log_cleanup_stuck(doctype, retention):
	"""Check if doctype has data significantly older than configured cleanup period"""
	threshold = add_to_date(today(), days=retention * -2)

	in_patch_test = os.environ.get("CI")

	return bool(frappe.db.get_value(doctype, {"modified": ("<", threshold)})) or bool(in_patch_test)


def get_current_setting(fieldname):
	try:
		return frappe.db.get_single_value("Log Settings", fieldname)
	except Exception:
		# Field might be gone if patch is reattempted
		pass
