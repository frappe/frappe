# Copyright (c) 2022, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections.abc import Iterable

import frappe
from frappe import _
from frappe.cache_manager import clear_doctype_map, get_doctype_map
from frappe.desk.form import assign_to
from frappe.model import log_types
from frappe.model.document import Document


class AssignmentRule(Document):
	def validate(self):
		self.validate_document_types()
		self.validate_assignment_days()

	def clear_cache(self):
		super().clear_cache()
		clear_doctype_map(self.doctype, self.document_type)
		clear_doctype_map(self.doctype, f"due_date_rules_for_{self.document_type}")

	def validate_document_types(self):
		if self.document_type == "ToDo":
			frappe.throw(
				_("Assignment Rule is not allowed on {0} document type").format(frappe.bold("ToDo"))
			)

	def validate_assignment_days(self):
		assignment_days = self.get_assignment_days()

		if len(set(assignment_days)) != len(assignment_days):
			repeated_days = get_repeated(assignment_days)
			plural = "s" if len(repeated_days) > 1 else ""

			frappe.throw(
				_("Assignment Day{0} {1} has been repeated.").format(
					plural, frappe.bold(", ".join(repeated_days))
				)
			)

	def apply_unassign(self, doc, assignments):
		if self.unassign_condition and self.name in [d.assignment_rule for d in assignments]:
			return self.clear_assignment(doc)

		return False

	def apply_assign(self, doc):
		if self.safe_eval("assign_condition", doc):
			return self.do_assignment(doc)

	def do_assignment(self, doc):
		# clear existing assignment, to reassign
		assign_to.clear(doc.get("doctype"), doc.get("name"), ignore_permissions=True)

		user = self.get_user(doc)

		if user:
			assign_to.add(
				dict(
					assign_to=[user],
					doctype=doc.get("doctype"),
					name=doc.get("name"),
					description=frappe.render_template(self.description, doc),
					assignment_rule=self.name,
					notify=True,
					date=doc.get(self.due_date_based_on) if self.due_date_based_on else None,
				),
				ignore_permissions=True,
			)

			# set for reference in round robin
			self.db_set("last_user", user)
			return True

		return False

	def clear_assignment(self, doc):
		"""Clear assignments"""
		if self.safe_eval("unassign_condition", doc):
			return assign_to.clear(doc.get("doctype"), doc.get("name"), ignore_permissions=True)

	def close_assignments(self, doc):
		"""Close assignments"""
		if self.safe_eval("close_condition", doc):
			return assign_to.close_all_assignments(
				doc.get("doctype"), doc.get("name"), ignore_permissions=True
			)

	def get_user(self, doc):
		"""
		Get the next user for assignment
		"""
		if self.rule == "Round Robin":
			return self.get_user_round_robin()
		elif self.rule == "Load Balancing":
			return self.get_user_load_balancing()
		elif self.rule == "Based on Field":
			return self.get_user_based_on_field(doc)

	def get_user_round_robin(self):
		"""
		Get next user based on round robin
		"""

		# first time, or last in list, pick the first
		if not self.last_user or self.last_user == self.users[-1].user:
			return self.users[0].user

		# find out the next user in the list
		for i, d in enumerate(self.users):
			if self.last_user == d.user:
				return self.users[i + 1].user

		# bad last user, assign to the first one
		return self.users[0].user

	def get_user_load_balancing(self):
		"""Assign to the user with least number of open assignments"""
		counts = []
		for d in self.users:
			counts.append(
				dict(
					user=d.user,
					count=frappe.db.count(
						"ToDo", dict(reference_type=self.document_type, allocated_to=d.user, status="Open")
					),
				)
			)

		# sort by dict value
		sorted_counts = sorted(counts, key=lambda k: k["count"])

		# pick the first user
		return sorted_counts[0].get("user")

	def get_user_based_on_field(self, doc):
		val = doc.get(self.field)
		if frappe.db.exists("User", val):
			return val

	def safe_eval(self, fieldname, doc):
		try:
			if self.get(fieldname):
				return frappe.safe_eval(self.get(fieldname), None, doc)
		except Exception as e:
			# when assignment fails, don't block the document as it may be
			# a part of the email pulling
			frappe.msgprint(frappe._("Auto assignment failed: {0}").format(str(e)), indicator="orange")

		return False

	def get_assignment_days(self):
		return [d.day for d in self.get("assignment_days", [])]

	def is_rule_not_applicable_today(self):
		today = frappe.flags.assignment_day or frappe.utils.get_weekday()
		assignment_days = self.get_assignment_days()
		return assignment_days and today not in assignment_days


def get_assignments(doc) -> list[dict]:
	return frappe.get_all(
		"ToDo",
		fields=["name", "assignment_rule"],
		filters=dict(
			reference_type=doc.get("doctype"), reference_name=doc.get("name"), status=("!=", "Cancelled")
		),
		limit=5,
	)


@frappe.whitelist()
def bulk_apply(doctype, docnames):
	docnames = frappe.parse_json(docnames)
	background = len(docnames) > 5

	for name in docnames:
		if background:
			frappe.enqueue(
				"frappe.automation.doctype.assignment_rule.assignment_rule.apply",
				doc=None,
				doctype=doctype,
				name=name,
			)
		else:
			apply(doctype=doctype, name=name)


def reopen_closed_assignment(doc):
	todo_list = frappe.get_all(
		"ToDo",
		filters={
			"reference_type": doc.doctype,
			"reference_name": doc.name,
			"status": "Closed",
		},
		pluck="name",
	)

	for todo in todo_list:
		todo_doc = frappe.get_doc("ToDo", todo)
		todo_doc.status = "Open"
		todo_doc.save(ignore_permissions=True)

	return bool(todo_list)


def apply(doc=None, method=None, doctype=None, name=None):
	doctype = doctype or doc.doctype

	skip_assignment_rules = (
		frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_setup_wizard
		or doctype in log_types
	)

	if skip_assignment_rules:
		return

	if not doc and doctype and name:
		doc = frappe.get_doc(doctype, name)

	assignment_rules = get_doctype_map(
		"Assignment Rule",
		doc.doctype,
		filters={"document_type": doc.doctype, "disabled": 0},
		order_by="priority desc",
	)

	# multiple auto assigns
	assignment_rule_docs: list[AssignmentRule] = [
		frappe.get_cached_doc("Assignment Rule", d.get("name")) for d in assignment_rules
	]

	if not assignment_rule_docs:
		return

	doc = doc.as_dict()
	assignments = get_assignments(doc)

	clear = True  # are all assignments cleared
	new_apply = False  # are new assignments applied

	if assignments:
		# first unassign
		# use case, there are separate groups to be assigned for say L1 and L2,
		# so when the value switches from L1 to L2, L1 team must be unassigned, then L2 can be assigned.
		clear = False
		for assignment_rule in assignment_rule_docs:
			if assignment_rule.is_rule_not_applicable_today():
				continue

			clear = assignment_rule.apply_unassign(doc, assignments)
			if clear:
				break

	# apply rule only if there are no existing assignments
	if clear:
		for assignment_rule in assignment_rule_docs:
			if assignment_rule.is_rule_not_applicable_today():
				continue

			new_apply = assignment_rule.apply_assign(doc)
			if new_apply:
				break

	# apply close rule only if assignments exists
	assignments = get_assignments(doc)

	if assignments:
		for assignment_rule in assignment_rule_docs:
			if assignment_rule.is_rule_not_applicable_today():
				continue

			if not new_apply:
				# only reopen if close condition is not satisfied
				to_close_todos = assignment_rule.safe_eval("close_condition", doc)

				if to_close_todos:
					# close todo status
					todos_to_close = frappe.get_all(
						"ToDo",
						filters={
							"reference_type": doc.doctype,
							"reference_name": doc.name,
						},
						pluck="name",
					)

					for todo in todos_to_close:
						_todo = frappe.get_doc("ToDo", todo)
						_todo.status = "Closed"
						_todo.save(ignore_permissions=True)
					break

				else:
					reopened = reopen_closed_assignment(doc)
					if reopened:
						break

			assignment_rule.close_assignments(doc)


def update_due_date(doc, state=None):
	"""Run on_update on every Document (via hooks.py)"""
	skip_document_update = (
		frappe.flags.in_migrate
		or frappe.flags.in_patch
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
		or frappe.flags.in_install
	)

	if skip_document_update:
		return

	assignment_rules = get_doctype_map(
		doctype="Assignment Rule",
		name=f"due_date_rules_for_{doc.doctype}",
		filters={
			"due_date_based_on": ["is", "set"],
			"document_type": doc.doctype,
			"disabled": 0,
		},
	)

	for rule in assignment_rules:
		rule_doc = frappe.get_cached_doc("Assignment Rule", rule.get("name"))
		due_date_field = rule_doc.due_date_based_on
		field_updated = (
			doc.meta.has_field(due_date_field)
			and doc.has_value_changed(due_date_field)
			and rule.get("name")
		)

		if field_updated:
			assignment_todos = frappe.get_all(
				"ToDo",
				filters={
					"assignment_rule": rule.get("name"),
					"reference_type": doc.doctype,
					"reference_name": doc.name,
					"status": "Open",
				},
				pluck="name",
			)

			for todo in assignment_todos:
				todo_doc = frappe.get_doc("ToDo", todo)
				todo_doc.date = doc.get(due_date_field)
				todo_doc.flags.updater_reference = {
					"doctype": "Assignment Rule",
					"docname": rule.get("name"),
					"label": _("via Assignment Rule"),
				}
				todo_doc.save(ignore_permissions=True)


def get_assignment_rules() -> list[str]:
	return frappe.get_all("Assignment Rule", filters={"disabled": 0}, pluck="document_type")


def get_repeated(values: Iterable) -> list:
	unique = set()
	repeated = set()

	for value in values:
		if value in unique:
			repeated.add(value)
		else:
			unique.add(value)

	return [str(x) for x in repeated]
