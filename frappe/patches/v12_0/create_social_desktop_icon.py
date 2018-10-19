import frappe

def execute():
	icon_obj = {
		'doctype': 'Desktop Icon',
		'module_name': 'Social',
		'label': 'Social',
		'standard': 1,
		'idx': 15,
		'type': 'link',
		'color': '#FF4136',
		'link': 'social/home',
		'icon': 'octicon octicon-heart'
	}

	if not frappe.db.exists(icon_obj):
		icon = frappe.get_doc(icon_obj)
		icon.insert()
		frappe.db.commit()