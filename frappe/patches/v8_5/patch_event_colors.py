from __future__ import unicode_literals
import frappe

def execute():

	if not frappe.db.sql("SHOW COLUMNS FROM `tabEvent` LIKE 'color';"):
		return

	colors = ['red', 'green', 'blue', 'yellow', 'skyblue', 'orange']
	hex_colors = ['#ffc4c4', '#cef6d1', '#d2d2ff', '#fffacd', '#d2f1ff', '#ffd2c2']

	def get_hex_for_color(color):
		index = colors.index(color)
		return hex_colors[index]

	query = '''
		update tabEvent
		set color='{hex}'
		where color='{color}'
	'''

	for color in colors:
		frappe.db.sql(query.format(color=color, hex=get_hex_for_color(color)))

	frappe.db.commit()
