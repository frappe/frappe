import frappe
from frappe.utils import add_to_date, now

@frappe.whitelist()
def create_if_not_exists(doc):
	'''Create records if they dont exist.
	Will check for uniqueness by checking if a record exists with these field value pairs

	:param doc: dict of field value pairs. can be a list of dict for multiple records.
	'''

	doc = frappe.parse_json(doc)

	if not isinstance(doc, list):
		docs = [doc]
	else:
		docs = doc

	names = []
	for doc in docs:
		doc = frappe._dict(doc)
		filters = doc.copy()
		filters.pop('doctype')
		name = frappe.db.exists(doc.doctype, filters)
		if not name:
			d = frappe.get_doc(doc)
			d.insert(ignore_permissions=True)
			name = d.name
		names.append(name)

	return names


@frappe.whitelist()
def create_todo_records():
	if frappe.db.get_all('ToDo', {'description': 'this is first todo'}):
		return

	frappe.get_doc({
		"doctype": "ToDo",
		"date": add_to_date(now(), days=3),
		"description": "this is first todo"
	}).insert()
	frappe.get_doc({
		"doctype": "ToDo",
		"date": add_to_date(now(), days=-3),
		"description": "this is second todo"
	}).insert()
	frappe.get_doc({
		"doctype": "ToDo",
		"date": add_to_date(now(), months=2),
		"description": "this is third todo"
	}).insert()
	frappe.get_doc({
		"doctype": "ToDo",
		"date": add_to_date(now(), months=-2),
		"description": "this is fourth todo"
	}).insert()

@frappe.whitelist()
def setup_workflow():
  from frappe.workflow.doctype.workflow.test_workflow import create_todo_workflow
  create_todo_workflow()
  create_todo_records()
  frappe.clear_cache()
