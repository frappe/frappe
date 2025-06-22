# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import itertools
import json
from collections import defaultdict

import frappe
import frappe.desk.form.load
import frappe.desk.form.meta
from frappe import _
from frappe.model.meta import is_single
from frappe.modules import load_doctype_module


@frappe.whitelist()
def get_submitted_linked_docs(doctype: str, name: str, ignore_doctypes_on_cancel_all=None) -> list[tuple]:
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

	if isinstance(ignore_doctypes_on_cancel_all, str):
		ignore_doctypes_on_cancel_all = json.loads(ignore_doctypes_on_cancel_all)

	frappe.has_permission(doctype, doc=name, throw=True)
	tree = SubmittableDocumentTree(doctype, name)
	visited_documents = tree.get_all_children(ignore_doctypes_on_cancel_all)
	docs = []

	for dt, names in visited_documents.items():
		docs.extend([{"doctype": dt, "name": name, "docstatus": 1} for name in names])

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

		self._submittable_doctypes = None  # All submittable doctypes in the system
		self._references_across_doctypes = None  # doctype wise links/references

	def get_all_children(self, ignore_doctypes_on_cancel_all):
		"""Get all nodes of a tree except the root node (all the nested submitted
		documents those are present in referencing tables dependent tables).
		"""
		while self.to_be_visited_documents:
			next_level_children = defaultdict(list)
			for parent_dt in list(self.to_be_visited_documents):
				parent_docs = self.to_be_visited_documents.get(parent_dt)
				if not parent_docs or (
					ignore_doctypes_on_cancel_all and parent_dt in ignore_doctypes_on_cancel_all
				):
					del self.to_be_visited_documents[parent_dt]
					continue

				child_docs = self.get_next_level_children(parent_dt, parent_docs)
				self.visited_documents[parent_dt].extend(parent_docs)
				for linked_dt, linked_names in child_docs.items():
					not_visited_child_docs = set(linked_names) - set(
						self.visited_documents.get(linked_dt, [])
					)
					next_level_children[linked_dt].extend(not_visited_child_docs)

			self.to_be_visited_documents = next_level_children

		# Remove root node from visited documents
		if self.root_docname in self.visited_documents.get(self.root_doctype, []):
			self.visited_documents[self.root_doctype].remove(self.root_docname)

		return self.visited_documents

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
			for linked_to in frappe.get_all(doctype, pluck=doctype_fieldname, filters=filters, distinct=1):
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


@frappe.whitelist()
def cancel_all_linked_docs(docs, ignore_doctypes_on_cancel_all=None):
	"""
	Cancel all linked doctype, optionally ignore doctypes specified in a list.

	Arguments:
	        docs (json str) - It contains list of dictionaries of a linked documents.
	        ignore_doctypes_on_cancel_all (list) - List of doctypes to ignore while cancelling.
	"""
	if ignore_doctypes_on_cancel_all is None:
		ignore_doctypes_on_cancel_all = []

	docs = json.loads(docs)
	if isinstance(ignore_doctypes_on_cancel_all, str):
		ignore_doctypes_on_cancel_all = json.loads(ignore_doctypes_on_cancel_all)
	for i, doc in enumerate(docs, 1):
		if validate_linked_doc(doc, ignore_doctypes_on_cancel_all):
			linked_doc = frappe.get_doc(doc.get("doctype"), doc.get("name"))
			linked_doc.cancel()
		frappe.publish_progress(percent=i / len(docs) * 100, title=_("Cancelling documents"))


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
	if isinstance(linkinfo, str):
		# additional fields are added in linkinfo
		linkinfo = json.loads(linkinfo)

	results = {}

	if not linkinfo:
		return results

	is_target_doctype_table = frappe.get_meta(doctype).istable

	for linked_doctype, link_context in linkinfo.items():
		# Don't try to fetch linked documents if the user can't read the doctype
		if not frappe.has_permission(linked_doctype):
			continue

		linked_doctype_meta = frappe.get_meta(linked_doctype)

		if linked_doctype_meta.issingle:
			continue

		filters = []
		ret = None
		parent_info = None

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

		fields = [f"`tab{linked_doctype}`.`{sf.strip()}`" for sf in fields if sf and "`tab" not in sf]

		if filters_ctx := link_context.get("filters"):
			ret = frappe.get_list(doctype=linked_doctype, fields=fields, filters=filters_ctx, order_by=None)

		elif link_context.get("get_parent"):
			# check for child table
			if not is_target_doctype_table:
				continue

			parent_info = parent_info or frappe.db.get_value(
				doctype, name, ["parenttype", "parent"], as_dict=True, order_by=None
			)

			if parent_info and parent_info.parenttype == linked_doctype:
				ret = frappe.get_list(
					doctype=linked_doctype,
					fields=fields,
					filters=[[linked_doctype, "name", "=", parent_info.parent]],
					order_by=None,
				)

		elif child_doctype := link_context.get("child_doctype"):
			or_filters = [
				[child_doctype, link_fieldnames, "=", name] for link_fieldnames in link_context["fieldname"]
			]

			# dynamic link_context
			if doctype_fieldname := link_context.get("doctype_fieldname"):
				filters.append([child_doctype, doctype_fieldname, "=", doctype])

			ret = frappe.get_list(
				doctype=linked_doctype,
				fields=fields,
				filters=filters,
				or_filters=or_filters,
				distinct=True,
				order_by=None,
			)

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
			ret = frappe.get_list(
				doctype=linked_doctype, fields=fields, filters=filters, or_filters=or_filters, order_by=None
			)

		if ret:
			results[linked_doctype] = ret

	return results


@frappe.whitelist()
def get(doctype, docname):
	frappe.has_permission(doctype, doc=docname, throw=True)
	linked_doctypes = get_linked_doctypes(doctype=doctype)
	return get_linked_docs(doctype=doctype, name=docname, linkinfo=linked_doctypes)


@frappe.whitelist()
def get_linked_doctypes(doctype, without_ignore_user_permissions_enabled=False):
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
		"DocType", filters=[["istable", "=", "1"], ["name", "in", tuple(links_dict)]]
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
		ret[parent] = {"child_doctype": options, "fieldname": links_dict[options]}
		if options in ret:
			del ret[options]

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
