# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import hashlib
import itertools
from collections import defaultdict, deque

import frappe
import frappe.desk.form.load
import frappe.desk.form.meta
from frappe import _
from frappe.model.delete_doc import LinkedDocumentsOverflow, get_dynamic_linked_docs
from frappe.model.delete_doc import get_linked_docs as get_statically_linked_docs
from frappe.model.meta import is_single
from frappe.modules import load_doctype_module
from frappe.utils.scheduler import is_scheduler_inactive


@frappe.whitelist()
def get_submitted_linked_docs(
	doctype: str, name: str, ignore_doctypes_on_cancel_all: str | list[str] | None = None
) -> list[tuple]:
	"""Get all the nested submitted documents those are present in referencing tables (dependent tables).

	:param doctype: Document type
	:param name: Name of the document

	Use-case:
	* User should be able to cancel the linked documents along with the one user trying to cancel.

	Case1: If document sd1-n1 (document name n1 from submittable doctype sd1) is linked to sd2-n2 and sd2-n2 is linked to sd3-n3,
	        Getting submittable linked docs of `sd1-n1`should give both sd2-n2 and sd3-n3.
	Case2: If document sd1-n1 (document name n1 from submittable doctype sd1) is linked to d2-n2 and d2-n2 is linked to sd3-n3,
	        Getting submittable linked docs of `sd1-n1`should give None. (because d2-n2 is not a submittable doctype)
	Case3: If document sd1-n1 (document name n1 from submittable doctype sd1) is linked to d2-n2 & sd2-n2. d2-n2 is linked to sd3-n3.
	        Getting submittable linked docs of `sd1-n1`should give sd2-n2.

	Logic:
	-----
	1. We can find linked documents only if we know how the doctypes are related.
	2. As we need only submittable documents, we can limit doctype relations search to submittable doctypes by
	        finding the relationships(Foreign key references) across submittable doctypes.
	3. Searching for links is going to be a tree like structure where at every level,
	        you will be finding documents using parent document and parent document links.

	Past MAX_LINKED_DOCUMENTS_LISTED the result is empty and marked truncated.
	"""

	frappe.has_permission(doctype, doc=name, throw=True)
	docs, truncated = collect_cancellation_blockers(
		doctype, name, ignore_doctypes_on_cancel_all, limit=MAX_LINKED_DOCUMENTS_LISTED
	)
	return {"docs": docs, "count": len(docs), "truncated": truncated}


def collect_cancellation_blockers(
	doctype: str, name: str, ignore_doctypes_on_cancel_all=None, limit: int | None = None
) -> tuple[list, bool]:
	"""Walk the submitted linked documents, deepest documents first in the
	result; past `limit` discovered documents, give up and report truncated."""
	ignore_doctypes_on_cancel_all = frappe.parse_json(ignore_doctypes_on_cancel_all) or []

	tree = SubmittableDocumentTree(doctype, name)
	visited_documents = tree.get_all_children(ignore_doctypes_on_cancel_all, limit=limit)
	if tree.truncated:
		return [], True

	docs = []
	for dt, names in visited_documents.items():
		docs.extend([{"doctype": dt, "name": docname, "docstatus": 1} for docname in names])

	# deepest first, so referencing documents get cancelled before the referenced
	docs.sort(key=lambda doc: tree.depth_by_document[doc["doctype"], doc["name"]], reverse=True)
	return docs, False


class SubmittableDocumentTree:
	def __init__(self, doctype: str, name: str):
		"""Construct a tree for the submitable linked documents.

		* Node has properties like doctype and docnames. Represented as Node(doctype, docnames).
		* Nodes are linked by doctype relationships like table, link and dynamic links.
		* Node is referenced(linked) by many other documents and those are the child nodes.

		NOTE: child document is a property of child node (not same as Frappe child docs of a table field).
		"""
		self.root_doctype = doctype
		self.root_docname = name

		# Documents those are yet to be visited for linked documents.
		self.to_be_visited_documents = {doctype: [name]}
		self.visited_documents = defaultdict(list)
		self.depth_by_document = {(doctype, name): 0}
		self.truncated = False
		self.fetch_limit = None

		self._submittable_doctypes = None  # All submittable doctypes in the system
		self._references_across_doctypes = None  # doctype wise links/references

	def get_all_children(self, ignore_doctypes_on_cancel_all, limit=None):
		"""Get all nodes of a tree except the root node (all the nested submitted
		documents those are present in referencing tables dependent tables); past
		`limit` documents, mark the tree truncated and return nothing."""
		self.fetch_limit = limit + 1 if limit else None
		depth = 0
		while self.to_be_visited_documents:
			depth += 1
			current_level = self.visit_current_level(ignore_doctypes_on_cancel_all)
			next_level_children = defaultdict(list)
			for parent_dt, parent_docs in current_level.items():
				try:
					child_docs = self.get_next_level_children(parent_dt, parent_docs)
				except LinkedDocumentsOverflow:
					self.truncated = True
					return defaultdict(list)
				for linked_dt, linked_names in child_docs.items():
					new_child_docs = (
						set(linked_names)
						- set(self.visited_documents.get(linked_dt, []))
						- set(next_level_children[linked_dt])
					)
					next_level_children[linked_dt].extend(new_child_docs)
					for linked_name in new_child_docs:
						self.depth_by_document[(linked_dt, linked_name)] = depth

			self.to_be_visited_documents = next_level_children
			if limit and len(self.depth_by_document) - 1 > limit:
				self.truncated = True
				return defaultdict(list)

		# Remove root node from visited documents
		if self.root_docname in self.visited_documents.get(self.root_doctype, []):
			self.visited_documents[self.root_doctype].remove(self.root_docname)

		assert self.root_docname not in self.visited_documents.get(self.root_doctype, []), (
			"root document must be excluded from linked children"
		)
		return self.visited_documents

	def visit_current_level(self, ignore_doctypes_on_cancel_all):
		"""Mark all documents of the current level as visited before expanding them,
		so a document referenced from its own level is not visited twice."""
		current_level = {}
		for parent_dt, parent_docs in self.to_be_visited_documents.items():
			if not parent_docs or (
				ignore_doctypes_on_cancel_all and parent_dt in ignore_doctypes_on_cancel_all
			):
				continue
			current_level[parent_dt] = parent_docs
			self.visited_documents[parent_dt].extend(parent_docs)
		return current_level

	def get_next_level_children(self, parent_dt, parent_names):
		"""Get immediate children of a Node(parent_dt, parent_names)"""
		referencing_fields = self.get_doctype_references(parent_dt)

		child_docs = defaultdict(list)
		for field in referencing_fields:
			if field["fieldname"] == "amended_from":
				# perf: amended_from links are always linked to cancelled documents.
				continue

			links = (
				get_referencing_documents(
					parent_dt,
					parent_names.copy(),
					field,
					get_parent_if_child_table_doc=True,
					parent_filters=[("docstatus", "=", 1)],
					allowed_parents=self.get_link_sources(),
					limit=self.fetch_limit,
				)
				or {}
			)
			for dt, names in links.items():
				child_docs[dt].extend(names)
		return child_docs

	def get_doctype_references(self, doctype):
		"""Get references for a given document."""
		if self._references_across_doctypes is None:
			get_links_to = self.get_document_sources()
			limit_link_doctypes = self.get_link_sources()
			self._references_across_doctypes = get_references_across_doctypes(
				get_links_to, limit_link_doctypes
			)
		return self._references_across_doctypes.get(doctype, [])

	def get_document_sources(self):
		"""Return list of doctypes from where we access submittable documents."""
		return list(set([*self.get_link_sources(), self.root_doctype]))

	def get_link_sources(self):
		"""limit doctype links to these doctypes."""
		return list(set(self.get_submittable_doctypes()) - set(get_exempted_doctypes() or []))

	def get_submittable_doctypes(self) -> list[str]:
		"""Return list of submittable doctypes."""
		if not self._submittable_doctypes:
			self._submittable_doctypes = frappe.get_all(
				"DocType", {"is_submittable": 1}, pluck="name", order_by=None
			)
		return self._submittable_doctypes


def get_child_tables_of_doctypes(doctypes: list[str] | None = None):
	"""Return child tables by doctype."""
	filters = [["fieldtype", "=", "Table"]]
	filters_for_docfield = filters
	filters_for_customfield = filters

	if doctypes:
		filters_for_docfield = [*filters, ["parent", "in", tuple(doctypes)]]
		filters_for_customfield = [*filters, ["dt", "in", tuple(doctypes)]]

	links = frappe.get_all(
		"DocField",
		fields=["parent", "fieldname", "options as child_table"],
		filters=filters_for_docfield,
		as_list=1,
		order_by=None,
	)

	links += frappe.get_all(
		"Custom Field",
		fields=["dt as parent", "fieldname", "options as child_table"],
		filters=filters_for_customfield,
		as_list=1,
		order_by=None,
	)

	child_tables_by_doctype = defaultdict(list)
	for doctype, fieldname, child_table in links:
		child_tables_by_doctype[doctype].append(
			{"doctype": doctype, "fieldname": fieldname, "child_table": child_table}
		)
	return child_tables_by_doctype


def get_references_across_doctypes(
	to_doctypes: list[str] | None = None, limit_link_doctypes: list[str] | None = None
) -> list:
	"""Find doctype wise foreign key references.

	:param to_doctypes: Get links of these doctypes.
	:param limit_link_doctypes: limit links to these doctypes.

	* Include child table, link and dynamic link references.
	"""
	if limit_link_doctypes:
		child_tables_by_doctype = get_child_tables_of_doctypes(limit_link_doctypes)
		all_child_tables = [
			each["child_table"] for each in itertools.chain(*child_tables_by_doctype.values())
		]
		limit_link_doctypes = limit_link_doctypes + all_child_tables
	else:
		child_tables_by_doctype = get_child_tables_of_doctypes()
		all_child_tables = [
			each["child_table"] for each in itertools.chain(*child_tables_by_doctype.values())
		]

	references_by_link_fields = get_references_across_doctypes_by_link_field(to_doctypes, limit_link_doctypes)
	references_by_dlink_fields = get_references_across_doctypes_by_dynamic_link_field(
		to_doctypes, limit_link_doctypes
	)

	references = references_by_link_fields.copy()
	for k, v in references_by_dlink_fields.items():
		references.setdefault(k, []).extend(v)

	for links in references.values():
		for link in links:
			link["is_child"] = link["doctype"] in all_child_tables
	return references


def get_references_across_doctypes_by_link_field(
	to_doctypes: list[str] | None = None, limit_link_doctypes: list[str] | None = None
):
	"""Find doctype wise foreign key references based on link fields.

	:param to_doctypes: Get links to these doctypes.
	:param limit_link_doctypes: limit links to these doctypes.
	"""
	filters = [["fieldtype", "=", "Link"]]

	if to_doctypes:
		filters += [["options", "in", tuple(to_doctypes)]]

	filters_for_docfield = filters[:]
	filters_for_customfield = filters[:]

	if limit_link_doctypes:
		filters_for_docfield += [["parent", "in", tuple(limit_link_doctypes)]]
		filters_for_customfield += [["dt", "in", tuple(limit_link_doctypes)]]

	links = frappe.get_all(
		"DocField",
		fields=["parent", "fieldname", "options as linked_to"],
		filters=filters_for_docfield,
		as_list=1,
	)

	links += frappe.get_all(
		"Custom Field",
		fields=["dt as parent", "fieldname", "options as linked_to"],
		filters=filters_for_customfield,
		as_list=1,
	)

	links_by_doctype = defaultdict(list)
	for doctype, fieldname, linked_to in links:
		links_by_doctype[linked_to].append({"doctype": doctype, "fieldname": fieldname})
	return links_by_doctype


def get_references_across_doctypes_by_dynamic_link_field(
	to_doctypes: list[str] | None = None, limit_link_doctypes: list[str] | None = None
):
	"""Find doctype wise foreign key references based on dynamic link fields.

	:param to_doctypes: Get links to these doctypes.
	:param limit_link_doctypes: limit links to these doctypes.
	"""

	filters = [["fieldtype", "=", "Dynamic Link"]]

	filters_for_docfield = filters[:]
	filters_for_customfield = filters[:]

	if limit_link_doctypes:
		filters_for_docfield += [["parent", "in", tuple(limit_link_doctypes)]]
		filters_for_customfield += [["dt", "in", tuple(limit_link_doctypes)]]

	# find dynamic links of parents
	links = frappe.get_all(
		"DocField",
		fields=["parent as doctype", "fieldname", "options as doctype_fieldname"],
		filters=filters_for_docfield,
		as_list=1,
		order_by=None,
	)

	links += frappe.get_all(
		"Custom Field",
		fields=["dt as doctype", "fieldname", "options as doctype_fieldname"],
		filters=filters_for_customfield,
		as_list=1,
		order_by=None,
	)

	links_by_doctype = defaultdict(list)
	for doctype, fieldname, doctype_fieldname in links:
		try:
			filters = [[doctype_fieldname, "in", to_doctypes]] if to_doctypes else []
			for linked_to in frappe.get_all(
				doctype,
				pluck=doctype_fieldname,
				filters=filters,
				distinct=1,
			):
				if linked_to:
					links_by_doctype[linked_to].append(
						{"doctype": doctype, "fieldname": fieldname, "doctype_fieldname": doctype_fieldname}
					)
		except frappe.db.ProgrammingError:
			# TODO: FIXME
			continue
	return links_by_doctype


def get_referencing_documents(
	reference_doctype: str,
	reference_names: list[str],
	link_info: dict,
	get_parent_if_child_table_doc: bool = True,
	parent_filters: list[list] | None = None,
	child_filters=None,
	allowed_parents=None,
	limit: int | None = None,
):
	"""Get linked documents based on link_info.

	:param reference_doctype: reference doctype to find links
	:param reference_names: reference document names to find links for
	:param link_info: linking details to get the linked documents
	        Ex: {'doctype': 'Purchase Invoice Advance', 'fieldname': 'reference_name',
	                'doctype_fieldname': 'reference_type', 'is_child': True}
	:param get_parent_if_child_table_doc: Get parent record incase linked document is a child table record.
	:param parent_filters: filters to apply on if not a child table.
	:param child_filters: apply filters if it is a child table.
	:param allowed_parents: list of parents allowed in case of get_parent_if_child_table_doc
	        is enabled.
	"""
	from_table = link_info["doctype"]
	filters = [[link_info["fieldname"], "in", tuple(reference_names)]]
	if link_info.get("doctype_fieldname"):
		filters.append([link_info["doctype_fieldname"], "=", reference_doctype])

	if not link_info.get("is_child"):
		filters.extend(parent_filters or [])
		names = frappe.get_all(from_table, filters, pluck="name", order_by=None, limit=limit)
		if limit and len(names) >= limit:
			raise LinkedDocumentsOverflow
		return {from_table: names}

	filters.extend(child_filters or [])
	res = frappe.get_all(
		from_table, filters=filters, fields=["name", "parenttype", "parent"], order_by=None, limit=limit
	)
	if limit and len(res) >= limit:
		raise LinkedDocumentsOverflow
	documents = defaultdict(list)

	for parent, rows in itertools.groupby(res, key=lambda row: row["parenttype"]):
		if allowed_parents and parent not in allowed_parents:
			continue
		filters = (parent_filters or []) + [["name", "in", tuple(row.parent for row in rows)]]
		documents[parent].extend(frappe.get_all(parent, filters=filters, pluck="name", order_by=None) or [])
	return documents


MAX_SYNCHRONOUS_LINKED_DOCS = 50


@frappe.whitelist()
def cancel_all_linked_docs(
	docs: str | list | None = None,
	ignore_doctypes_on_cancel_all: str | list[str] | None = None,
	root_doctype: str | None = None,
	root_name: str | None = None,
):
	"""Cancel the linked documents in dependency order, then the root, all or
	nothing; large sets, roots that queue their cancellations, and docs=None
	past the listing cap move to a job instead."""
	ignore_doctypes_on_cancel_all = frappe.parse_json(ignore_doctypes_on_cancel_all) or []
	if docs is None:
		return enqueue_discovery("cancel", root_doctype, root_name, ignore_doctypes_on_cancel_all)

	docs = deduplicated(frappe.parse_json(docs))
	to_cancel = [doc for doc in docs if validate_linked_doc(doc, ignore_doctypes_on_cancel_all)]
	if len(to_cancel) > MAX_SYNCHRONOUS_LINKED_DOCS or is_cancelled_in_background(root_doctype):
		return enqueue_linked_docs_processing(
			to_cancel, "cancel", root_doctype, root_name, ignore_doctypes_on_cancel_all
		)

	if root_doctype and root_name:
		try:
			to_cancel = keep_currently_linked(
				to_cancel,
				"cancel",
				root_doctype,
				root_name,
				ignore_doctypes_on_cancel_all,
				limit=MAX_LINKED_DOCUMENTS_LISTED,
			)
		except LinkedDocumentsOverflow:
			return enqueue_discovery("cancel", root_doctype, root_name, ignore_doctypes_on_cancel_all)
		# the root goes last, in the same transaction as its links
		to_cancel = [*to_cancel, frappe._dict(doctype=root_doctype, name=root_name)]
	process_linked_docs_in_dependency_order(to_cancel, cancel_linked_doc, _("Cancelling documents"))


def cancel_linked_doc(docinfo):
	"""Cancel a document unless the on_cancel hook of another document already cancelled it."""
	doc = frappe.get_doc(docinfo.get("doctype"), docinfo.get("name"))
	if doc.docstatus.is_submitted():
		doc.cancel()


def is_cancelled_in_background(doctype):
	"""Whether the doctype queues its cancellations, as the form's own Cancel honours."""
	return bool(doctype and frappe.get_meta(doctype).queue_in_background and not is_scheduler_inactive())


MAX_LINKED_DOCUMENTS_LISTED = 500


@frappe.whitelist()
def get_linked_docs_to_delete(doctype: str, name: str) -> dict:
	"""Get the documents blocking deletion of the given document, recursively,
	deepest first; unreadable ones are neither returned nor traversed. Past
	MAX_LINKED_DOCUMENTS_LISTED the result is empty and marked truncated."""
	frappe.has_permission(doctype, doc=name, throw=True)
	docs, truncated = collect_deletion_blockers(doctype, name, limit=MAX_LINKED_DOCUMENTS_LISTED)
	return {"docs": docs, "count": len(docs), "truncated": truncated}


def collect_deletion_blockers(doctype: str, name: str, limit: int | None = None) -> tuple[list, bool]:
	"""Walk the delete-blocking graph breadth first, deepest documents first in
	the result; past `limit` discovered documents, give up and report truncated."""
	root_key = (doctype, name)
	depth_by_document = {root_key: 0}
	queue = deque([root_key])
	fetch_limit = limit + 1 if limit else None
	while queue:
		parent_key = queue.popleft()
		# lightweight stand-in; a full get_doc per node is too expensive
		parent = frappe._dict(doctype=parent_key[0], name=parent_key[1])
		try:
			links = get_statically_linked_docs(parent, method="Delete", limit=fetch_limit)
			dynamic_links = get_dynamic_linked_docs(parent, method="Delete", limit=fetch_limit)
		except LinkedDocumentsOverflow:
			return [], True
		for link in [*links, *dynamic_links]:
			key = (link["reference_doctype"], link["reference_docname"])
			if key in depth_by_document:
				continue
			if limit and len(depth_by_document) > limit:
				return [], True
			if not frappe.has_permission(key[0], doc=key[1]):
				continue
			depth_by_document[key] = depth_by_document[parent_key] + 1
			queue.append(key)

	docs = [
		{"doctype": dt, "name": docname} for dt, docname in depth_by_document if (dt, docname) != root_key
	]
	docs.sort(key=lambda doc: depth_by_document[doc["doctype"], doc["name"]], reverse=True)
	return docs, False


@frappe.whitelist()
def delete_all_linked_docs(
	docs: str | list | None = None, root_doctype: str | None = None, root_name: str | None = None
) -> dict | None:
	"""Delete the linked documents in dependency order, then the root, all or
	nothing; sets larger than MAX_SYNCHRONOUS_LINKED_DOCS, or docs=None past
	the listing cap, move to a job instead."""
	if docs is None:
		return enqueue_discovery("delete", root_doctype, root_name)

	to_delete = deduplicated(frappe.parse_json(docs))
	if len(to_delete) > MAX_SYNCHRONOUS_LINKED_DOCS:
		return enqueue_linked_docs_processing(to_delete, "delete", root_doctype, root_name)

	if root_doctype and root_name:
		try:
			to_delete = keep_currently_linked(
				to_delete, "delete", root_doctype, root_name, limit=MAX_LINKED_DOCUMENTS_LISTED
			)
		except LinkedDocumentsOverflow:
			return enqueue_discovery("delete", root_doctype, root_name)
		# the root goes last: its on_trash may remove blockers nothing else can
		to_delete = [*to_delete, frappe._dict(doctype=root_doctype, name=root_name)]

	# no realtime progress: late events strand the dialog; the freeze overlay suffices
	process_linked_docs_in_dependency_order(to_delete, delete_linked_doc)


def keep_currently_linked(
	docs, action, root_doctype, root_name, ignore_doctypes_on_cancel_all=None, limit=None
):
	"""Drop entries no longer linked to the root: the list was built in an earlier
	request and may be stale; raise LinkedDocumentsOverflow past `limit`."""
	if action == "cancel":
		current_docs, truncated = collect_cancellation_blockers(
			root_doctype, root_name, ignore_doctypes_on_cancel_all, limit=limit
		)
	else:
		current_docs, truncated = collect_deletion_blockers(root_doctype, root_name, limit=limit)
	if truncated:
		raise LinkedDocumentsOverflow

	current = {(doc["doctype"], doc["name"]) for doc in current_docs}
	return [doc for doc in docs if (doc.get("doctype"), doc.get("name")) in current]


def delete_linked_doc(docinfo):
	"""Delete a document; one already removed by another document's on_trash hook is ignored."""
	frappe.delete_doc(docinfo.get("doctype"), docinfo.get("name"))


def enqueue_discovery(action, root_doctype, root_name, ignore_doctypes_on_cancel_all=None):
	"""Queue a job that discovers the root's graph itself, uncapped, and processes it."""
	if not (root_doctype and root_name):
		frappe.throw(_("Either the documents to process or a root document is required"))
	frappe.has_permission(root_doctype, doc=root_name, throw=True)
	return enqueue_linked_docs_processing(
		[], action, root_doctype, root_name, ignore_doctypes_on_cancel_all, discover=True
	)


def enqueue_linked_docs_processing(
	docs, action, root_doctype, root_name, ignore_doctypes_on_cancel_all=None, discover=False
):
	"""Queue processing of a large set; the job handles the root too."""
	root = (root_doctype, root_name) if root_doctype and root_name else None
	job_kwargs = {}
	if root:
		# hash the identity: doctype and name may contain any separator
		digest = hashlib.sha256(str((action, root_doctype, root_name)).encode()).hexdigest()[:16]
		job_kwargs = {"job_id": f"linked_docs_{digest}", "deduplicate": True}

	frappe.enqueue(
		process_linked_docs_in_background,
		docs=docs,
		action=action,
		root=root,
		discover=discover,
		ignore_doctypes_on_cancel_all=ignore_doctypes_on_cancel_all,
		queue="long",
		now=frappe.in_test,
		**job_kwargs,
	)
	return {"queued": True}


def process_linked_docs_in_background(
	docs, action, root=None, discover=False, ignore_doctypes_on_cancel_all=None
):
	"""Process the docs, root last, all or nothing, and notify the user; the
	queued list is refreshed, or discovered uncapped, before processing."""
	if not frappe.db.get_value("User", frappe.session.user, "enabled"):
		# the initiating account was disabled after this job was queued
		return

	if root:
		if discover and action == "cancel":
			docs, _truncated = collect_cancellation_blockers(*root, ignore_doctypes_on_cancel_all)
		elif discover:
			docs, _truncated = collect_deletion_blockers(*root)
		else:
			docs = keep_currently_linked(docs, action, *root, ignore_doctypes_on_cancel_all)
		docs = [*docs, frappe._dict(doctype=root[0], name=root[1])]

	process = cancel_linked_doc if action == "cancel" else delete_linked_doc
	side_effect_counts = capture_pending_side_effects()
	frappe.db.savepoint("linked_docs_job")
	error = None
	try:
		process_linked_docs_in_dependency_order(docs, process)
	except DEFERRABLE_ERRORS as blocker:
		frappe.db.rollback(save_point="linked_docs_job")
		discard_side_effects_since(side_effect_counts)
		error = blocker
	except frappe.QueryDeadlockError as deadlock:
		# the database has already discarded the whole transaction, savepoint included
		frappe.db.rollback()
		error = deadlock
	notify_linked_docs_processed(linked_docs_job_message(action, len(docs), error))


def linked_docs_job_message(action, count, error=None):
	"""The notification text for a finished or failed job."""
	messages = {
		"cancel": (_("Cancelled {0} linked documents."), _("Could not cancel {0} linked documents: {1}")),
		"delete": (_("Deleted {0} linked documents."), _("Could not delete {0} linked documents: {1}")),
	}
	done, failed = messages[action]
	return failed.format(count, error) if error else done.format(count)


def notify_linked_docs_processed(message):
	"""Notify live and via Notification Log, both after commit."""
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	frappe.publish_realtime(
		"msgprint", {"message": message, "alert": True}, user=frappe.session.user, after_commit=True
	)
	enqueue_create_notification([frappe.session.user], {"type": "Alert", "subject": message})


def deduplicated(docs):
	"""Preserve order, dropping repeated (doctype, name) entries."""
	seen = set()
	unique = []
	for doc in docs:
		key = (doc.get("doctype"), doc.get("name"))
		if key not in seen:
			seen.add(key)
			unique.append(doc)
	return unique


# a document blocked by another one, or by a lock, may go through on a later pass;
# not a deadlocked one: the database has already rolled the whole transaction back
DEFERRABLE_ERRORS = (frappe.ValidationError, frappe.PermissionError, frappe.QueryTimeoutError)


def process_linked_docs_in_dependency_order(docs, process, progress_title=None):
	"""Run process over docs, deferring blocked ones to later passes until a
	pass makes no progress, then raise the first blocker's error."""
	total = len(docs)
	processed = 0
	save_point = "process_linked_doc"

	def mark_processed():
		nonlocal processed
		processed += 1
		if progress_title:
			frappe.publish_progress(percent=processed / total * 100, title=progress_title)

	while docs:
		deferred = []
		for doc in docs:
			side_effect_counts = capture_pending_side_effects()
			frappe.db.savepoint(save_point)
			try:
				process(doc)
			except DEFERRABLE_ERRORS:
				# hooks ran before the failing check; undo their writes and side effects
				frappe.db.rollback(save_point=save_point)
				discard_side_effects_since(side_effect_counts)
				deferred.append(doc)
				continue
			frappe.db.release_savepoint(save_point)
			mark_processed()

		if len(deferred) == len(docs):
			# surface the blocker's error; a success means the block was transient
			process(deferred[0])
			mark_processed()
			deferred = deferred[1:]
		docs = deferred


def capture_pending_side_effects() -> dict:
	"""Snapshot the side-effect queues that savepoints cannot restore."""
	return {
		"message_log": list(frappe.local.message_log),
		"currently_saving": list(frappe.flags.currently_saving or []),
		"before_commit": len(frappe.db.before_commit),
		"after_commit": len(frappe.db.after_commit),
		"before_rollback": len(frappe.db.before_rollback),
		"after_rollback": len(frappe.db.after_rollback),
		"realtime_log": len(frappe.local._realtime_log) if hasattr(frappe.local, "_realtime_log") else None,
		"webhook_queue": len(getattr(frappe.local, "_webhook_queue", None) or []),
	}


def discard_side_effects_since(counts: dict):
	"""Drop what a rolled-back attempt queued; its rollback watchers are run,
	not dropped, since they compensate effects the savepoint cannot undo."""
	frappe.local.message_log = counts["message_log"]
	frappe.flags.currently_saving = counts["currently_saving"]
	frappe.db.before_commit.truncate(counts["before_commit"])
	frappe.db.after_commit.truncate(counts["after_commit"])

	for callback in [
		*frappe.db.before_rollback.cut(counts["before_rollback"]),
		*frappe.db.after_rollback.cut(counts["after_rollback"]),
	]:
		callback()

	if counts["realtime_log"] is None:
		if hasattr(frappe.local, "_realtime_log"):
			# its flush hook was truncated above; drop the log so it re-registers
			del frappe.local._realtime_log
	elif hasattr(frappe.local, "_realtime_log"):
		frappe.local._realtime_log = frappe.local._realtime_log[: counts["realtime_log"]]

	if getattr(frappe.local, "_webhook_queue", None):
		frappe.local._webhook_queue = frappe.local._webhook_queue[: counts["webhook_queue"]]


def validate_linked_doc(docinfo, ignore_doctypes_on_cancel_all=None):
	"""
	Validate a document to be submitted and non-exempted from auto-cancel.

	Arguments:
	        docinfo (dict): The document to check for submitted and non-exempt from auto-cancel
	        ignore_doctypes_on_cancel_all (list) - List of doctypes to ignore while cancelling.

	Return:
	        bool: True if linked document passes all validations, else False
	"""
	# ignore doctype to cancel
	if docinfo.get("doctype") in (ignore_doctypes_on_cancel_all or []):
		return False

	# skip non-submittable doctypes since they don't need to be cancelled
	if not frappe.get_meta(docinfo.get("doctype")).is_submittable:
		return False

	# skip draft or cancelled documents
	if docinfo.get("docstatus") != 1:
		return False

	# skip other doctypes since they don't need to be cancelled
	auto_cancel_exempt_doctypes = get_exempted_doctypes()
	if docinfo.get("doctype") in auto_cancel_exempt_doctypes:
		return False

	return True


def get_exempted_doctypes():
	"""Get list of doctypes exempted from being auto-cancelled"""
	return list(frappe.get_hooks("auto_cancel_exempted_doctypes"))


def get_linked_docs(doctype: str, name: str, linkinfo: dict | None = None) -> dict[str, list]:
	# additional fields are added in linkinfo
	linkinfo = frappe.parse_json(linkinfo)

	results = {}

	if not linkinfo:
		return results

	is_target_doctype_table = frappe.get_meta(doctype).istable

	for linked_doctype, link_context in linkinfo.items():
		linked_doctype_meta = frappe.get_meta(linked_doctype)

		if linked_doctype_meta.issingle:
			continue

		has_permission = frappe.has_permission(linked_doctype)
		filters = []
		or_filters = []
		ret = None
		parent_info = None

		if filters_ctx := link_context.get("filters"):
			filters = filters_ctx

		elif link_context.get("get_parent"):
			# check for child table
			if not is_target_doctype_table:
				continue

			parent_info = parent_info or frappe.db.get_value(
				doctype, name, ["parenttype", "parent"], as_dict=True, order_by=None
			)

			if not (parent_info and parent_info.parenttype == linked_doctype):
				continue

			filters = [[linked_doctype, "name", "=", parent_info.parent]]

		elif child_doctype := link_context.get("child_doctype"):
			# doctype may link through more than one child table, each with its own Link field
			child_links = link_context.get("child_links") or [
				{"child_doctype": child_doctype, "fieldname": link_context["fieldname"]}
			]
			or_filters = [
				[child_link["child_doctype"], fieldname, "=", name]
				for child_link in child_links
				for fieldname in child_link["fieldname"]
			]

			# dynamic link_context
			if doctype_fieldname := link_context.get("doctype_fieldname"):
				filters.append([child_doctype, doctype_fieldname, "=", doctype])

		elif link_fieldnames := link_context.get("fieldname"):
			if isinstance(link_fieldnames, str):
				link_fieldnames = [link_fieldnames]
			or_filters = [[linked_doctype, fieldname, "=", name] for fieldname in link_fieldnames]
			# dynamic link_context
			if doctype_fieldname := link_context.get("doctype_fieldname"):
				filters.append([linked_doctype, doctype_fieldname, "=", doctype])
			# check for child table that no one links to
			if linked_doctype_meta.istable:
				if not (
					frappe.db.exists("DocField", {"options": linked_doctype})
					or frappe.db.exists(linked_doctype, {"parenttype": doctype, "parent": name})
				):
					continue

		total_count = len(
			frappe.get_all(
				linked_doctype,
				filters=filters,
				or_filters=or_filters,
				fields=["name"],
				order_by=None,
			)
		)

		if not total_count:
			continue

		if has_permission:
			fields = [
				d.fieldname
				for d in linked_doctype_meta.get(
					"fields",
					{
						"in_list_view": 1,
						"fieldtype": ["not in", ("Image", "HTML", "Button", *frappe.model.table_fields)],
					},
				)
			] + ["name", "modified", "docstatus"]

			if add_fields := link_context.get("add_fields"):
				fields += add_fields

			fields = [sf.strip() for sf in fields if sf]

			ret = frappe.get_list(
				doctype=linked_doctype,
				fields=fields,
				filters=filters,
				or_filters=or_filters,
				distinct=True,
				order_by=None,
			)

		permitted_count = len(ret or [])
		assert permitted_count <= total_count, "permitted linked docs cannot exceed total linked docs"
		results[linked_doctype] = {
			"docs": ret or [],
			"hidden_count": total_count - permitted_count,
		}

	return results


@frappe.whitelist()
def get(doctype: str, docname: str):
	frappe.has_permission(doctype, doc=docname, throw=True)
	linked_doctypes = get_linked_doctypes(doctype=doctype)
	return get_linked_docs(doctype=doctype, name=docname, linkinfo=linked_doctypes)


@frappe.whitelist()
def get_linked_doctypes(doctype: str, without_ignore_user_permissions_enabled: int | bool = False):
	"""add list of doctypes this doctype is 'linked' with.

	Example, for Customer:

	        {"Address": {"fieldname": "customer"}..}
	"""
	if without_ignore_user_permissions_enabled:
		return frappe.cache.hget(
			"linked_doctypes_without_ignore_user_permissions_enabled",
			doctype,
			lambda: _get_linked_doctypes(doctype, without_ignore_user_permissions_enabled),
		)
	else:
		return frappe.cache.hget("linked_doctypes", doctype, lambda: _get_linked_doctypes(doctype))


def _get_linked_doctypes(doctype, without_ignore_user_permissions_enabled=False):
	ret = {}
	# find fields where this doctype is linked
	ret.update(get_linked_fields(doctype, without_ignore_user_permissions_enabled))
	ret.update(get_dynamic_linked_fields(doctype, without_ignore_user_permissions_enabled))

	filters = [["fieldtype", "in", frappe.model.table_fields], ["options", "=", doctype]]
	if without_ignore_user_permissions_enabled:
		filters.append(["ignore_user_permissions", "!=", 1])
	# find links of parents
	links = frappe.get_all("DocField", fields=["parent as dt"], filters=filters)
	links += frappe.get_all("Custom Field", fields=["dt"], filters=filters)

	for (dt,) in links:
		if dt in ret:
			continue
		ret[dt] = {"get_parent": True}

	custom_doctypes = frappe.get_all(
		doctype="DocType", filters=[["custom", "=", 1], ["name", "in", list(ret.keys())]], as_list=True
	)

	custom_doctypes = [item[0] for item in custom_doctypes]

	for dt in list(ret):
		# if the custom checkbox is checked, then don't load the module of the DocType because it doesn't belong to any app.
		if dt in custom_doctypes:
			continue
		try:
			doctype_module = load_doctype_module(dt)
		except (ImportError, KeyError):
			# in case of Custom DocType
			# or in case of module rename eg. (Schools -> Education)
			continue

		if getattr(doctype_module, "exclude_from_linked_with", False):
			del ret[dt]

	return ret


def get_linked_fields(doctype, without_ignore_user_permissions_enabled=False):
	filters = [["fieldtype", "=", "Link"], ["options", "=", doctype]]
	if without_ignore_user_permissions_enabled:
		filters.append(["ignore_user_permissions", "!=", 1])

	# find links of parents
	links = frappe.get_all("DocField", fields=["parent", "fieldname"], filters=filters, as_list=1)
	links += frappe.get_all("Custom Field", fields=["dt as parent", "fieldname"], filters=filters, as_list=1)

	ret = {}

	if not links:
		return ret

	links_dict = defaultdict(list)
	for doctype, fieldname in links:
		links_dict[doctype].append(fieldname)

	for doctype_name in links_dict:
		ret[doctype_name] = {"fieldname": links_dict.get(doctype_name)}
	table_doctypes = frappe.get_all(
		"DocType",
		filters=[["istable", "=", "1"], ["is_virtual", "=", "0"], ["name", "in", tuple(links_dict)]],
	)
	child_filters = [
		["fieldtype", "in", frappe.model.table_fields],
		["options", "in", tuple(doctype.name for doctype in table_doctypes)],
	]
	if without_ignore_user_permissions_enabled:
		child_filters.append(["ignore_user_permissions", "!=", 1])

	# find out if linked in a child table
	for parent, options in frappe.get_all(
		"DocField", fields=["parent", "options"], filters=child_filters, as_list=1
	):
		child_link = {"child_doctype": options, "fieldname": links_dict[options]}
		if parent in ret and "child_doctype" in ret[parent]:
			# parent links to doctype through more than one child table
			if "child_links" not in ret[parent]:
				ret[parent]["child_links"] = [dict(ret[parent])]
			ret[parent]["child_links"].append(child_link)
		else:
			ret[parent] = child_link
		ret.pop(options, None)

	virtual_doctypes = frappe.get_all("DocType", {"is_virtual": 1}, pluck="name")
	for dt in virtual_doctypes:
		ret.pop(dt, None)

	return ret


def get_dynamic_linked_fields(doctype, without_ignore_user_permissions_enabled=False):
	ret = {}

	filters = [["fieldtype", "=", "Dynamic Link"]]
	if without_ignore_user_permissions_enabled:
		filters.append(["ignore_user_permissions", "!=", 1])

	# find dynamic links of parents
	links = frappe.get_all(
		"DocField",
		fields=["parent as doctype", "fieldname", "options as doctype_fieldname"],
		filters=filters,
	)
	links += frappe.get_all(
		"Custom Field",
		fields=["dt as doctype", "fieldname", "options as doctype_fieldname"],
		filters=filters,
	)

	for df in links:
		if is_single(df.doctype):
			continue

		meta = frappe.get_meta(df.doctype)
		if meta.is_virtual:
			continue

		is_child = meta.istable
		possible_link = frappe.get_all(
			df.doctype,
			filters={df.doctype_fieldname: doctype},
			fields=["parenttype"] if is_child else None,
			distinct=True,
		)

		if not possible_link:
			continue

		if is_child:
			for d in possible_link:
				ret[d.parenttype] = {
					"child_doctype": df.doctype,
					"fieldname": [df.fieldname],
					"doctype_fieldname": df.doctype_fieldname,
				}
		else:
			ret[df.doctype] = {"fieldname": [df.fieldname], "doctype_fieldname": df.doctype_fieldname}

	return ret
