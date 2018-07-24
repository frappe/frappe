# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import json
from frappe.utils import get_request_session

@frappe.whitelist()
def send_request_for_version_upgrade(preferred_date):
	sess = get_request_session()

	try:
		res = sess.post("htpps://erpnext.com/api/method/central.bench_central.doctype.version_upgrade_request.version_upgrade_request.prepare_version_upgrade_request",
			data= json.dumps({
				'preferred_date': preferred_date,
				'request_from': frappe.session.user,
				'site_name': frappe.local.site
				})
			)
		res.raise_for_status()
		data = res.json()
		
		doc = frappe.get_doc("System Settings")
		doc.sent_version_upgrade_request = 1
		doc.save()

		return data.get('message')
	except Exception:
		frappe.log_error(frappe.get_traceback())
		frappe.db.commit()
	