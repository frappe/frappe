# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

import frappe
import getpass
from frappe.utils.password import update_password

def before_install():
	frappe.reload_doc("core", "doctype", "docfield")
	frappe.reload_doc("core", "doctype", "docperm")
	frappe.reload_doc("core", "doctype", "doctype")

def after_install():
	# reset installed apps for re-install
	frappe.db.set_global("installed_apps", '["frappe"]')

	install_basic_docs()

	from frappe.core.doctype.file.file import make_home_folder
	make_home_folder()

	import_country_and_currency()

	from frappe.core.doctype.language.language import sync_languages
	sync_languages()

	# save default print setting
	print_settings = frappe.get_doc("Print Settings")
	print_settings.save()

	# all roles to admin
	frappe.get_doc("User", "Administrator").add_roles(*frappe.db.sql_list("""select name from tabRole"""))

	# update admin password
	update_password("Administrator", get_admin_password())

	if not frappe.conf.skip_setup_wizard:
		frappe.db.set_default('desktop:home_page', 'setup-wizard')

	# clear test log
	with open(frappe.get_site_path('.test_log'), 'w') as f:
		f.write('')

	frappe.db.commit()

def install_basic_docs():
	# core users / roles
	install_docs = [
		{'doctype':'User', 'name':'Administrator', 'first_name':'Administrator',
			'email':'admin@example.com', 'enabled':1, "is_admin": 1,
			'roles': [{'role': 'Administrator'}]
		},
		{'doctype':'User', 'name':'Guest', 'first_name':'Guest',
			'email':'guest@example.com', 'enabled':1, "is_guest": 1,
			'roles': [{'role': 'Guest'}]
		},
		{'doctype': "Role", "role_name": "Report Manager"},
		{'doctype': "Role", "role_name": "Translator"},
		{'doctype': "Workflow State", "workflow_state_name": "Pending",
			"icon": "question-sign", "style": ""},
		{'doctype': "Workflow State", "workflow_state_name": "Approved",
			"icon": "ok-sign", "style": "Success"},
		{'doctype': "Workflow State", "workflow_state_name": "Rejected",
			"icon": "remove", "style": "Danger"},
		{'doctype': "Workflow Action Master", "workflow_action_name": "Approve"},
		{'doctype': "Workflow Action Master", "workflow_action_name": "Reject"},
		{'doctype': "Workflow Action Master", "workflow_action_name": "Review"},
		{'doctype': "Email Domain", "domain_name":"example.com", "email_id": "account@example.com", "password": "pass", "email_server": "imap.example.com","use_imap": 1, "smtp_server": "smtp.example.com"},
		{'doctype': "Email Account", "domain":"example.com", "email_id": "notifications@example.com", "default_outgoing": 1},
		{'doctype': "Email Account", "domain":"example.com", "email_id": "replies@example.com", "default_incoming": 1}
	]

	for d in install_docs:
		try:
			frappe.get_doc(d).insert()
		except frappe.NameError:
			pass

def get_admin_password():
	def ask_admin_password():
		admin_password = getpass.getpass("Set Administrator password: ")
		admin_password2 = getpass.getpass("Re-enter Administrator password: ")
		if not admin_password == admin_password2:
			print("\nPasswords do not match")
			return ask_admin_password()
		return admin_password

	admin_password = frappe.conf.get("admin_password")
	if not admin_password:
		return ask_admin_password()
	return admin_password


def before_tests():
	if len(frappe.get_installed_apps()) > 1:
		# don't run before tests if any other app is installed
		return

	frappe.db.sql("delete from `tabCustom Field`")
	frappe.db.sql("delete from `tabEvent`")
	frappe.db.commit()
	frappe.clear_cache()

	# complete setup if missing
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
	if not int(frappe.db.get_single_value('System Settings', 'setup_complete') or 0):
		setup_complete({
			"language"			:"English",
			"email"				:"test@erpnext.com",
			"full_name"			:"Test User",
			"password"			:"test",
			"country"			:"United States",
			"timezone"			:"America/New_York",
			"currency"			:"USD"
		})

	frappe.db.commit()
	frappe.clear_cache()

def import_country_and_currency():
	from frappe.geo.country_info import get_all
	from frappe.utils import update_progress_bar

	data = get_all()

	for i, name in enumerate(data):
		update_progress_bar("Updating country info", i, len(data))
		country = frappe._dict(data[name])
		add_country_and_currency(name, country)

	print("")

	# enable frequently used currencies
	for currency in ("INR", "USD", "GBP", "EUR", "AED", "AUD", "JPY", "CNY", "CHF"):
		frappe.db.set_value("Currency", currency, "enabled", 1)

def add_country_and_currency(name, country):
	if not frappe.db.exists("Country", name):
		frappe.get_doc({
			"doctype": "Country",
			"country_name": name,
			"code": country.code,
			"date_format": country.date_format or "dd-mm-yyyy",
			"time_zones": "\n".join(country.timezones or []),
			"docstatus": 0
		}).db_insert()

	if country.currency and not frappe.db.exists("Currency", country.currency):
		frappe.get_doc({
			"doctype": "Currency",
			"currency_name": country.currency,
			"fraction": country.currency_fraction,
			"symbol": country.currency_symbol,
			"fraction_units": country.currency_fraction_units,
			"smallest_currency_fraction_value": country.smallest_currency_fraction_value,
			"number_format": country.number_format,
			"docstatus": 0
		}).db_insert()
