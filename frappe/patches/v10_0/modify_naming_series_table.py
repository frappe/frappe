
'''
    Modify the Integer 10 Digits Value to BigInt 20 Digit value
    to generate long Naming Series

'''
import frappe
import re
def execute():
        
        fields = frappe.db.sql("""DESC `tabSeries` """, as_dict=True)
        for field in fields:
                if field.get("Field") == "current" and re.sub("[0-9()]", "", field.get("Type"))=="int":
                        frappe.db.sql(""" ALTER TABLE `tabSeries` MODIFY current BIGINT """)


