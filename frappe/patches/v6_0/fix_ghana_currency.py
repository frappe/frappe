from __future__ import unicode_literals

def execute():
	from frappe.geo.country_info import get_all
	import frappe.utils.install

	countries = get_all()
	frappe.utils.install.add_country_and_currency("Ghana", frappe._dict(countries["Ghana"]))
