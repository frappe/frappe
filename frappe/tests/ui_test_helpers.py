import frappe
from frappe import _
from frappe.utils import add_to_date, now

@frappe.whitelist()
def create_if_not_exists(doc):
	'''Create records if they dont exist.
	Will check for uniqueness by checking if a record exists with these field value pairs

	:param doc: dict of field value pairs. can be a list of dict for multiple records.
	'''

	if not frappe.local.dev_server:
		frappe.throw(_('This method can only be accessed in development'), frappe.PermissionError)

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
		"date": add_to_date(now(), days=7),
		"description": "this is first todo"
	}).insert()
	frappe.get_doc({
		"doctype": "ToDo",
		"date": add_to_date(now(), days=-7),
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
def create_communication_record():
	doc = frappe.get_doc({
		"doctype": "Communication",
		"recipients": "test@gmail.com",
		"subject": "Test Form Communication 1",
		"communication_date": frappe.utils.now_datetime(),
	})
	doc.insert()
	return doc

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
def create_doctype(name, fields):
	fields = frappe.parse_json(fields)
	if frappe.db.exists('DocType', name):
		return
	frappe.get_doc({
		"doctype": "DocType",
		"module": "Core",
		"custom": 1,
		"fields": fields,
		"permissions": [{
			"role": "System Manager",
			"read": 1
		}],
		"name": name
	}).insert()

@frappe.whitelist()
def create_child_doctype(name, fields):
	fields = frappe.parse_json(fields)
	if frappe.db.exists('DocType', name):
		return
	frappe.get_doc({
		"doctype": "DocType",
		"module": "Core",
		"istable": 1,
		"custom": 1,
		"fields": fields,
		"permissions": [{
			"role": "System Manager",
			"read": 1
		}],
		"name": name
	}).insert()

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

@frappe.whitelist()
def create_form_tour():
	if frappe.db.exists('Form Tour', {'name': 'Test Form Tour'}):
		return

	def get_docfield_name(filters):
		return frappe.db.get_value('DocField', filters, "name")

	tour = frappe.get_doc({
		'doctype': 'Form Tour',
		'title': 'Test Form Tour',
		'reference_doctype': 'Contact',
		'save_on_complete': 1,
		'steps': [{
			"title": "Test Title 1",
			"description": "Test Description 1",
			"has_next_condition": 1,
			"next_step_condition": "eval: doc.first_name",
			"field": get_docfield_name({'parent': 'Contact', 'fieldname': 'first_name'}),
			"fieldname": "first_name",
			"fieldtype": "Data"
		},{
			"title": "Test Title 2",
			"description": "Test Description 2",
			"has_next_condition": 1,
			"next_step_condition": "eval: doc.last_name",
			"field": get_docfield_name({'parent': 'Contact', 'fieldname': 'last_name'}),
			"fieldname": "last_name",
			"fieldtype": "Data"
		},{
			"title": "Test Title 3",
			"description": "Test Description 3",
			"field": get_docfield_name({'parent': 'Contact', 'fieldname': 'phone_nos'}),
			"fieldname": "phone_nos",
			"fieldtype": "Table"
		},{
			"title": "Test Title 4",
			"description": "Test Description 4",
			"is_table_field": 1,
			"parent_field": get_docfield_name({'parent': 'Contact', 'fieldname': 'phone_nos'}),
			"field": get_docfield_name({'parent': 'Contact Phone', 'fieldname': 'phone'}),
			"next_step_condition": "eval: doc.phone",
			"has_next_condition": 1,
			"fieldname": "phone",
			"fieldtype": "Data"
		}]
	})
	tour.insert()

@frappe.whitelist()
def create_data_for_discussions():
	web_page = create_web_page("Test page for discussions", "test-page-discussions", False)
	create_topic_and_reply(web_page)
	create_web_page("Test single thread discussion", "test-single-thread", True)

def create_web_page(title, route, single_thread):
	web_page = frappe.db.exists("Web Page", {"route": route})
	if not web_page:
		web_page = frappe.get_doc({
			"doctype": "Web Page",
			"title": title,
			"route": route,
			"published": True
		})
		web_page.save()

		web_page.append("page_blocks", {
			"web_template": "Discussions",
			"web_template_values": frappe.as_json({
				"title": "Discussions",
				"cta_title": "New Discussion",
				"docname": web_page.name,
				"single_thread": single_thread
			})
		})
		web_page.save()

	return web_page

def create_topic_and_reply(web_page):
	topic = frappe.db.exists("Discussion Topic",{
		"reference_doctype": "Web Page",
		"reference_docname": web_page.name
	})

	if not topic:
		topic = frappe.get_doc({
			"doctype": "Discussion Topic",
			"reference_doctype": "Web Page",
			"reference_docname": web_page.name,
			"title": "Test Topic"
		})
		topic.save()

		reply = frappe.get_doc({
			"doctype": "Discussion Reply",
			"topic": topic.name,
			"reply": "This is a test reply"
		})

		reply.save()
