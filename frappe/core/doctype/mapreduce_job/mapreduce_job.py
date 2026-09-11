# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from types import NoneType

import frappe
from frappe import qb
from frappe.model.document import Document
from frappe.query_builder.functions import Count
from frappe.utils import cint


class MapReduceJob(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		callback: DF.Data | None
		callback_executed: DF.Check
		data: DF.JSON | None
		document_name: DF.DynamicLink | None
		document_type: DF.Link | None
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

	def on_cancel(self):
		mrt = qb.DocType("MapReduce Task")
		if (
			to_cancel := qb.from_(mrt)
			.select(mrt.name)
			.where(mrt.master.eq(self.name) & mrt.status.isin(["Queued", "Paused"]))
			.for_update(skip_locked=True)
			.run(as_dict=True, pluck="name")
		):
			qb.update(mrt).set(mrt.status, "Canceled").where(mrt.name.isin(to_cancel)).run()


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

	atomically_schedule_tasks(master, 1)


def execute_callback(job: str | int):
	# Ensure job is not cancelled
	if frappe.db.get_value("MapReduce Job", job, "docstatus") == 1:
		if callback := frappe.db.get_value("MapReduce Job", filters={"name": job}, fieldname="callback"):
			callback_executed = frappe.db.get_value(
				"MapReduce Job", job, "callback_executed", for_update=True, skip_locked=True
			)
			if not isinstance(callback_executed, NoneType) and callback_executed == 0:
				result, ref_dt, ref_dn = frappe.db.get_value(
					"MapReduce Job",
					filters={"name": job},
					fieldname=["result", "document_type", "document_name"],
				)
				result = frappe.parse_json(result)

				frappe.call(callback, result, ref_dt, ref_dn) if ref_dt and ref_dn else frappe.call(
					callback, result
				)
				frappe.db.set_value("MapReduce Job", job, "callback_executed", 1)


def atomically_schedule_tasks(job, count):
	frappe.db.commit()
	mpt = qb.DocType("MapReduce Task")
	if queued := (
		qb.from_(mpt)
		.select(mpt.name)
		.where(mpt.status.eq("Queued") & mpt.master.eq(job))
		.orderby(mpt.name)
		.limit(count)
		.for_update(skip_locked=True)
		.run(as_dict=True, pluck="name")
	):
		for x in queued:
			frappe.db.set_value("MapReduce Task", x, "status", "Running")
			frappe.enqueue(
				method="frappe.core.doctype.mapreduce_job.mapreduce_job.task_execution_flow",
				enqueue_after_commit=True,
				current_task=x,
			)
	else:
		if frappe.db.get_value("MapReduce Job", job, "docstatus", for_update=True) == 1:
			total = frappe.db.count("MapReduce Task", {"master": job})
			completed = frappe.db.count("MapReduce Task", {"master": job, "status": "Completed"})
			if total == completed:
				frappe.enqueue(
					method="frappe.core.doctype.mapreduce_job.mapreduce_job.execute_callback",
					enqueue_after_commit=True,
					job=job,
				)

	frappe.db.commit()


def pause_tasks(job: str):
	mpt = qb.DocType("MapReduce Task")
	if queued := (
		qb.from_(mpt)
		.select(mpt.name)
		.where(mpt.status.eq("Queued") & mpt.master.eq(job))
		.orderby(mpt.name)
		.for_update(skip_locked=True)
		.run(as_dict=True, pluck="name")
	):
		qb.update(mpt).set("status", "Paused").where(mpt.name.isin(queued)).run()


@frappe.whitelist()
def start_execution(job: str | int):
	job = int(job) if isinstance(job, str) else job
	frappe.has_permission("MapReduce Job", ptype="write", doc=job, throw=True)

	mpt = qb.DocType("MapReduce Task")
	if paused := (
		qb.from_(mpt)
		.select(mpt.name)
		.where(mpt.status.eq("Paused") & mpt.master.eq(job))
		.orderby(mpt.name)
		.for_update(skip_locked=True)
		.run(as_dict=True, pluck="name")
	):
		qb.update(mpt).set("status", "Queued").where(mpt.name.isin(paused)).run()

	atomically_schedule_tasks(job, 4)


@frappe.whitelist()
def force_retry(job: str | int):
	job = int(job) if isinstance(job, str) else job
	frappe.has_permission("MapReduce Job", ptype="write", doc=job, throw=True)

	mpt = qb.DocType("MapReduce Task")
	if running := (
		qb.from_(mpt)
		.select(mpt.name)
		.where(mpt.status.eq("Running") & mpt.master.eq(job))
		.orderby(mpt.name)
		.for_update()
		.run(as_dict=True, pluck="name")
	):
		qb.update(mpt).set("status", "Queued").where(mpt.name.isin(running)).run()

	atomically_schedule_tasks(job, 4)


@frappe.whitelist()
def pause_execution(job: str | int):
	job = int(job) if isinstance(job, str) else job
	frappe.has_permission("MapReduce Job", ptype="write", doc=job, throw=True)
	pause_tasks(job)


@frappe.whitelist()
def get_progress(job: str | int):
	job = int(job) if isinstance(job, str) else job
	frappe.has_permission("MapReduce Job", ptype="write", doc=job, throw=True)

	tasks = frappe.db.get_all("MapReduce Task", filters={"master": job}, fields=["status"], pluck="status")
	job_status = frappe._dict()

	if "Paused" in tasks:
		job_status.status = "Paused"
	elif "Queued" in tasks:
		job_status.status = "Queued"

	# progress
	job_status.progress = (len([x for x in tasks if x == "Completed"]) / len(tasks)) * 100
	return job_status
