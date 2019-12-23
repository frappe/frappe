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

@frappe.whitelist()
def create_contact_phone_nos_records():
	if frappe.db.get_all('Contact', {'first_name': 'Test Contact'}):
		return

	doc = frappe.new_doc('Contact')
	doc.first_name = 'Test Contact'
	for index in range(1000):
		doc.append('phone_nos', {'phone': '123456{}'.format(index)})
	doc.insert()

@frappe.whitelist()
def create_contact_records():
	if frappe.db.get_all('Contact', {'first_name': 'Test Form Contact 1'}):
		return

	insert_contact('Test Form Contact 1', '12345')
	insert_contact('Test Form Contact 2', '54321')
	insert_contact('Test Form Contact 3', '12345')


def insert_contact(first_name, phone_number):
	doc = frappe.get_doc({
		'doctype': 'Contact',
		'first_name': first_name
	})
	doc.append('phone_nos', {'phone': phone_number})
	doc.insert()
