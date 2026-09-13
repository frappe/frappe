# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import operator

from pypika.terms import Criterion, Not

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import DEFAULT_WORKFLOW_TASKS, get_workflow_names
from frappe.utils import cint
from frappe.utils.data import compare, evaluate_filters

CONDITION_COMPARATORS = {
	"=": operator.eq,
	"!=": operator.ne,
	">": operator.gt,
	"<": operator.lt,
	">=": operator.ge,
	"<=": operator.le,
}
LOWER_BOUND_CONDITIONS = {">", ">="}
UPPER_BOUND_CONDITIONS = {"<", "<="}


class Workflow(Document):
	_DOCTYPE_NAME = "Workflow"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from frappe.workflow.doctype.workflow_condition.workflow_condition import WorkflowCondition
		from frappe.workflow.doctype.workflow_document_state.workflow_document_state import (
			WorkflowDocumentState,
		)
		from frappe.workflow.doctype.workflow_transition.workflow_transition import WorkflowTransition

		conditions: DF.Table[WorkflowCondition]
		document_type: DF.Link
		is_active: DF.Check
		override_status: DF.Check
		priority: DF.Int
		send_email_alert: DF.Check
		states: DF.Table[WorkflowDocumentState]
		transitions: DF.Table[WorkflowTransition]
		workflow_data: DF.JSON | None
		workflow_name: DF.Data
		workflow_state_field: DF.Data
	# end: auto-generated types

	def validate(self):
		self.validate_fields_in_conditions()
		self.validate_shared_state_field()
		self.set_active()
		self.validate_no_ambiguous_peer()
		self.validate_docstatus()

	def on_update(self):
		self.create_custom_field_for_workflow_state()
		self.update_default_workflow_status()

	def on_trash(self):
		"""Drop this workflow's name from the doctype cache, which resolution reads without rechecking."""
		frappe.clear_cache(doctype=self.document_type)

	def create_custom_field_for_workflow_state(self):
		frappe.clear_cache(doctype=self.document_type)
		meta = frappe.get_meta(self.document_type)
		if not meta.get_field(self.workflow_state_field):
			# create custom field
			frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": self.document_type,
					"__islocal": 1,
					"fieldname": self.workflow_state_field,
					"label": self.workflow_state_field.replace("_", " ").title(),
					"hidden": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
					"fieldtype": "Link",
					"options": "Workflow State",
					"owner": "Administrator",
				}
			).save()

			frappe.msgprint(
				_("Created Custom Field {0} in {1}").format(self.workflow_state_field, self.document_type)
			)

	def update_default_workflow_status(self):
		"""Seed the state field of documents this workflow governs, leaving the rest untouched.

		A state this workflow does not define is treated as unset. A workflow that outranks a
		peer has to correct what the peer seeded before it existed, the same way validate_workflow
		re-enters a document whose stored state is foreign to the workflow that governs it.
		"""
		outranking = self.get_higher_priority_workflows()
		if any(not workflow.conditions for workflow in outranking):
			return

		docstatus_map = {}
		TargetDocType = frappe.qb.DocType(self.document_type)
		state_field = getattr(TargetDocType, self.workflow_state_field)
		criteria = self.get_condition_criteria(TargetDocType)
		criteria += [
			Not(Criterion.all(workflow.get_condition_criteria(TargetDocType))) for workflow in outranking
		]

		own_states = [d.state for d in self.states]

		for d in self.get("states"):
			if d.doc_status in docstatus_map:
				continue

			query = (
				frappe.qb.update(TargetDocType)
				.set(state_field, d.state)
				.where(state_field.isnull() | (state_field == "") | state_field.notin(own_states))
				.where(TargetDocType.docstatus == d.doc_status)
			)
			for criterion in criteria:
				query = query.where(criterion)

			query.run()
			docstatus_map[d.doc_status] = d.state

	def get_higher_priority_workflows(self) -> list["Workflow"]:
		"""Active workflows of this doctype that resolve before this one.

		Position, not priority: get_workflow_names breaks a tie by modification time, so comparing
		priority alone would let an older peer seed the documents its newer peer governs.
		"""
		names = get_workflow_names(self.document_type)
		if self.name not in names:
			return []

		return [frappe.get_cached_doc("Workflow", name) for name in names[: names.index(self.name)]]

	def get_condition_criteria(self, table) -> list:
		return [CONDITION_COMPARATORS[d.condition](getattr(table, d.field), d.value) for d in self.conditions]

	def validate_docstatus(self):
		def get_state(state):
			for s in self.states:
				if s.state == state:
					return s

			frappe.throw(frappe._("{0} not a valid State").format(state))

		meta = frappe.get_meta(self.document_type)
		is_submittable = meta.is_submittable

		if not is_submittable:
			for state in self.states:
				if cint(state.doc_status) != 0:
					frappe.throw(
						frappe._(
							"Workflow State '{0}' has Document Status {1}, but DocType '{2}' is not submittable. "
							"Only Document Status 0 (Draft) is allowed for non-submittable DocTypes."
						).format(state.state, state.doc_status, self.document_type)
					)

		for t in self.transitions:
			state = get_state(t.state)
			next_state = get_state(t.next_state)
			state_docstatus = cint(state.doc_status)
			next_state_docstatus = cint(next_state.doc_status)

			if state_docstatus == 2:
				frappe.throw(
					frappe._("Cannot change state of Cancelled Document. Transition row {0}").format(t.idx)
				)

			if state_docstatus == 1 and next_state_docstatus == 0:
				frappe.throw(
					frappe._(
						"Submitted Document cannot be converted back to draft. Transition row {0}"
					).format(t.idx)
				)

			if state_docstatus == 0 and next_state_docstatus == 2:
				frappe.throw(frappe._("Cannot cancel before submitting. See Transition {0}").format(t.idx))

	def applies_to(self, doc) -> bool:
		"""Return True if this workflow governs `doc`. A workflow without conditions governs all."""
		if not self.conditions:
			return True

		return evaluate_filters(
			doc, [(self.document_type, d.field, d.condition, d.value) for d in self.conditions]
		)

	def validate_fields_in_conditions(self):
		if not self.conditions:
			return

		docfields = {df.fieldname for df in frappe.get_meta(self.document_type).fields}
		for condition in self.conditions:
			if condition.field not in docfields:
				frappe.throw(
					_("{0} is not a field of doctype {1}").format(
						frappe.bold(condition.field), frappe.bold(self.document_type)
					)
				)

	def validate_shared_state_field(self):
		"""Every workflow of a doctype has to read its state from the same field.

		The desk resolves the state field per doctype, so two active workflows disagreeing on it
		would leave documents rendering against the wrong field.
		"""
		if not cint(self.is_active):
			return

		others = self.get_other_active_workflows(["name", "workflow_state_field"])
		for other in others:
			if other.workflow_state_field != self.workflow_state_field:
				frappe.throw(
					_(
						"Workflow {0} on {1} uses the state field {2}. Every active workflow of a doctype must use the same field."
					).format(
						frappe.bold(other.name),
						frappe.bold(self.document_type),
						frappe.bold(other.workflow_state_field),
					)
				)

	def validate_no_ambiguous_peer(self):
		"""Active workflows sharing a priority must not both be able to match one document.

		Resolution takes the first match in priority order, so a tie is settled by modification
		time, and the losing workflow is never reached.
		"""
		if not cint(self.is_active):
			return

		for peer in self.get_other_active_workflows(["name", "priority"]):
			if cint(peer.priority) != cint(self.priority):
				continue

			if not self.is_disjoint_from(frappe.get_cached_doc("Workflow", peer.name)):
				frappe.throw(
					_(
						"Workflow {0} has the same priority and can govern the same {1}. Narrow the conditions of either workflow, or give them different priorities."
					).format(frappe.bold(peer.name), frappe.bold(self.document_type))
				)

	def is_disjoint_from(self, other: "Workflow") -> bool:
		"""True when a field the two workflows share proves no document can match both."""
		return any(
			self.is_contradictory(own, their)
			for own in self.conditions
			for their in other.conditions
			if own.field == their.field
		)

	def is_contradictory(self, first, second) -> bool:
		"""True when no value of the field the two conditions share can satisfy both."""
		docfield = frappe.get_meta(self.document_type).get_field(first.field)
		fieldtype = docfield.fieldtype if docfield else None

		if first.condition == "=":
			return not compare(first.value, second.condition, second.value, fieldtype)

		if second.condition == "=":
			return not compare(second.value, first.condition, first.value, fieldtype)

		return is_empty_range(first, second, fieldtype)

	def set_active(self):
		"""Retire the other catch-all workflow of this doctype; conditional ones can coexist."""
		if not cint(self.is_active) or self.conditions:
			return

		names = [other.name for other in self.get_other_active_workflows(["name"])]
		if not names:
			return

		conditional = set(
			frappe.get_all(
				"Workflow Condition",
				filters={"parenttype": "Workflow", "parent": ("in", names)},
				pluck="parent",
			)
		)
		for name in names:
			if name not in conditional:
				frappe.db.set_value("Workflow", name, "is_active", 0)

	def get_other_active_workflows(self, fields: list[str]) -> list:
		"""Read the peers straight from the table.

		This runs during validate, before this workflow's own row exists. Going through the
		cached name list would store an answer taken from that gap and hand it to every document
		saved afterwards.
		"""
		return frappe.get_all(
			"Workflow",
			filters={
				"document_type": self.document_type,
				"is_active": 1,
				"name": ("!=", self.name),
			},
			fields=fields,
		)


def is_empty_range(first, second, fieldtype) -> bool:
	"""True when a lower bound and an upper bound on the same field leave no value between them."""
	lower, upper = first, second
	if lower.condition in UPPER_BOUND_CONDITIONS:
		lower, upper = upper, lower

	if lower.condition not in LOWER_BOUND_CONDITIONS or upper.condition not in UPPER_BOUND_CONDITIONS:
		return False

	both_inclusive = lower.condition == ">=" and upper.condition == "<="
	return compare(lower.value, ">" if both_inclusive else ">=", upper.value, fieldtype)


@frappe.whitelist()
def get_workflow_state_count(doctype: str, workflow_state_field: str, states: str | list[str]):
	frappe.has_permission(doctype=doctype, ptype="read", throw=True)
	states = frappe.parse_json(states)

	if workflow_state_field in frappe.get_meta(doctype).get_valid_columns():
		result = frappe.get_all(
			doctype,
			fields=[workflow_state_field, {"COUNT": "*", "as": "count"}],
			filters={workflow_state_field: ["not in", states]},
			group_by=workflow_state_field,
		)
		return [r for r in result if r[workflow_state_field]]


@frappe.whitelist(methods=["GET"])
def get_workflow_methods():
	return [i["name"] for i in frappe.get_hooks("workflow_methods")] + DEFAULT_WORKFLOW_TASKS
