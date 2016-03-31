from __future__ import unicode_literals
import frappe.utils
from collections import defaultdict
from rq import Worker, Connection
from frappe.utils.background_jobs import get_redis_conn, get_queue, get_queue_list, get_jobs
from frappe.utils.scheduler import is_scheduler_disabled


def get_workers():
	with Connection(get_redis_conn()):
		workers = Worker.all()
		return workers


def purge_pending_tasks(event=None, site=None, queue=None):
	"""
	Purge tasks of the event event type. Passing 'all' will not purge all
	events but of the all event type, ie. the ones that are enqueued every five
	mintues and would any leave daily, hourly and weekly tasks
	"""
	purged_task_count = 0
	for queue in get_queue_list(queue):
		q = get_queue(queue)
		if (site and event):
			for job in q.jobs:
				if job.kwargs['site'] == site and job.kwargs['event'] == event:
					job.delete()
					purged_task_count+=1
		elif site:
			for job in q.jobs:
				if job.kwargs['site'] == site:
					job.delete()
					purged_task_count+=1
		elif event:
			for job in q.jobs:
				if job.kwargs['event'] == event:
					job.delete()
					purged_task_count+=1
		else:
			purged_task_count += q.count
			q.empty()


	return purged_task_count

def get_jobs_by_queue(site=None):
	jobs_per_queue = defaultdict(list)
	queue_list = get_queue_list()
	for queue in queue_list:
		q = get_queue(queue)
		for job in q.jobs:
			if not site:
				jobs_per_queue[queue].append(job.kwargs['method'])
			elif job.kwargs['site'] == site:
				jobs_per_queue[queue].append(job.kwargs['method'])
		

	return jobs_per_queue

def get_pending_task_count(site=None, queue=None):
	"Get count of pending tasks"
	pending = 0
	for queue in get_queue_list(queue):
		q = get_queue(queue)
		for job in q.jobs:
			if site is None:
				pending += 1
			else:
				if job.kwargs[site] is site:
					pending += 1
	return pending


def check_number_of_workers():
	return len(get_workers())
	
def get_running_tasks():
	for worker in get_workers():
		return worker.get_current_job()


def doctor():
	"""
	Prints diagnostic information for the scheduler
	"""
	print "Inspecting workers and queues..."
	workers_online = check_number_of_workers()
	pending_tasks = get_pending_task_count()
	print "Checking scheduler status..."
	for site in frappe.utils.get_sites():
		frappe.init(site)
		frappe.connect()
		if is_scheduler_disabled():
			print "{0:40}: Scheduler disabled via System Settings or site_config.json".format(site)
		frappe.destroy()

	print "Workers online:", workers_online
	print "Pending tasks", pending_tasks


	return True

def rq_doctor(site=None):
	queues = dump_queue_status(site=site)
	running_tasks = get_running_tasks()
	print 'Queue Status'
	print '------------'
	print queues
	print ''
	print 'Running Tasks'
	print '------------'
	print running_tasks

def inspect_queue():
	print 'Pending Tasks Queue'
	print '-'*20
	r = get_redis_conn()
	for queue in get_queues():
		for taskstr in r.lrange(queue, 0, -1):
			taskbody = get_task_body(taskstr)
			kwargs = taskbody.get('kwargs')
			if kwargs:
				print frappe.as_json(kwargs)
