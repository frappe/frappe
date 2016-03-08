import frappe, json

def execute():
	for ps in frappe.get_all('Property Setter', filters={'property': '_idx'},
		fields = ['doc_type', 'value']):
		custom_fields = frappe.get_all('Custom Field',
			filters = {'dt': ps.doc_type}, fields=['name', 'fieldname'])

		if custom_fields:
			for custom_field in custom_fields:
				_idx = json.loads(ps.value)
				prev_fieldname = ""
				for fieldname in _idx:
					if fieldname == custom_field.fieldname:
						frappe.db.set_value('Custom Field', custom_field.name, 'insert_after', prev_fieldname)
						break
					prev_fieldname = fieldname

