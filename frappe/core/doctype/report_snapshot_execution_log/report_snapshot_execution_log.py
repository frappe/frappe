# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.doctype.report_snapshot.report_snapshot import take_snapshot

class ReportSnapshotExecutionLog(Document):
	def on_update(self):
		# pass
		schedule_next_snapshot_config(self.report_snapshot)

def schedule_next_snapshot_config(snapshot_name):

	query = """
	SELECT 
	start_report_snapshot
	FROM `tabSnappily Flow` snap_flow
	INNER JOIN `tabSnappily` snap
	ON snap.name = snap_flow.parent
	AND snap.disabled = 0
	and snap_flow.on_report_snapshot = %(report_name)s
	"""

	snapshots = frappe.db.sql(query, {'report_name': snapshot_name}, as_dict=1)

	for snap in snapshots:
		take_snapshot(snap.start_report_snapshot)
