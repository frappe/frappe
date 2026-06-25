# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.email.inbox import create_email_flag_queue
from frappe.tests import IntegrationTestCase


class TestInbox(IntegrationTestCase):
	def test_create_email_flag_queue_accepts_native_list(self):
		comm = frappe.get_doc(
			doctype="Communication",
			communication_type="Communication",
			content="test inbox flag",
			subject="test inbox flag",
			sent_or_received="Received",
		).insert(ignore_permissions=True)

		# names as a native list instead of a JSON string (frappe.parse_json passthrough);
		# the communication has no uid so it is skipped, but the parse_json loop is exercised
		create_email_flag_queue([comm.name], "Read")
		comm.delete()
