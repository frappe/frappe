# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model import no_value_fields, table_fields
from frappe.model.document import Document
from frappe.utils.background_jobs import get_jobs


class EventUpdateLog(Document):
	def after_insert(self):
		"""Send update notification updates to event consumers
		whenever update log is generated"""
		enqueued_method = (
			"frappe.event_streaming.doctype.event_consumer.event_consumer.notify_event_consumers"
		)
		jobs = get_jobs()
		if not jobs or enqueued_method not in jobs[frappe.local.site]:
			frappe.enqueue(
				enqueued_method, doctype=self.ref_doctype, queue="long", enqueue_after_commit=True
			)


def notify_consumers(doc, event):
	"""called via hooks"""
	# make event update log for doctypes having event consumers
	if frappe.flags.in_install or frappe.flags.in_migrate:
		return

	consumers = check_doctype_has_consumers(doc.doctype)
	if consumers:
		if event == "after_insert":
			doc.flags.event_update_log = make_event_update_log(doc, update_type="Create")
		elif event == "on_trash":
			make_event_update_log(doc, update_type="Delete")
		else:
			# on_update
			# called after saving
			if not doc.flags.event_update_log:  # if not already inserted
				diff = get_update(doc.get_doc_before_save(), doc)
				if diff:
					doc.diff = diff
					make_event_update_log(doc, update_type="Update")


def check_doctype_has_consumers(doctype):
	"""Check if doctype has event consumers for event streaming"""
	return frappe.cache_manager.get_doctype_map(
		"Event Consumer Document Type",
		doctype,
		dict(ref_doctype=doctype, status="Approved", unsubscribed=0),
	)


def get_update(old, new, for_child=False):
	"""
	Get document objects with updates only
	If there is a change, then returns a dict like:
	{
	        "changed"		: {fieldname1: new_value1, fieldname2: new_value2, },
	        "added"			: {table_fieldname1: [{row_dict1}, {row_dict2}], },
	        "removed"		: {table_fieldname1: [row_name1, row_name2], },
	        "row_changed"	: {table_fieldname1:
	                {
	                        child_fieldname1: new_val,
	                        child_fieldname2: new_val
	                },
	        },
	}
	"""
	if not new:
		return None

	out = frappe._dict(changed={}, added={}, removed={}, row_changed={})
	for df in new.meta.fields:
		if df.fieldtype in no_value_fields and df.fieldtype not in table_fields:
			continue

		old_value, new_value = old.get(df.fieldname), new.get(df.fieldname)

		if df.fieldtype in table_fields:
			old_row_by_name, new_row_by_name = make_maps(old_value, new_value)
			out = check_for_additions(out, df, new_value, old_row_by_name)
			out = check_for_deletions(out, df, old_value, new_row_by_name)

		elif old_value != new_value:
			out.changed[df.fieldname] = new_value

	out = check_docstatus(out, old, new, for_child)
	if any((out.changed, out.added, out.removed, out.row_changed)):
		return out
	return None


def make_event_update_log(doc, update_type):
	"""Save update info for doctypes that have event consumers"""
	if update_type != "Delete":
		# diff for update type, doc for create type
		data = frappe.as_json(doc) if not doc.get("diff") else frappe.as_json(doc.diff)
	else:
		data = None
	return frappe.get_doc(
		{
			"doctype": "Event Update Log",
			"update_type": update_type,
			"ref_doctype": doc.doctype,
			"docname": doc.name,
			"data": data,
		}
	).insert(ignore_permissions=True)


def make_maps(old_value, new_value):
	"""make maps"""
	old_row_by_name, new_row_by_name = {}, {}
	for d in old_value:
		old_row_by_name[d.name] = d
	for d in new_value:
		new_row_by_name[d.name] = d
	return old_row_by_name, new_row_by_name


def check_for_additions(out, df, new_value, old_row_by_name):
	"""check rows for additions, changes"""
	for _i, d in enumerate(new_value):
		if d.name in old_row_by_name:
			diff = get_update(old_row_by_name[d.name], d, for_child=True)
			if diff and diff.changed:
				if not out.row_changed.get(df.fieldname):
					out.row_changed[df.fieldname] = []
				diff.changed["name"] = d.name
				out.row_changed[df.fieldname].append(diff.changed)
		else:
			if not out.added.get(df.fieldname):
				out.added[df.fieldname] = []
			out.added[df.fieldname].append(d.as_dict())
	return out


def check_for_deletions(out, df, old_value, new_row_by_name):
	"""check for deletions"""
	for d in old_value:
		if d.name not in new_row_by_name:
			if not out.removed.get(df.fieldname):
				out.removed[df.fieldname] = []
			out.removed[df.fieldname].append(d.name)
	return out


def check_docstatus(out, old, new, for_child):
	"""docstatus changes"""
	if not for_child and old.docstatus != new.docstatus:
		out.changed["docstatus"] = new.docstatus
	return out


def is_consumer_uptodate(update_log, consumer):
	"""
	Checks if Consumer has read all the UpdateLogs before the specified update_log
	:param update_log: The UpdateLog Doc in context
	:param consumer: The EventConsumer doc
	"""
	if update_log.update_type == "Create":
		# consumer is obviously up to date
		return True

	prev_logs = frappe.get_all(
		"Event Update Log",
		filters={
			"ref_doctype": update_log.ref_doctype,
			"docname": update_log.docname,
			"creation": ["<", update_log.creation],
		},
		order_by="creation desc",
		limit_page_length=1,
	)

	if not len(prev_logs):
		return False

	prev_log_consumers = frappe.get_all(
		"Event Update Log Consumer",
		fields=["consumer"],
		filters={
			"parent": prev_logs[0].name,
			"parenttype": "Event Update Log",
			"consumer": consumer.name,
		},
	)

	return len(prev_log_consumers) > 0


def mark_consumer_read(update_log_name, consumer_name):
	"""
	This function appends the Consumer to the list of Consumers that has 'read' an Update Log
	"""
	update_log = frappe.get_doc("Event Update Log", update_log_name)
	if len([x for x in update_log.consumers if x.consumer == consumer_name]):
		return

	frappe.get_doc(
		frappe._dict(
			doctype="Event Update Log Consumer",
			consumer=consumer_name,
			parent=update_log_name,
			parenttype="Event Update Log",
			parentfield="consumers",
		)
	).insert(ignore_permissions=True)


def get_unread_update_logs(consumer_name, dt, dn):
	"""
	Get old logs unread by the consumer on a particular document
	"""
	already_consumed = [
		x[0]
		for x in frappe.db.sql(
			"""
		SELECT
			update_log.name
		FROM `tabEvent Update Log` update_log
		JOIN `tabEvent Update Log Consumer` consumer ON consumer.parent = %(log_name)s
		WHERE
			consumer.consumer = %(consumer)s
			AND update_log.ref_doctype = %(dt)s
			AND update_log.docname = %(dn)s
	""",
			{
				"consumer": consumer_name,
				"dt": dt,
				"dn": dn,
				"log_name": "update_log.name"
				if frappe.conf.db_type == "mariadb"
				else "CAST(update_log.name AS VARCHAR)",
			},
			as_dict=0,
		)
	]

	logs = frappe.get_all(
		"Event Update Log",
		fields=["update_type", "ref_doctype", "docname", "data", "name", "creation"],
		filters={"ref_doctype": dt, "docname": dn, "name": ["not in", already_consumed]},
		order_by="creation",
	)

	return logs


@frappe.whitelist()
def get_update_logs_for_consumer(event_consumer, doctypes, last_update):
	"""
	Fetches all the UpdateLogs for the consumer
	It will inject old un-consumed Update Logs if a doc was just found to be accessible to the Consumer
	"""

	if isinstance(doctypes, str):
		doctypes = frappe.parse_json(doctypes)

	from frappe.event_streaming.doctype.event_consumer.event_consumer import has_consumer_access

	consumer = frappe.get_doc("Event Consumer", event_consumer)
	docs = frappe.get_list(
		doctype="Event Update Log",
		filters={"ref_doctype": ("in", doctypes), "creation": (">", last_update)},
		fields=["update_type", "ref_doctype", "docname", "data", "name", "creation"],
		order_by="creation desc",
	)

	result = []
	to_update_history = []
	for d in docs:
		if (d.ref_doctype, d.docname) in to_update_history:
			# will be notified by background jobs
			continue

		if not has_consumer_access(consumer=consumer, update_log=d):
			continue

		if not is_consumer_uptodate(d, consumer):
			to_update_history.append((d.ref_doctype, d.docname))
			# get_unread_update_logs will have the current log
			old_logs = get_unread_update_logs(consumer.name, d.ref_doctype, d.docname)
			if old_logs:
				old_logs.reverse()
				result.extend(old_logs)
		else:
			result.append(d)

	for d in result:
		mark_consumer_read(update_log_name=d.name, consumer_name=consumer.name)

	result.reverse()
	return result
