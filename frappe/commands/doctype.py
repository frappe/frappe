# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import sys

import click

import frappe
from frappe.commands import get_site, pass_context


@click.group("doctype")
def doctype_group():
	"Manage DocTypes from their exported JSON files"


@click.command("sync")
@click.argument("target")
@pass_context
def sync_doctype(context, target):
	"""Sync an edited DocType JSON file through the full validated save pipeline.

	TARGET is a DocType name or a path to its exported .json file (required for new
	DocTypes). The save runs validation, database schema sync, controller stub and type
	generation, then re-exports the JSON — renormalizing timestamps, field_order and
	defaults. The last line of output is a machine-readable JSON result; on validation
	failure nothing is saved, the file is left as written, and the command exits non-zero.
	"""
	from frappe.modules.sync_doctype import sync_doctype_from_file
	from frappe.utils.messages import get_message_log

	site = get_site(context)
	try:
		frappe.init(site)
		frappe.connect()
		try:
			result = sync_doctype_from_file(target)
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			output = {
				"synced": False,
				"error_type": type(e).__name__,
				"error": str(e),
				"messages": [m.get("message") for m in get_message_log()],
			}
			click.echo(json.dumps(output, indent=1, default=str))
			sys.exit(1)

		result["synced"] = True
		if result["renormalized"]:
			result["hint"] = (
				"The exported file was renormalized on save; re-read it before making further edits."
			)
		click.echo(json.dumps(result, indent=1, default=str))
	finally:
		frappe.destroy()


doctype_group.add_command(sync_doctype)

commands = [doctype_group]
