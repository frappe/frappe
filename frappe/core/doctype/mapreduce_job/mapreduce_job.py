# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import qb
from frappe.model.document import Document


class MapReduceJob(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		data: DF.JSON | None
		map: DF.Data | None
		name: DF.Int | None
		reduce: DF.Data | None
		result: DF.JSON | None
	# end: auto-generated types

	_DOCTYPE_NAME = "MapReduce Job"

	def before_insert(self):
		self.result = None

	def on_submit(self):
		data = frappe.parse_json(self.data)
		assert isinstance(data, list), "Data should always be a list"

		create_tasks(self.name)

	def on_trash(self):
		for doc in frappe.db.get_all("MapReduce Task", {"master": self.name}, pluck="name"):
			frappe.delete_doc("MapReduce Task", doc)


def create_tasks(job: str):
	doc = frappe.get_doc("MapReduce Job", job)
	data = frappe.parse_json(doc.data)

	for chunk in data:
		task = frappe.new_doc("MapReduce Task")
		task.master = doc.name
		task.map = doc.map
		task.reduce = doc.reduce
		task.status = "Queued"
		task.chunk = frappe.json.dumps(chunk)
		task.map_partial = None
		task.save()

	atomically_schedule_tasks(job, 4)


def task_execution_flow(current_task: str):
	# Map
	mpt = qb.DocType("MapReduce Task")
	master, mapper, reducer, chunk = (
		qb.from_(mpt)
		.select(mpt.master, mpt.map, mpt.reduce, mpt.chunk)
		.where(mpt.name.eq(current_task))
		.run()[0]
	)
	parsed_val = frappe.parse_json(chunk)

	# call map function
	partial = frappe.call(mapper, parsed_val)

	frappe.db.set_value("MapReduce Task", current_task, "map_partial", frappe.json.dumps(partial))
	frappe.db.commit()
	# transaction boundary

	# Reduce
	# take lock on master job
	res = frappe.db.get_value("MapReduce Job", master, "result", for_update=True, wait=True)
	final = frappe.parse_json(res)

	partial_res = frappe.parse_json(frappe.db.get_value("MapReduce Task", current_task, "map_partial"))

	# call reduce function
	final = frappe.call(reducer, final, partial_res)

	frappe.db.set_value("MapReduce Job", master, "result", frappe.json.dumps(final))
	frappe.db.set_value("MapReduce Task", current_task, "status", "Completed")
	frappe.db.commit()
	# transaction boundary

	# chain call
	atomically_schedule_tasks(master, 1)


def atomically_schedule_tasks(job, count):
	frappe.db.commit()
	mpt = qb.DocType("MapReduce Task")
	for x in (
		qb.from_(mpt)
		.select(mpt.name)
		.where(mpt.status.eq("Queued") & mpt.master.eq(job))
		.orderby(mpt.name)
		.limit(count)
		.for_update(skip_locked=True)
		.run(as_dict=True, pluck="name")
	):
		frappe.db.set_value("MapReduce Task", x, "status", "Running")
		frappe.enqueue(
			method="frappe.core.doctype.mapreduce_job.mapreduce_job.task_execution_flow",
			enqueue_after_commit=True,
			current_task=x,
		)
	frappe.db.commit()
