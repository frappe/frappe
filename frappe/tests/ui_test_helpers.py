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

@frappe.whitelist()
def create_multiple_todo_records():
	values = []
	if frappe.db.get_all('ToDo', {'description': 'Multiple ToDo 1'}):
		return

	for index in range(1, 1002):
		values.append(('100{}'.format(index), 'Multiple ToDo {}'.format(index)))

	frappe.db.bulk_insert('ToDo', fields=['name', 'description'], values=set(values))

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
			"fieldname": "first_name",
			"fieldtype": "Data"
		},{
			"title": "Test Title 2",
			"description": "Test Description 2",
			"has_next_condition": 1,
			"next_step_condition": "eval: doc.last_name",
			"fieldname": "last_name",
			"fieldtype": "Data"
		},{
			"title": "Test Title 3",
			"description": "Test Description 3",
			"fieldname": "phone_nos",
			"fieldtype": "Table"
		},{
			"title": "Test Title 4",
			"description": "Test Description 4",
			"is_table_field": 1,
			"parent_fieldname": "phone_nos",
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


@frappe.whitelist()
def update_webform_to_multistep():
	if not frappe.db.exists("Web Form", "update-profile-duplicate"):
		doc = frappe.get_doc("Web Form", "edit-profile")
		_doc = frappe.copy_doc(doc)
		_doc.is_multi_step_form = 1
		_doc.title = "update-profile-duplicate"
		_doc.route = "update-profile-duplicate"
		_doc.is_standard = False
		_doc.save()

@frappe.whitelist()
def update_child_table(name):
	doc = frappe.get_doc('DocType', name)
	if len(doc.fields) == 1:
		doc.append('fields', {
			'fieldname': 'doctype_to_link',
			'fieldtype': 'Link',
			'in_list_view': 1,
			'label': 'Doctype to Link',
			'options': 'Doctype to Link'
		})

		doc.save()


@frappe.whitelist()
def insert_doctype_with_child_table_record(name):
	if frappe.db.get_all(name, {'title': 'Test Grid Search'}):
		return

	def insert_child(doc, data, barcode, check, rating, duration, date):
		doc.append('child_table_1', {
			'data': data,
			'barcode': barcode,
			'check': check,
			'rating': rating,
			'duration': duration,
			'date': date,
		})

	doc = frappe.new_doc(name)
	doc.title = 'Test Grid Search'
	doc.append('child_table', {'title': 'Test Grid Search'})

	insert_child(doc, 'Data', '09709KJKKH2432', 1, 0.5, 266851, "2022-02-21")
	insert_child(doc, 'Test', '09209KJHKH2432', 1, 0.8, 547877, "2021-05-27")
	insert_child(doc, 'New', '09709KJHYH1132', 0, 0.1, 3, "2019-03-02")
	insert_child(doc, 'Old', '09701KJHKH8750', 0, 0, 127455, "2022-01-11")
	insert_child(doc, 'Alpha', '09204KJHKH2432', 0, 0.6, 364, "2019-12-31")
	insert_child(doc, 'Delta', '09709KSPIO2432', 1, 0.9, 1242000, "2020-04-21")
	insert_child(doc, 'Update', '76989KJLVA2432', 0, 1, 183845, "2022-02-10")
	insert_child(doc, 'Delete', '29189KLHVA1432', 0, 0, 365647, "2021-05-07")
	insert_child(doc, 'Make', '09689KJHAA2431', 0, 0.3, 24, "2020-11-11")
	insert_child(doc, 'Create', '09709KLKKH2432', 1, 0.3, 264851, "2021-02-21")
	insert_child(doc, 'Group', '09209KJLKH2432', 1, 0.8, 537877, "2020-03-15")
	insert_child(doc, 'Slide', '01909KJHYH1132', 0, 0.5, 9, "2018-03-02")
	insert_child(doc, 'Drop', '09701KJHKH8750', 1, 0, 127255, "2018-01-01")
	insert_child(doc, 'Beta', '09204QJHKN2432', 0, 0.6, 354, "2017-12-30")
	insert_child(doc, 'Flag', '09709KXPIP2432', 1, 0, 1241000, "2021-04-21")
	insert_child(doc, 'Upgrade', '75989ZJLVA2432', 0.8, 1, 183645, "2020-08-13")
	insert_child(doc, 'Down', '28189KLHRA1432', 1, 0, 362647, "2020-06-17")
	insert_child(doc, 'Note', '09689DJHAA2431', 0, 0.1, 29, "2021-09-11")
	insert_child(doc, 'Click', '08189DJHAA2431', 1, 0.3, 209, "2020-07-04")
	insert_child(doc, 'Drag', '08189DIHAA2981', 0, 0.7, 342628, "2022-05-04")

	doc.insert()
