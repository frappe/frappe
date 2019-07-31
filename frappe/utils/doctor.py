from __future__ import unicode_literals, print_function
import frappe.utils
from collections import defaultdict
from rq import Worker, Connection
from frappe.utils.background_jobs import get_redis_conn, get_queue, get_queue_list
from frappe.utils.scheduler import is_scheduler_disabled, is_scheduler_inactive
from six import iteritems


def get_workers():
	with Connection(get_redis_conn()):
		workers = Worker.all()
		return workers


def purge_pending_jobs(event=None, site=None, queue=None):
	"""
	Purge tasks of the event event type. Passing 'all' will not purge all
	events but of the all event type, ie. the ones that are enqueued every five
	mintues and would any leave daily, hourly and weekly tasks
	"""
	purged_task_count = 0
	for queue in get_queue_list(queue):
		q = get_queue(queue)
		for job in q.jobs:
			if (site and event):
				if job.kwargs['site'] == site and job.kwargs['event'] == event:
					job.delete()
					purged_task_count+=1
			elif site:
				if job.kwargs['site'] == site:
					job.delete()
					purged_task_count+=1
			elif event:
				if job.kwargs['event'] == event:
					job.delete()
					purged_task_count+=1
			else:
				purged_task_count += q.count
				q.empty()


	return purged_task_count

def get_jobs_by_queue(site=None):
	jobs_per_queue = defaultdict(list)
	job_count = consolidated_methods = {}
	for queue in get_queue_list():
		q = get_queue(queue)
		for job in q.jobs:
			if not site:
				jobs_per_queue[queue].append(job.kwargs.get('method') or job.description)
			elif job.kwargs['site'] == site:
				jobs_per_queue[queue].append(job.kwargs.get('method') or job.description)

		consolidated_methods = {}

		for method in jobs_per_queue[queue]:
			if method not in list(consolidated_methods):
				consolidated_methods[method] = 1
			else:
				consolidated_methods[method] += 1

		job_count[queue] = len(jobs_per_queue[queue])
		jobs_per_queue[queue] = consolidated_methods


	return jobs_per_queue, job_count


def get_pending_jobs(site=None):
	jobs_per_queue = defaultdict(list)
	for queue in get_queue_list():
		q = get_queue(queue)
		for job in q.jobs:
			method_kwargs = job.kwargs['kwargs'] if job.kwargs['kwargs'] else ""
			if job.kwargs['site'] == site:
				jobs_per_queue[queue].append("{0} {1}".
					format(job.kwargs['method'], method_kwargs))

	return jobs_per_queue



def check_number_of_workers():
	return len(get_workers())

def get_running_tasks():
	for worker in get_workers():
		return worker.get_current_job()


def doctor(site=None):
	"""
	Prints diagnostic information for the scheduler
	"""
	with frappe.init_site(site):
		workers_online = check_number_of_workers()
		jobs_per_queue, job_count = get_jobs_by_queue(site)

	print("-----Checking scheduler status-----")
	if site:
		sites = [site]
	else:
		sites = frappe.utils.get_sites()

	for s in sites:
		frappe.init(s)
		frappe.connect()

		if is_scheduler_disabled():
			print("Scheduler disabled for", s)

		if frappe.local.conf.maintenance_mode:
			print("Maintenance mode on for", s)

		if frappe.local.conf.pause_scheduler:
			print("Scheduler paused for", s)

		if is_scheduler_inactive():
			print("Scheduler inactive for", s)

		frappe.destroy()

	# TODO improve this
	print("Workers online:", workers_online)
	print("-----{0} Jobs-----".format(site))
	for queue in get_queue_list():
		if jobs_per_queue[queue]:
			print("Queue:", queue)
			print("Number of Jobs: ", job_count[queue])
			print("Methods:")
			for method, count in iteritems(jobs_per_queue[queue]):
				print("{0} : {1}".format(method, count))
			print("------------")

	return True

def pending_jobs(site=None):
	print("-----Pending Jobs-----")
	pending_jobs = get_pending_jobs(site)
	for queue in get_queue_list():
		if(pending_jobs[queue]):
			print("-----Queue :{0}-----".format(queue))
			print("\n".join(pending_jobs[queue]))

