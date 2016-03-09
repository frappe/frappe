import frappe, json

def execute():
	for ps in frappe.get_all('Property Setter', filters={'property': '_idx'},
		fields = ['doc_type', 'value']):
		custom_fields = frappe.get_all('Custom Field',
			filters = {'dt': ps.doc_type}, fields=['name', 'fieldname'])

		if custom_fields:
			_idx = json.loads(ps.value)

			for custom_field in custom_fields:
				if custom_field.fieldname in _idx:
					custom_field_idx = _idx.index(custom_field.fieldname)
					if custom_field_idx == 0:
						prev_fieldname = ""

					else:
						prev_fieldname = _idx[custom_field_idx - 1]

				else:
					prev_fieldname = _idx[-1]
					custom_field_idx = len(_idx)

				frappe.db.set_value('Custom Field', custom_field.name, 'insert_after', prev_fieldname)
				frappe.db.set_value('Custom Field', custom_field.name, 'idx', custom_field_idx)
