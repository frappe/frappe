# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import itertools
from collections import defaultdict, deque

import frappe
import frappe.desk.form.load
import frappe.desk.form.meta
from frappe import _
from frappe.model.meta import is_single
from frappe.modules import load_doctype_module


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
	"""

	ignore_doctypes_on_cancel_all = frappe.parse_json(ignore_doctypes_on_cancel_all) or []

	frappe.has_permission(doctype, doc=name, throw=True)
	tree = SubmittableDocumentTree(doctype, name)
	visited_documents = tree.get_all_children(ignore_doctypes_on_cancel_all)
	docs = []

	for dt, names in visited_documents.items():
		docs.extend([{"doctype": dt, "name": name, "docstatus": 1} for name in names])

	# Deepest documents first, so referencing documents get cancelled before
	# the documents they reference.
	docs.sort(key=lambda doc: tree.depth_by_document[doc["doctype"], doc["name"]], reverse=True)

	return {"docs": docs, "count": len(docs)}


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

		self._submittable_doctypes = None  # All submittable doctypes in the system
		self._references_across_doctypes = None  # doctype wise links/references

	def get_all_children(self, ignore_doctypes_on_cancel_all):
		"""Get all nodes of a tree except the root node (all the nested submitted
		documents those are present in referencing tables dependent tables).
		"""
		depth = 0
		while self.to_be_visited_documents:
			depth += 1
			current_level = self.visit_current_level(ignore_doctypes_on_cancel_all)
			next_level_children = defaultdict(list)
			for parent_dt, parent_docs in current_level.items():
				child_docs = self.get_next_level_children(parent_dt, parent_docs)
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
		return {from_table: frappe.get_all(from_table, filters, pluck="name", order_by=None)}

	filters.extend(child_filters or [])
	res = frappe.get_all(from_table, filters=filters, fields=["name", "parenttype", "parent"], order_by=None)
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
	docs: str | list,
	ignore_doctypes_on_cancel_all: str | list[str] | None = None,
	root_doctype: str | None = None,
	root_name: str | None = None,
):
	"""
	Cancel all linked doctype, optionally ignore doctypes specified in a list.

	A document whose cancellation another document blocks, through a link or a
	controller check that wants the other document cancelled first, is deferred
	and retried after the rest, so callers need not pass docs in dependency
	order.

	A set larger than MAX_SYNCHRONOUS_LINKED_DOCS is cancelled in a background
	job together with the root document, the user is notified when it finishes,
	and the call returns {"queued": True}.

	Arguments:
	        docs (json str) - It contains list of dictionaries of a linked documents.
	        ignore_doctypes_on_cancel_all (list) - List of doctypes to ignore while cancelling.
	        root_doctype, root_name - The document whose links are being cancelled;
	                only cancelled here when the work moves to a background job.
	"""
	if ignore_doctypes_on_cancel_all is None:
		ignore_doctypes_on_cancel_all = []

	docs = frappe.parse_json(docs)
	ignore_doctypes_on_cancel_all = frappe.parse_json(ignore_doctypes_on_cancel_all)

	to_cancel = [doc for doc in deduplicated(docs) if validate_linked_doc(doc, ignore_doctypes_on_cancel_all)]
	if len(to_cancel) > MAX_SYNCHRONOUS_LINKED_DOCS:
		return enqueue_linked_docs_processing(to_cancel, "cancel", root_doctype, root_name)

	process_linked_docs_in_dependency_order(to_cancel, cancel_linked_doc, _("Cancelling documents"))


def cancel_linked_doc(docinfo):
	"""Cancel a document unless the on_cancel hook of another document already cancelled it."""
	doc = frappe.get_doc(docinfo.get("doctype"), docinfo.get("name"))
	if doc.docstatus.is_submitted():
		doc.cancel()


MAX_LINKED_DELETE_DOCUMENTS = 500


@frappe.whitelist()
def get_linked_docs_to_delete(doctype: str, name: str) -> dict:
	"""Get all documents that block deletion of the given document, including
	documents that block deletion of those documents, and so on.

	Documents the user cannot read are neither returned nor traversed, so their
	identities stay hidden and their deletion fails with the regular link error.

	Deepest documents come first, so deleting in list order resolves the links.

	Traversal stops once MAX_LINKED_DELETE_DOCUMENTS is exceeded and returns no
	documents marked truncated; deletion can still proceed through
	delete_all_linked_docs without docs, which discovers the graph in a
	background job where the cap does not apply.
	"""
	frappe.has_permission(doctype, doc=name, throw=True)
	docs, truncated = collect_deletion_blockers(doctype, name, limit=MAX_LINKED_DELETE_DOCUMENTS)
	return {"docs": docs, "count": len(docs), "truncated": truncated}


def collect_deletion_blockers(doctype: str, name: str, limit: int | None = None) -> tuple[list, bool]:
	"""Walk the delete-blocking graph breadth first, deepest documents first in
	the result; past `limit` discovered documents, give up and report truncated."""
	from frappe.model.delete_doc import get_dynamic_linked_docs
	from frappe.model.delete_doc import get_linked_docs as get_statically_linked_docs

	root_key = (doctype, name)
	depth_by_document = {root_key: 0}
	queue = deque([root_key])
	while queue:
		parent_key = queue.popleft()
		# a lightweight stand-in is enough for the link lookups; loading the
		# full document of every node is too expensive
		parent = frappe._dict(doctype=parent_key[0], name=parent_key[1])
		links = get_statically_linked_docs(parent, method="Delete") + get_dynamic_linked_docs(
			parent, method="Delete"
		)
		for link in links:
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
) -> dict:
	"""
	Delete as many of the given documents as their links allow.

	A document that other documents still reference is deferred and retried
	after the rest, so callers need not pass docs in dependency order. A
	document that stays undeletable is skipped without undoing the rest.
	Return the deleted and the skipped documents.

	A set larger than MAX_SYNCHRONOUS_LINKED_DOCS is deleted in a background
	job together with the root document, the user is notified when it finishes,
	and the call returns {"queued": True}. Without docs, the graph was too
	large to even list: the background job discovers it itself, uncapped.

	Arguments:
	        docs (json str) - It contains list of dictionaries of the documents to delete.
	        root_doctype, root_name - The document whose links are being deleted;
	                only deleted here when the work moves to a background job.
	"""
	if docs is None:
		if not (root_doctype and root_name):
			frappe.throw(_("Either the documents to delete or a root document is required"))
		frappe.has_permission(root_doctype, doc=root_name, throw=True)
		return enqueue_linked_docs_processing([], "delete", root_doctype, root_name, discover=True)

	to_delete = deduplicated(frappe.parse_json(docs))
	if len(to_delete) > MAX_SYNCHRONOUS_LINKED_DOCS:
		return enqueue_linked_docs_processing(to_delete, "delete", root_doctype, root_name)

	# No realtime progress here: the events race the requests and navigation
	# that follow deletion and can strand the progress dialog; the freeze
	# overlay of the call covers the feedback.
	skipped = process_linked_docs_in_dependency_order(to_delete, delete_linked_doc, raise_when_stuck=False)
	return {"deleted": [doc for doc in to_delete if doc not in skipped], "skipped": skipped}


def delete_linked_doc(docinfo):
	"""Delete a document; one already removed by another document's on_trash hook is ignored."""
	frappe.delete_doc(docinfo.get("doctype"), docinfo.get("name"))


def enqueue_linked_docs_processing(docs, action, root_doctype, root_name, discover=False):
	"""Queue processing of a large set together with the root document, which
	the caller must not touch before the job has processed its links. With
	discover, the job walks the graph itself instead of receiving it."""
	job_kwargs = {}
	if root_doctype and root_name:
		if not discover:
			docs = [*docs, frappe._dict(doctype=root_doctype, name=root_name)]
		job_kwargs = {"job_id": f"linked_docs_{action}::{root_doctype}::{root_name}", "deduplicate": True}

	frappe.enqueue(
		process_linked_docs_in_background,
		docs=docs,
		action=action,
		discover_root=(root_doctype, root_name) if discover else None,
		queue="long",
		now=frappe.in_test,
		**job_kwargs,
	)
	return {"queued": True}


def process_linked_docs_in_background(docs, action, discover_root=None):
	"""Process the docs and notify the user of the outcome, since a background
	job has no response to report through. With discover_root, walk the graph
	here, where the listing cap does not apply.

	Cancellation is all or nothing, matching the synchronous behaviour, since a
	half-cancelled tree cannot be uncancelled. Deletion is best effort: some
	blockers are permanently undeletable yet harmless, so the rest proceeds and
	the leftovers are counted."""
	if discover_root:
		docs, _truncated = collect_deletion_blockers(*discover_root)
		docs = [*docs, frappe._dict(doctype=discover_root[0], name=discover_root[1])]

	if action == "cancel":
		side_effect_counts = capture_pending_side_effects()
		frappe.db.savepoint("cancel_linked_docs_job")
		try:
			process_linked_docs_in_dependency_order(docs, cancel_linked_doc)
		except (
			frappe.ValidationError,
			frappe.PermissionError,
			frappe.QueryTimeoutError,
			frappe.QueryDeadlockError,
		) as error:
			frappe.db.rollback(save_point="cancel_linked_docs_job")
			discard_side_effects_since(side_effect_counts)
			notify_linked_docs_processed(
				_("Could not cancel {0} linked documents: {1}").format(len(docs), str(error))
			)
			return
		notify_linked_docs_processed(_("Cancelled {0} linked documents.").format(len(docs)))
		return

	skipped = process_linked_docs_in_dependency_order(docs, delete_linked_doc, raise_when_stuck=False)
	done = len(docs) - len(skipped)
	message = (
		_("Deleted {0} linked documents; {1} could not be deleted.").format(done, len(skipped))
		if skipped
		else _("Deleted {0} linked documents.").format(done)
	)
	notify_linked_docs_processed(message)


def notify_linked_docs_processed(message):
	"""Tell the user live when they are still around, and durably via a notification."""
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	frappe.publish_realtime("msgprint", {"message": message, "alert": True}, user=frappe.session.user)
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


def process_linked_docs_in_dependency_order(docs, process, progress_title=None, raise_when_stuck=True):
	"""Run process over docs, deferring a document blocked by another document
	to a later pass, until a full pass makes no progress.

	Any validation or permission failure defers, not just link errors: a
	controller may block cancellation until a referencing document is cancelled
	first, and some documents cannot be processed directly but stop being in
	the way as a side effect of processing a document near them (e.g. ledger
	entries that only the on_trash hook of their voucher removes). A document
	locked by another session or caught in a deadlock defers too, since the
	lock may be gone by the retry pass.

	Once stuck, either surface the error of the first blocked document or, with
	raise_when_stuck disabled, keep the progress made and return the blocked
	documents."""
	total = len(docs)
	processed = 0
	save_point = "process_linked_doc"
	while docs:
		deferred = []
		for doc in docs:
			side_effect_counts = capture_pending_side_effects()
			frappe.db.savepoint(save_point)
			try:
				process(doc)
			except (
				frappe.ValidationError,
				frappe.PermissionError,
				frappe.QueryTimeoutError,
				frappe.QueryDeadlockError,
			):
				# cancel and delete both run their hooks before the link check, so
				# roll back the writes of the failed attempt before deferring, and
				# drop the messages and side effects it queued, which savepoints
				# cannot undo
				frappe.db.rollback(save_point=save_point)
				discard_side_effects_since(side_effect_counts)
				deferred.append(doc)
				continue
			frappe.db.release_savepoint(save_point)
			processed += 1
			if progress_title:
				frappe.publish_progress(percent=processed / total * 100, title=progress_title)

		if len(deferred) == len(docs):
			if raise_when_stuck:
				# a document outside `docs` blocks the rest; process without
				# catching to surface the link error
				process(deferred[0])
			return deferred
		docs = deferred
	return []


def capture_pending_side_effects() -> dict:
	"""The pending side-effect queues, which savepoints cannot restore.

	The message log and currently_saving are captured as copies, not lengths:
	some permission checks swap the message log out without restoring it when
	they raise, and a failed document save leaks its currently_saving entry."""
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
	"""Drop side effects queued after capture: the messages, commit hooks,
	realtime events and webhook executions of a rolled-back attempt would
	otherwise still run.

	Rollback watchers the attempt registered are executed rather than dropped:
	a savepoint rollback does not run them, yet the work they compensate for
	(files written, caches primed) is being undone right here."""
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
			# the attempt created the log and its flush hook, which the truncation
			# above removed; drop the log so the next event re-registers the flush
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
