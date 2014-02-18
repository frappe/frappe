from __future__ import unicode_literals
from frappe.celery import app
import frappe
from frappe.cli import get_sites

@app.task()
def scheduler_task(site, event, handler):
	from frappe.utils.scheduler import log
	traceback = ""
	try:
		frappe.init(site=site)
		frappe.get_attr(handler)()
		frappe.conn.commit()
	except Exception:
		traceback += log("Method: {event}, Handler: {handler}".format(event=event, handler=handler))
		traceback += log(frappe.get_traceback())
		frappe.conn.rollback()
	# TODO: use logger
	print 'ran {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event)

@app.task()
def enqueue_scheduler_events():
	import frappe
	from frappe.utils.scheduler import execute
	for site in get_sites():
		execute(site)
