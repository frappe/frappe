# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.handler import execute_cmd
from frappe.async import set_task_status, END_LINE, get_std_streams
import frappe.utils.response
import sys


def is_site_in_maintenance_mode(queue, prefix):
	# check if site is in maintenance mode
	site = queue.replace(prefix, "")
	try:
		frappe.init(site=site)
		if not frappe.local.conf.db_name or frappe.local.conf.maintenance_mode or frappe.conf.disable_scheduler:
			# don't add site if in maintenance mode
			return True

	except frappe.IncorrectSitePath:
		return True

	finally:
		frappe.destroy()

	return False

def pull_from_email_account(site, email_account):
	try:
		frappe.init(site=site)
		frappe.connect(site=site)
		email_account = frappe.get_doc("Email Account", email_account)
		email_account.receive()
		frappe.db.commit()
	finally:
		frappe.destroy()

def run_async_task(self, site=None, user=None, cmd=None, form_dict=None, hijack_std=False):
	ret = {}
	frappe.init(site)
	frappe.connect()

	frappe.local.task_id = self.request.id

	if hijack_std:
		original_stdout, original_stderr = sys.stdout, sys.stderr
		sys.stdout, sys.stderr = get_std_streams(self.request.id)
		frappe.local.stdout, frappe.local.stderr = sys.stdout, sys.stderr

	try:
		set_task_status(self.request.id, "Running")
		frappe.db.commit()
		frappe.set_user(user)
		# sleep(60)
		frappe.local.form_dict = frappe._dict(form_dict)
		execute_cmd(cmd, from_async=True)
		ret = frappe.local.response

	except Exception, e:
		frappe.db.rollback()
		ret = frappe.local.response
		http_status_code = getattr(e, "http_status_code", 500)
		ret['status_code'] = http_status_code
		frappe.errprint(frappe.get_traceback())
		frappe.utils.response.make_logs()
		set_task_status(self.request.id, "Error", response=ret)
		frappe.get_logger(__name__).error('Exception in running {}: {}'.format(cmd, ret['exc']))
	else:
		set_task_status(self.request.id, "Success", response=ret)
		if not frappe.flags.in_test:
			frappe.db.commit()
	finally:
		if not frappe.flags.in_test:
			frappe.destroy()
		if hijack_std:
			sys.stdout.write('\n' + END_LINE)
			sys.stderr.write('\n' + END_LINE)
			sys.stdout.close()
			sys.stderr.close()

			sys.stdout, sys.stderr = original_stdout, original_stderr

	return ret

