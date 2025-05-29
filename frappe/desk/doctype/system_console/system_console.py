# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import read_sql, safe_exec


class SystemConsole(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		commit: DF.Check
		console: DF.Code | None
		output: DF.Code | None
		show_processlist: DF.Check
		type: DF.Literal["Python", "SQL"]
	# end: auto-generated types

	def run(self):
		frappe.only_for(["System Manager", "Administrator"])
		try:
			frappe.local.debug_log = []
			if self.type == "Python":
				safe_exec(
					self.console, script_filename="System Console", restrict_commit_rollback=not self.commit
				)
				self.output = "\n".join(frappe.debug_log)
			elif self.type == "SQL":
				self.output = frappe.as_json(read_sql(self.console, as_dict=1))
		except Exception:
			self.commit = False
			self.output = frappe.get_traceback()

		if self.commit:
			frappe.db.commit()
		else:
			frappe.db.rollback()
		frappe.get_doc(
			doctype="Console Log", script=self.console, type=self.type, committed=self.commit
		).insert()
		frappe.db.commit()


@frappe.whitelist()
def execute_code(doc):
	console = frappe.get_doc(json.loads(doc))
	console.run()
	return console.as_dict()


@frappe.whitelist()
def show_processlist():
	frappe.only_for("System Manager")
	return _show_processlist()


def _show_processlist():
	if frappe.db.db_type == "sqlite":
		return []

	return frappe.db.multisql(
		{
			"postgres": """
			SELECT pid AS "Id",
				query_start AS "Time",
				state AS "State",
				query AS "Info",
				wait_event AS "Progress"
			FROM pg_stat_activity""",
			"mariadb": "show full processlist",
		},
		as_dict=True,
	)
