# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals

import frappe, json, os
from frappe.utils import strip, cint
from frappe.translate import (set_default_language, get_dict, send_translations)
from frappe.geo.country_info import get_country_info
from frappe.utils.file_manager import save_file
from frappe.utils.password import update_password
from werkzeug.useragents import UserAgent
from . import install_fixtures
from six import string_types

@frappe.whitelist()
def setup_complete(args):
	"""Calls hooks for `setup_wizard_complete`, sets home page as `desktop`
	and clears cache. If wizard breaks, calls `setup_wizard_exception` hook"""

	if cint(frappe.db.get_single_value('System Settings', 'setup_complete')):
		# do not throw an exception if setup is already complete
		# let the user continue to desk
		return
		#frappe.throw(_('Setup already complete'))

	args = process_args(args)

	try:
		if args.language and args.language != "english":
			set_default_language(get_language_code(args.lang))

		frappe.clear_cache()

		# update system settings
		update_system_settings(args)
		update_user_name(args)

		for method in frappe.get_hooks("setup_wizard_complete"):
			frappe.get_attr(method)(args)

		disable_future_access()

		frappe.db.commit()
		frappe.clear_cache()
	except:
		frappe.db.rollback()
		if args:
			traceback = frappe.get_traceback()
			for hook in frappe.get_hooks("setup_wizard_exception"):
				frappe.get_attr(hook)(traceback, args)

		raise

	else:
		for hook in frappe.get_hooks("setup_wizard_success"):
			frappe.get_attr(hook)(args)
		install_fixtures.install()


def update_system_settings(args):
	number_format = get_country_info(args.get("country")).get("number_format", "#,###.##")

	# replace these as float number formats, as they have 0 precision
	# and are currency number formats and not for floats
	if number_format=="#.###":
		number_format = "#.###,##"
	elif number_format=="#,###":
		number_format = "#,###.##"

	system_settings = frappe.get_doc("System Settings", "System Settings")
	system_settings.update({
		"country": args.get("country"),
		"language": get_language_code(args.get("language")),
		"time_zone": args.get("timezone"),
		"float_precision": 3,
		'date_format': frappe.db.get_value("Country", args.get("country"), "date_format"),
		'number_format': number_format,
		'enable_scheduler': 1 if not frappe.flags.in_test else 0,
		'backup_limit': 3 # Default for downloadable backups
	})
	system_settings.save()

def update_user_name(args):
	first_name, last_name = args.get('full_name'), ''
	if ' ' in first_name:
		first_name, last_name = first_name.split(' ', 1)

	if args.get("email"):
		if frappe.db.exists('User', args.get('email')):
			# running again
			return


		args['name'] = args.get("email")

		_mute_emails, frappe.flags.mute_emails = frappe.flags.mute_emails, True
		doc = frappe.get_doc({
			"doctype":"User",
			"email": args.get("email"),
			"first_name": first_name,
			"last_name": last_name
		})
		doc.flags.no_welcome_mail = True
		doc.insert()
		frappe.flags.mute_emails = _mute_emails
		update_password(args.get("email"), args.get("password"))

	else:
		args.update({
			"name": frappe.session.user,
			"first_name": first_name,
			"last_name": last_name
		})

		frappe.db.sql("""update `tabUser` SET first_name=%(first_name)s,
			last_name=%(last_name)s WHERE name=%(name)s""", args)

	if args.get("attach_user"):
		attach_user = args.get("attach_user").split(",")
		if len(attach_user)==3:
			filename, filetype, content = attach_user
			fileurl = save_file(filename, content, "User", args.get("name"), decode=True).file_url
			frappe.db.set_value("User", args.get("name"), "user_image", fileurl)

	add_all_roles_to(args.get("name"))

def process_args(args):
	if not args:
		args = frappe.local.form_dict
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)

	# strip the whitespace
	for key, value in args.items():
		if isinstance(value, string_types):
			args[key] = strip(value)

	return args

def add_all_roles_to(name):
	user = frappe.get_doc("User", name)
	for role in frappe.db.sql("""select name from tabRole"""):
		if role[0] not in ["Administrator", "Guest", "All", "Customer", "Supplier", "Partner", "Employee"]:
			d = user.append("roles")
			d.role = role[0]
	user.save()

def disable_future_access():
	frappe.db.set_default('desktop:home_page', 'desktop')
	frappe.db.set_value('System Settings', 'System Settings', 'setup_complete', 1)
	frappe.db.set_value('System Settings', 'System Settings', 'is_first_startup', 1)

	if not frappe.flags.in_test:
		# remove all roles and add 'Administrator' to prevent future access
		page = frappe.get_doc('Page', 'setup-wizard')
		page.roles = []
		page.append('roles', {'role': 'Administrator'})
		page.flags.do_not_update_json = True
		page.flags.ignore_permissions = True
		page.save()

@frappe.whitelist()
def load_messages(language):
	"""Load translation messages for given language from all `setup_wizard_requires`
	javascript files"""
	frappe.clear_cache()
	set_default_language(get_language_code(language))
	m = get_dict("page", "setup-wizard")

	for path in frappe.get_hooks("setup_wizard_requires"):
		# common folder `assets` served from `sites/`
		js_file_path = os.path.abspath(frappe.get_site_path("..", *path.strip("/").split("/")))
		m.update(get_dict("jsfile", js_file_path))

	m.update(get_dict("boot"))
	send_translations(m)
	return frappe.local.lang

@frappe.whitelist()
def load_languages():
	language_codes = frappe.db.sql('select language_code, language_name from tabLanguage order by name', as_dict=True)
	codes_to_names = {}
	for d in language_codes:
		codes_to_names[d.language_code] = d.language_name
	return {
		"default_language": frappe.db.get_value('Language', frappe.local.lang, 'language_name') or frappe.local.lang,
		"languages": sorted(frappe.db.sql_list('select language_name from tabLanguage order by name')),
		"codes_to_names": codes_to_names
	}

@frappe.whitelist()
def load_country():
	from frappe.sessions import get_geo_ip_country
	return get_geo_ip_country(frappe.local.request_ip) if frappe.local.request_ip else None

@frappe.whitelist()
def load_user_details():
	return {
		"full_name": frappe.cache().hget("full_name", "signup"),
		"email": frappe.cache().hget("email", "signup")
	}

@frappe.whitelist()
def reset_is_first_startup():
	frappe.db.set_value('System Settings', 'System Settings', 'is_first_startup', 0)

def prettify_args(args):
	# remove attachments
	for key, val in args.items():
		if isinstance(val, string_types) and "data:image" in val:
			filename = val.split("data:image", 1)[0].strip(", ")
			size = round((len(val) * 3 / 4) / 1048576.0, 2)
			args[key] = "Image Attached: '{0}' of size {1} MB".format(filename, size)

	pretty_args = []
	for key in sorted(args):
		pretty_args.append("{} = {}".format(key, args[key]))
	return pretty_args

def email_setup_wizard_exception(traceback, args):
	if not frappe.local.conf.setup_wizard_exception_email:
		return

	pretty_args = prettify_args(args)

	if frappe.local.request:
		user_agent = UserAgent(frappe.local.request.headers.get('User-Agent', ''))

	else:
		user_agent = frappe._dict()

	message = """
#### Basic Information

- **Site:** {site}
- **User:** {user}
- **Browser:** {user_agent.platform} {user_agent.browser} version: {user_agent.version} language: {user_agent.language}
- **Browser Languages**: `{accept_languages}`

---

#### Traceback

<pre>{traceback}</pre>

---

#### Setup Wizard Arguments

<pre>{args}</pre>

---

#### Request Headers

<pre>{headers}</pre>""".format(
		site=frappe.local.site,
		traceback=traceback,
		args="\n".join(pretty_args),
		user=frappe.session.user,
		user_agent=user_agent,
		headers=frappe.local.request.headers,
		accept_languages=", ".join(frappe.local.request.accept_languages.values()))

	frappe.sendmail(recipients=frappe.local.conf.setup_wizard_exception_email,
		sender=frappe.session.user,
		subject="Exception in Setup Wizard - {}".format(frappe.local.site),
		message=message,
		delayed=False)

def get_language_code(lang):
	return frappe.db.get_value('Language', {'language_name':lang})


def enable_twofactor_all_roles():
	all_role = frappe.get_doc('Role',{'role_name':'All'})
	all_role.two_factor_auth = True
	all_role.save(ignore_permissions=True)

