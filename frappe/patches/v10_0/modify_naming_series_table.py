"""
<<<<<<< HEAD
    Modify the Integer 10 Digits Value to BigInt 20 Digit value
    to generate long Naming Series

"""
=======
Modify the Integer 10 Digits Value to BigInt 20 Digit value
to generate long Naming Series

"""

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
import frappe


def execute():
	frappe.db.sql(""" ALTER TABLE `tabSeries` MODIFY current BIGINT """)
