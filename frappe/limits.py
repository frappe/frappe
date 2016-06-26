from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, flt, cint, get_fullname
from frappe.installer import update_site_config
from frappe.utils.data import formatdate
from frappe.utils.user import get_enabled_system_users
import os, subprocess, urlparse, urllib

class SiteExpiredError(frappe.ValidationError):
	pass

EXPIRY_WARNING_DAYS = 10

def check_if_expired():
	"""check if account is expired. If expired, do not allow login"""
	if not has_expired():
		return
	# if expired, stop user from logging in
	expires_on = formatdate(get_limits().get("expiry"))
	support_email = get_limits().get("support_email") or _("your provider")

	frappe.throw(_("""Your subscription expired on {0}.
		To extend please send an email to {1}""").format(expires_on, support_email),
		SiteExpiredError)

def has_expired():
	if frappe.session.user=="Administrator":
		return False

	expires_on = get_limits().expiry
	if not expires_on:
		return False

	if now_datetime().date() <= getdate(expires_on):
		return False

	return True

def get_expiry_message():
	if "System Manager" not in frappe.get_roles():
		return ""

	if not get_limits().get("expiry"):
		return ""

	expires_on = getdate(get_limits().get("expiry"))
	today = now_datetime().date()

	message = ""
	if today > expires_on:
		message = _("Your subscription has expired")
	else:
		days_to_expiry = (expires_on - today).days

		if days_to_expiry == 0:
			message = _("Your subscription will expire today")

		elif days_to_expiry == 1:
			message = _("Your subscription will expire tomorrow")

		elif days_to_expiry <= EXPIRY_WARNING_DAYS:
			message = _("Your subscription will expire on") + " " + formatdate(expires_on)

	return message

@frappe.whitelist()
def get_usage_info():
	'''Get data to show for Usage Info'''
	# imported here to prevent circular import
	from frappe.email.queue import get_emails_sent_this_month

	limits = get_limits()
	if not (limits and any([limits.users, limits.space, limits.emails, limits.expiry])):
		# no limits!
		return

	limits.space = limits.space * 1024.0 # to MB
	if not limits.space_usage:
		# hack! to show some progress
		limits.space_usage = {
			'database_size': 26,
			'files_size': 1,
			'backup_size': 1,
			'total': 28
		}

	usage_info = frappe._dict({
		'limits': limits,
		'enabled_users': len(get_enabled_system_users()),
		'emails_sent': get_emails_sent_this_month(),
		'space_usage': limits.space_usage['total'],
	})

	if limits.expiry:
		usage_info['expires_on'] = formatdate(limits.expiry)
		usage_info['days_to_expiry'] = (getdate(limits.expiry) - getdate()).days

	if limits.upgrade_link:
		usage_info['upgrade_link'] = get_upgrade_link(limits.upgrade_link)

	return usage_info

def get_upgrade_link(upgrade_link):
	parts = urlparse.urlsplit(upgrade_link)
	params = dict(urlparse.parse_qsl(parts.query))
	params.update({
		'site': frappe.local.site,
		'email': frappe.session.user,
		'full_name': get_fullname()
	})

	query = urllib.urlencode(params, doseq=True)
	url = urlparse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
	return url

def get_limits():
	'''
		"limits": {
			"users": 1,
			"space": 0.5, # in GB
			"emails": 1000 # per month
			"expiry": "2099-12-31"
		}
	'''
	return frappe._dict(frappe.local.conf.limits or {})

def update_limits(limits_dict):
	'''Add/Update limit in site_config'''
	limits = get_limits()
	limits.update(limits_dict)
	update_site_config("limits", limits, validate=False)
	frappe.conf.limits = limits

def clear_limit(key):
	'''Remove a limit option from site_config'''
	limits = get_limits()
	if key in limits:
		del limits[key]

	update_site_config("limits", limits, validate=False)
	frappe.conf.limits = limits

def validate_space_limit(file_size):
	"""Stop from writing file if max space limit is reached"""
	from frappe.utils.file_manager import MaxFileSizeReachedError

	limits = get_limits()
	if not limits.space:
		return

	# to MB
	space_limit = flt(limits.space * 1024.0, 2)

	# in MB
	usage = frappe._dict(limits.space_usage or {})
	if not usage:
		# first time
		usage = frappe._dict(update_space_usage())

	file_size = file_size / (1024.0 ** 2)

	if flt(flt(usage.total) + file_size, 2) > space_limit:
		# Stop from attaching file
		frappe.throw(_("You have exceeded the max space of {0} for your plan. {1}.").format(
			"<b>{0}MB</b>".format(cint(space_limit)) if (space_limit < 1024) else "<b>{0}GB</b>".format(limits.space),
			'<a href="#usage-info">{0}</a>'.format(_("Click here to check your usage or upgrade to a higher plan"))),
			MaxFileSizeReachedError)

	# update files size in frappe subscription
	usage.files_size = flt(usage.files_size) + file_size
	update_limits({ 'space_usage': usage })

def update_space_usage():
	# public and private files
	files_size = get_folder_size(frappe.get_site_path("public", "files"))
	files_size += get_folder_size(frappe.get_site_path("private", "files"))

	backup_size = get_folder_size(frappe.get_site_path("private", "backups"))
	database_size = get_database_size()

	usage = {
		'files_size': flt(files_size, 2),
		'backup_size': flt(backup_size, 2),
		'database_size': flt(database_size, 2),
		'total': flt(flt(files_size) + flt(backup_size) + flt(database_size), 2)
	}

	update_limits({ 'space_usage': usage })

	return usage

def get_folder_size(path):
	'''Returns folder size in MB if it exists'''
	if os.path.exists(path):
		return flt(subprocess.check_output(['du', '-ms', path]).split()[0], 2)

def get_database_size():
	'''Returns approximate database size in MB'''
	db_name = frappe.conf.db_name

	# This query will get the database size in MB
	db_size = frappe.db.sql('''
		SELECT table_schema "database_name", sum( data_length + index_length ) / 1024 / 1024 "database_size"
		FROM information_schema.TABLES WHERE table_schema = %s GROUP BY table_schema''', db_name, as_dict=True)

	return flt(db_size[0].get('database_size'), 2)
