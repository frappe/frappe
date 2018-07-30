import frappe
from frappe.utils import nowdate, parse_val
from frappe import _

def run_automations(doc, method):
	if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
		return

	if doc.flags.automations == None:
		doc.flags.automations = get_automations(doc.doctype)

	if not doc.flags.automations:
		return

	event_map = {
		"on_update": "Save",
		"after_insert": "New",
		"on_submit": "Submit",
		"on_cancel": "Cancel"
	}

	if not doc.flags.in_insert:
		# value change is not applicable in insert
		event_map['validate'] = 'Value Change'
		event_map['before_change'] = 'Value Change'
		event_map['before_update_after_submit'] = 'Value Change'

	# called before updating, so just update the doc object, do not save the DB
	doc.flags.automation_before_update = True

	for action in doc.flags.automations:
		event = event_map.get(method, None)
		if event and action.event == event:
			run_automation(action, doc, event)
		elif action.event=='Method' and method == action.method:
			run_automation(action, doc, event)

def get_automations(doctype):
	automations = frappe.cache().hget('automations', doctype)
	if automations==None:
		automations = []
		for automation_type in frappe.get_hooks('automation_types'):
			automations.extend(frappe.get_all(automation_type,
				fields=['name', 'event', 'method', '`condition`', 'value_changed'],
				filters={'enabled': 1, 'document_type': doctype},
				update={'doctype': automation_type}
			))
		frappe.cache().hset('automations', doctype, automations)

	return automations


def run_automation(action, doc, event):
	'''Trigger action for a given doc for a given event'''
	_doc = doc
	if doc.flags.automations_executed is None:
		doc.flags.automations_executed = []

	if action.name in doc.flags.automations_executed:
		return

	try:
		context = get_context(doc)

		if action.condition:
			if not frappe.safe_eval(action.condition, None, context):
				return

		if not doc.is_new():
			if event=="Value Change":
				if not evaluate_value_change(doc, action):
					return

		if not hasattr(action, '__frappedoc__'):
			action = frappe.get_doc(action.doctype, action.name)

		action.execute(doc)
		_doc.flags.automations_executed.append(action.name)

	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title=str(e))
		frappe.throw(_("Error while evaluating {doctype} {name}").format(doctype=action.doctype, name=action.name), e)

def evaluate_value_change(doc, action):
	try:
		db_value = frappe.db.get_value(doc.doctype, doc.name, action.value_changed)
	except Exception:
		frappe.db.set_value(action.doctype, action.name, 'enabled', 0)
		frappe.log_error('{0} {1} has been disabled due to missing field'.format(action.doctype, action.name))
		return False

	db_value = parse_val(db_value)
	if (doc.get(action.value_changed) == db_value) or \
		(not db_value and not doc.get(action.value_changed)):

		return False

	return True

def get_context(doc):
	return {"doc": doc, "nowdate": nowdate, "frappe.utils": frappe.utils}