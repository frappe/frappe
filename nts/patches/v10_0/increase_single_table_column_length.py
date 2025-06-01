"""
Run this after updating country_info.json and or
"""
import nts


def execute():
	for col in ("field", "doctype"):
		nts.db.sql_ddl(f"alter table `tabSingles` modify column `{col}` varchar(255)")
