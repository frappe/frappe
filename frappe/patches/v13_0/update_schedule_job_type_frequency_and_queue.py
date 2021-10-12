
import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'scheduled_job_type')

	for job in frappe.get_all('Scheduled Job Type', ['name', 'frequency']):
		if 'Long' in job.frequency:
			frequency = job.frequency.split(' ')[0]
			frappe.db.set_value('Scheduled Job Type', job.name, 'frequency', frequency, update_modified=0)
			frappe.db.set_value('Scheduled Job Type', job.name, 'queue', 'Long', update_modified=0)