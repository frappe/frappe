# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder import DocType

def execute():
	WorkflowAction = DocType("Workflow Action")
	frappe.qb.update(WorkflowAction).set(WorkflowAction.is_deleted, 0).run()
