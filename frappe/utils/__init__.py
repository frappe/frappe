# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# util __init__.py

from __future__ import unicode_literals
from werkzeug.test import Client
import os, sys, re, urllib
import frappe
import requests

# utility functions like cint, int, flt, etc.
from frappe.utils.data import *

default_fields = ['doctype', 'name', 'owner', 'creation', 'modified', 'modified_by',
	'parent', 'parentfield', 'parenttype', 'idx', 'docstatus']

# used in import_docs.py
# TODO: deprecate it
def getCSVelement(v):
	"""
		 Returns the CSV value of `v`, For example:

		 * apple becomes "apple"
		 * hi"there becomes "hi""there"
	"""
	v = cstr(v)
	if not v: return ''
	if (',' in v) or ('\n' in v) or ('"' in v):
		if '"' in v: v = v.replace('"', '""')
		return '"'+v+'"'
	else: return v or ''

def get_fullname(user=None):
	"""get the full name (first name + last name) of the user from User"""
	if not user:
		user = frappe.session.user

	if not hasattr(frappe.local, "fullnames"):
		frappe.local.fullnames = {}

	if not frappe.local.fullnames.get(user):
		p = frappe.db.get_value("User", user, ["first_name", "last_name"], as_dict=True)
		if p:
			frappe.local.fullnames[user] = " ".join(filter(None,
				[p.get('first_name'), p.get('last_name')])) or user
		else:
			frappe.local.fullnames[user] = user

	return frappe.local.fullnames.get(user)

def get_formatted_email(user):
	"""get email id of user formatted as: John Doe <johndoe@example.com>"""
	if user == "Administrator":
		return user
	from email.utils import formataddr
	fullname = get_fullname(user)
	return formataddr((fullname, user))

def extract_email_id(email):
	"""fetch only the email part of the email id"""
	from email.utils import parseaddr
	fullname, email_id = parseaddr(email)
	if isinstance(email_id, basestring) and not isinstance(email_id, unicode):
		email_id = email_id.decode("utf-8", "ignore")
	return email_id

def validate_email_add(email_str, throw=False):
	"""Validates the email string"""
	if email_str and " " in email_str and "<" not in email_str:
		# example: "test@example.com test2@example.com" will return "test@example.comtest2" after parseaddr!!!
		return False

	email = extract_email_id(email_str)
	match = re.match("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", email.lower())

	if not match:
		if throw:
			frappe.throw(frappe._("{0} is not a valid email id").format(email),
				frappe.InvalidEmailAddressError)
		else:
			return False

	matched = match.group(0)

	if match:
		match = matched==email.lower()

	if not match and throw:
		frappe.throw(frappe._("{0} is not a valid email id").format(email),
			frappe.InvalidEmailAddressError)

	return matched

def split_emails(txt):
	email_list = []
	for email in re.split(''',(?=(?:[^"]|"[^"]*")*$)''', cstr(txt)):
		email = strip(cstr(email))
		if email:
			email_list.append(email)

	return email_list

def random_string(length):
	"""generate a random string"""
	import string
	from random import choice
	return ''.join([choice(string.letters + string.digits) for i in range(length)])

def get_gravatar(email):
	import md5
	return "https://secure.gravatar.com/avatar/{hash}?d=retro".format(hash=md5.md5(email).hexdigest())

def get_traceback():
	"""
		 Returns the traceback of the Exception
	"""
	import traceback
	exc_type, value, tb = sys.exc_info()

	trace_list = traceback.format_tb(tb, None) + \
		traceback.format_exception_only(exc_type, value)
	body = "Traceback (innermost last):\n" + "%-20s %s" % \
		(unicode((b"").join(trace_list[:-1]), 'utf-8'), unicode(trace_list[-1], 'utf-8'))

	if frappe.logger:
		frappe.logger.error('Db:'+(frappe.db and frappe.db.cur_db_name or '') \
			+ ' - ' + body)

	return body

def log(event, details):
	frappe.logger.info(details)

def dict_to_str(args, sep='&'):
	"""
	Converts a dictionary to URL
	"""
	t = []
	for k in args.keys():
		t.append(str(k)+'='+urllib.quote(str(args[k] or '')))
	return sep.join(t)

# Get Defaults
# ==============================================================================

def get_defaults(key=None):
	"""
	Get dictionary of default values from the defaults, or a value if key is passed
	"""
	return frappe.db.get_defaults(key)

def set_default(key, val):
	"""
	Set / add a default value to defaults`
	"""
	return frappe.db.set_default(key, val)

def remove_blanks(d):
	"""
		Returns d with empty ('' or None) values stripped
	"""
	empty_keys = []
	for key in d:
		if d[key]=='' or d[key]==None:
			# del d[key] raises runtime exception, using a workaround
			empty_keys.append(key)
	for key in empty_keys:
		del d[key]

	return d

def strip_html_tags(text):
	"""Remove html tags from text"""
	return re.sub("\<[^>]*\>", "", text)

def pprint_dict(d, level=1, no_blanks=True):
	"""
		Pretty print a dictionary with indents
	"""
	if no_blanks:
		remove_blanks(d)

	# make indent
	indent, ret = '', ''
	for i in range(0,level): indent += '\t'

	# add lines
	comment, lines = '', []
	kl = d.keys()
	kl.sort()

	# make lines
	for key in kl:
		if key != '##comment':
			tmp = {key: d[key]}
			lines.append(indent + str(tmp)[1:-1] )

	# add comment string
	if '##comment' in kl:
		ret = ('\n' + indent) + '# ' + d['##comment'] + '\n'

	# open
	ret += indent + '{\n'

	# lines
	ret += indent + ',\n\t'.join(lines)

	# close
	ret += '\n' + indent + '}'

	return ret

def get_common(d1,d2):
	"""
		returns (list of keys) the common part of two dicts
	"""
	return [p for p in d1 if p in d2 and d1[p]==d2[p]]

def get_common_dict(d1, d2):
	"""
		return common dictionary of d1 and d2
	"""
	ret = {}
	for key in d1:
		if key in d2 and d2[key]==d1[key]:
			ret[key] = d1[key]
	return ret

def get_diff_dict(d1, d2):
	"""
		return common dictionary of d1 and d2
	"""
	diff_keys = set(d2.keys()).difference(set(d1.keys()))

	ret = {}
	for d in diff_keys: ret[d] = d2[d]
	return ret


def get_file_timestamp(fn):
	"""
		Returns timestamp of the given file
	"""
	from frappe.utils import cint

	try:
		return str(cint(os.stat(fn).st_mtime))
	except OSError, e:
		if e.args[0]!=2:
			raise
		else:
			return None

# to be deprecated
def make_esc(esc_chars):
	"""
		Function generator for Escaping special characters
	"""
	return lambda s: ''.join(['\\' + c if c in esc_chars else c for c in s])

# esc / unescape characters -- used for command line
def esc(s, esc_chars):
	"""
		Escape special characters
	"""
	if not s:
		return ""
	for c in esc_chars:
		esc_str = '\\' + c
		s = s.replace(c, esc_str)
	return s

def unesc(s, esc_chars):
	"""
		UnEscape special characters
	"""
	for c in esc_chars:
		esc_str = '\\' + c
		s = s.replace(esc_str, c)
	return s

def execute_in_shell(cmd, verbose=0):
	# using Popen instead of os.system - as recommended by python docs
	from subprocess import Popen
	import tempfile

	with tempfile.TemporaryFile() as stdout:
		with tempfile.TemporaryFile() as stderr:
			p = Popen(cmd, shell=True, stdout=stdout, stderr=stderr)
			p.wait()

			stdout.seek(0)
			out = stdout.read()

			stderr.seek(0)
			err = stderr.read()

	if verbose:
		if err: print err
		if out: print out

	return err, out

def get_path(*path, **kwargs):
	base = kwargs.get('base')
	if not base:
		base = frappe.local.site_path
	return os.path.join(base, *path)

def get_site_base_path(sites_dir=None, hostname=None):
	return frappe.local.site_path

def get_site_path(*path):
	return get_path(base=get_site_base_path(), *path)

def get_files_path(*path):
	return get_site_path("public", "files", *path)

def get_bench_path():
	return os.path.realpath(os.path.join(os.path.dirname(frappe.__file__), '..', '..', '..'))

def get_backups_path():
	return get_site_path("private", "backups")

def get_request_site_address(full_address=False):
	return get_url(full_address=full_address)

def encode_dict(d, encoding="utf-8"):
	for key in d:
		if isinstance(d[key], basestring) and isinstance(d[key], unicode):
			d[key] = d[key].encode(encoding)

	return d

def decode_dict(d, encoding="utf-8"):
	for key in d:
		if isinstance(d[key], basestring) and not isinstance(d[key], unicode):
			d[key] = d[key].decode(encoding, "ignore")

	return d

def get_site_name(hostname):
	return hostname.split(':')[0]

def get_disk_usage():
	"""get disk usage of files folder"""
	files_path = get_files_path()
	if not os.path.exists(files_path):
		return 0
	err, out = execute_in_shell("du -hsm {files_path}".format(files_path=files_path))
	return cint(out.split("\n")[-2].split("\t")[0])

def touch_file(path):
	with open(path, 'a'):
		os.utime(path, None)
	return True

def get_test_client():
	from frappe.app import application
	return Client(application)

def get_hook_method(hook_name, fallback=None):
	method = (frappe.get_hooks().get(hook_name))
	if method:
		method = frappe.get_attr(method[0])
		return method
	if fallback:
		return fallback

def call_hook_method(hook, *args, **kwargs):
	for method_name in frappe.get_hooks(hook):
		frappe.get_attr(method_name)(*args, **kwargs)

def update_progress_bar(txt, i, l):
	lt = len(txt)
	if lt < 36:
		txt = txt + " "*(36-lt)
	complete = int(float(i+1) / l * 40)
	sys.stdout.write("\r{0}: [{1}{2}]".format(txt, "="*complete, " "*(40-complete)))
	sys.stdout.flush()

def get_html_format(print_path):
	html_format = None
	if os.path.exists(print_path):
		with open(print_path, "r") as f:
			html_format = f.read()

		for include_directive, path in re.findall("""({% include ['"]([^'"]*)['"] %})""", html_format):
			for app_name in frappe.get_installed_apps():
				include_path = frappe.get_app_path(app_name, *path.split(os.path.sep))
				if os.path.exists(include_path):
					with open(include_path, "r") as f:
						html_format = html_format.replace(include_directive, f.read())
					break

	return html_format

def is_markdown(text):
	if "<!-- markdown -->" in text:
		return True
	elif "<!-- html -->" in text:
		return False
	else:
		return not re.search("<p[\s]*>|<br[\s]*>", text)

def get_sites(sites_path=None):
	import os
	if not sites_path:
		sites_path = '.'
	return [site for site in os.listdir(sites_path)
			if os.path.isdir(os.path.join(sites_path, site))
				and not site in ('assets',)]


def get_request_session(max_retries=3):
	from requests.packages.urllib3.util import Retry
	session = requests.Session()
	session.mount("http://", requests.adapters.HTTPAdapter(max_retries=Retry(total=5, status_forcelist=[500])))
	session.mount("https://", requests.adapters.HTTPAdapter(max_retries=Retry(total=5, status_forcelist=[500])))
	return session

