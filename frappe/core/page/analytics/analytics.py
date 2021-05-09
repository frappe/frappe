import psutil
import frappe
import time

@frappe.whitelist()
def cpu_data_job():
	while True:
		root_process_count = 0
		user_process_count = 0
		cpu_usage = psutil.cpu_percent()
		cpu_frequency = psutil.cpu_freq()[0]
		for proc in psutil.process_iter(['username']):
			if proc.info['username']== 'root':
				root_process_count += 1
			else:
				user_process_count += 1
		total_process_count = root_process_count + user_process_count
		data = {
			'cpu_usage': cpu_usage,
   			'cpu_frequency': cpu_frequency,
	 		'root_process_count': root_process_count,
			'user_process_count': user_process_count,
			'total_process_count': total_process_count
		}
		frappe.publish_realtime('cpu_page', data)
		time.sleep(3)

@frappe.whitelist()
def run_cpu_job():
    # Running the background job to fetch real time data
	frappe.enqueue('frappe.core.page.analytics.analytics.cpu_data_job')
