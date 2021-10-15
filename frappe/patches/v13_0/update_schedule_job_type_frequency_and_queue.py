
import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'scheduled_job_type')
	frappe.reload_doc('core', 'doctype', 'server_script')

	for job in frappe.get_all('Scheduled Job Type', ['name', 'frequency']):
		if 'Long' in job.frequency:
			frequency = job.frequency.split(' ')[0]
			frappe.db.set_value('Scheduled Job Type', job.name, {
				'frequency': frequency,
				'queue': 'Long'
			}, update_modified=True)

	for script in frappe.get_all('Server Script', {'script_type': 'Scheduler Event'}, ['name', 'frequency']):
		if 'Long' in script.frequency:
			frequency = script.frequency.split(' ')[0]
			frappe.db.set_value('Server Script', script.name, {
				'frequency': frequency,
				'queue': 'Long'
			}, update_modified=True)