import frappe

def execute():
	frappe.db.sql("alter table tabSessions add column `device` varchar(255) default 'desktop'")
