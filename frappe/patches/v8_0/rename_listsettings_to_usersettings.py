import frappe, json

def execute():
	for us in frappe.db.sql('''select user, doctype, data from __ListSettings''', as_dict=True):
		try:
			data = json.loads(us.data)
		except:
			continue
		
		if 'List' in data:
			continue

		if 'limit' in data:
			data['page_length'] = data['limit']
			del data['limit']

		new_data = dict(List=data)
		new_data = json.dumps(new_data)

		frappe.db.sql('''update __ListSettings
			set data=%(new_data)s
			where user=%(user)s
			and doctype=%(doctype)s''',
			{'new_data': new_data, 'user': us.user, 'doctype': us.doctype})

	frappe.db.sql("RENAME TABLE __ListSettings to __UserSettings")