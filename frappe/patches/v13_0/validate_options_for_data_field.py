# Copyright (c) 2022, Frappe and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe.model import data_field_options


def execute():

    for field in frappe.get_all('Custom Field',
                            fields = ['name', 'options'],
                            filters = {
                                'fieldtype': 'Data',
                                'options': ['is', 'set']
                            }):

        if field.options not in data_field_options:
            custom_field = frappe.qb.DocType('Custom Field')
            frappe.qb.update(
                custom_field
            ).set(
                custom_field.options, None
            ).where(
                custom_field.name == field.name
            ).run()
