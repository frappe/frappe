# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Built-in automation actions. Each delegates to existing framework internals."""

import frappe
from frappe import _
from frappe.automation_engine.actions.base import AutomationAction, AutomationParamError


class SetFieldValue(AutomationAction):
	action_type = "SetFieldValue"
	label = "Set Field Value"
	description = "Set a field on the triggering document."
	params_schema = [
		{"fieldname": "field", "label": "Field", "fieldtype": "Select", "reqd": 1, "options_source": "doc_fields"},
		{"fieldname": "value", "label": "Value", "fieldtype": "Data", "reqd": 1},
	]

	def validate(self, params, doctype):
		field = params.get("field")
		if not field:
			raise AutomationParamError(_("Field is required"), fieldname="field")
		if not frappe.get_meta(doctype).get_field(field):
			raise AutomationParamError(
				_("{0} has no field {1}").format(doctype, field), fieldname="field"
			)

	def execute(self, doc, params, context):
		field, value = params["field"], params.get("value")
		doc.set(field, value)
		doc.save(ignore_permissions=True)
		return _("Set {0} = {1}").format(field, value)


CORE_ACTIONS = [SetFieldValue]
