from redis import Redis
from rq import Queue
import frappe
from collections import defaultdict
from frappe.utils import cstr

logger = frappe.get_logger(__name__)

def enqueue(method, queue, timeout, **kwargs):
	"""queue should be either low, high or default
	timeout should be set accoridngly"""
	q = Queue(queue, connection=Redis())
	q.enqueue(rq_task, args=(frappe.local.site, method, kwargs))

def get_jobs():
	job_dict = defaultdict(list)
	queue_list = ['low', 'default', 'high']
	for queue in queue_list:
		q = Queue(queue, connection=Redis())
		for job in q.jobs:
			job_dict[job.args[0]].append(job.args[1])
	return job_dict

def rq_task(site, method, kwargs):
	from frappe.utils.scheduler import log
	frappe.connect(site)

	if isinstance(method, basestring):
		method_name = method
		method = frappe.get_attr(method)
	else:
		method_name = cstr(method)

	try:
		method(**kwargs)
	except:
		frappe.db.rollback()
		log(method_name)
	else:
		frappe.db.commit()
	finally:
		frappe.destroy()


def new_todo(description):
	doc = frappe.get_doc({
	"doctype": "ToDo",
	"title": "My new project",
	"description": description,
	"status": "Open"
	})
	doc.insert()