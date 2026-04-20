import os
import sys

import click

import frappe
from frappe.database.db_manager import DbManager


def setup_database():
	db_user = frappe.conf.db_user
	db_name = frappe.local.conf.db_name
	# dbman = DbManager(root_conn)
	print((db_user, db_name))
