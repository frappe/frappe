# Copyright (c) {year}, {app_publisher} and contributors
# For license information, please see license.txt

# import frappe


def execute(filters=None):
	columns, data = [], []
	return columns, data

<<<<<<< HEAD

def execute_synced_report(filters: dict | None = None):
=======
def execute_snapshot_report(filters: dict | None = None):
>>>>>>> 9c477cdb72 (refactor: rename execute_synced_report to execute_snapshot_report)
	"""Return columns and data for the report.

	This is the main entry point for snapshot report. When 'Synced
	Report' is enabled in report, framework will call this method
	every time the report is refreshed or a filter is updated. It
	accepts the same filters as normal execute. But a utility method -
	get_latest_sync, is also imported.

	"""
	from frappe.database.duckdb.database import get_latest_sync

	columns, data = [], []
	return columns, data
