# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from __future__ import print_function, unicode_literals

import functools
import hashlib
import io
import json
import os
import re
import sys
import traceback
import typing
from collections.abc import MutableMapping, MutableSequence, Sequence
from email.header import decode_header, make_header
from email.utils import formataddr, parseaddr
from gzip import GzipFile
from typing import Generator, Iterable
from urllib.parse import quote, urlparse

from werkzeug.test import Client

import frappe

# utility functions like cint, int, flt, etc.
from frappe.utils.data import *
from frappe.utils.html_utils import sanitize_html

default_fields = [
	"doctype",
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"parent",
	"parentfield",
	"parenttype",
	"idx",
	"docstatus",
]


def get_fullname(user=None):
	"""get the full name (first name + last name) of the user from User"""
	if not user:
		user = frappe.session.user

	if not hasattr(frappe.local, "fullnames"):
		frappe.local.fullnames = {}

	if not frappe.local.fullnames.get(user):
		p = frappe.db.get_value("User", user, ["first_name", "last_name"], as_dict=True)
		if p:
			frappe.local.fullnames[user] = (
				" ".join(filter(None, [p.get("first_name"), p.get("last_name")])) or user
			)
		else:
			frappe.local.fullnames[user] = user

	return frappe.local.fullnames.get(user)


def get_email_address(user=None):
	"""get the email address of the user from User"""
	if not user:
		user = frappe.session.user

	return frappe.db.get_value("User", user, "email")


def get_formatted_email(user, mail=None):
	"""get Email Address of user formatted as: `John Doe <johndoe@example.com>`"""
	fullname = get_fullname(user)
	method = get_hook_method("get_sender_details")

	if method:
		sender_name, mail = method()
		# if method exists but sender_name is ""
		fullname = sender_name or fullname

	if not mail:
		mail = get_email_address(user) or validate_email_address(user)

	if not mail:
		return ""
	else:
		return cstr(make_header(decode_header(formataddr((fullname, mail)))))


def extract_email_id(email):
	"""fetch only the email part of the Email Address"""
	email_id = parse_addr(email)[1]
	if email_id and isinstance(email_id, str) and not isinstance(email_id, str):
		email_id = email_id.decode("utf-8", "ignore")
	return email_id


def validate_phone_number(phone_number, throw=False):
	"""Returns True if valid phone number"""
	if not phone_number:
		return False

	phone_number = phone_number.strip()
	match = re.match(r"([0-9\ \+\_\-\,\.\*\#\(\)]){1,20}$", phone_number)

	if not match and throw:
		frappe.throw(
			frappe._("{0} is not a valid Phone Number").format(phone_number), frappe.InvalidPhoneNumberError
		)

	return bool(match)


def validate_name(name, throw=False):
	"""Returns True if the name is valid
	valid names may have unicode and ascii characters, dash, quotes, numbers
	anything else is considered invalid
	"""
	if not name:
		return False

	name = name.strip()
	match = re.match(r"^[\w][\w\'\-]*( \w[\w\'\-]*)*$", name)

	if not match and throw:
		frappe.throw(frappe._("{0} is not a valid Name").format(name), frappe.InvalidNameError)

	return bool(match)


def validate_email_address(email_str, throw=False):
	"""Validates the email string"""
	email = email_str = (email_str or "").strip()

	def _check(e):
		_valid = True
		if not e:
			_valid = False

		if "undisclosed-recipient" in e:
			return False

		elif " " in e and "<" not in e:
			# example: "test@example.com test2@example.com" will return "test@example.comtest2" after parseaddr!!!
			_valid = False

		else:
			email_id = extract_email_id(e)
			match = (
				re.match(
					"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?",
					email_id.lower(),
				)
				if email_id
				else None
			)

			if not match:
				_valid = False
			else:
				matched = match.group(0)
				if match:
					match = matched == email_id.lower()

		if not _valid:
			if throw:
				invalid_email = frappe.utils.escape_html(e)
				frappe.throw(
					frappe._("{0} is not a valid Email Address").format(invalid_email),
					frappe.InvalidEmailAddressError,
				)
			return None
		else:
			return matched

	out = []
	for e in email_str.split(","):
		email = _check(e.strip())
		if email:
			out.append(email)

	return ", ".join(out)


def split_emails(txt):
	email_list = []

	# emails can be separated by comma or newline
	s = re.sub(r"[\t\n\r]", " ", cstr(txt))
	for email in re.split("""[,\\n](?=(?:[^"]|"[^"]*")*$)""", s):
		email = strip(cstr(email))
		if email:
			email_list.append(email)

	return email_list


def validate_url(txt, throw=False, valid_schemes=None):
	"""
	Checks whether `txt` has a valid URL string

	Parameters:
	        throw (`bool`): throws a validationError if URL is not valid
	        valid_schemes (`str` or `list`): if provided checks the given URL's scheme against this

	Returns:
	        bool: if `txt` represents a valid URL
	"""
	url = urlparse(txt)
	is_valid = bool(url.netloc)

	# Handle scheme validation
	if isinstance(valid_schemes, str):
		is_valid = is_valid and (url.scheme == valid_schemes)
	elif isinstance(valid_schemes, (list, tuple, set)):
		is_valid = is_valid and (url.scheme in valid_schemes)

	if not is_valid and throw:
		frappe.throw(frappe._("'{0}' is not a valid URL").format(frappe.bold(txt)))

	return is_valid


def random_string(length):
	"""generate a random string"""
	import string
	from random import choice

	return "".join([choice(string.ascii_letters + string.digits) for i in range(length)])


def has_gravatar(email):
	"""Returns gravatar url if user has set an avatar at gravatar.com"""
	import requests

	if frappe.flags.in_import or frappe.flags.in_install or frappe.flags.in_test:
		# no gravatar if via upload
		# since querying gravatar for every item will be slow
		return ""

	hexdigest = hashlib.md5(frappe.as_unicode(email).encode("utf-8")).hexdigest()

	gravatar_url = "https://secure.gravatar.com/avatar/{hash}?d=404&s=200".format(hash=hexdigest)
	try:
		res = requests.get(gravatar_url)
		if res.status_code == 200:
			return gravatar_url
		else:
			return ""
	except requests.exceptions.ConnectionError:
		return ""


def get_gravatar_url(email):
	return "https://secure.gravatar.com/avatar/{hash}?d=mm&s=200".format(
		hash=hashlib.md5(email.encode("utf-8")).hexdigest()
	)


def get_gravatar(email):
	from frappe.utils.identicon import Identicon

	gravatar_url = has_gravatar(email)

	if not gravatar_url:
		gravatar_url = Identicon(email).base64()

	return gravatar_url


def get_traceback() -> str:
	"""
	Returns the traceback of the Exception
	"""
	exc_type, exc_value, exc_tb = sys.exc_info()

	if not any([exc_type, exc_value, exc_tb]):
		return ""

	trace_list = traceback.format_exception(exc_type, exc_value, exc_tb)
	bench_path = get_bench_path() + "/"

	return "".join(cstr(t) for t in trace_list).replace(bench_path, "")


def log(event, details):
	frappe.logger().info(details)


def dict_to_str(args, sep="&"):
	"""
	Converts a dictionary to URL
	"""
	t = []
	for k in list(args):
		t.append(str(k) + "=" + quote(str(args[k] or "")))
	return sep.join(t)


def list_to_str(seq, sep=", "):
	"""Convert a sequence into a string using seperator.

	Same as str.join, but does type conversion and strip extra spaces.
	"""
	return sep.join(map(str.strip, map(str, seq)))


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
		if d[key] == "" or d[key] == None:
			# del d[key] raises runtime exception, using a workaround
			empty_keys.append(key)
	for key in empty_keys:
		del d[key]

	return d


def strip_html_tags(text):
	"""Remove html tags from text"""
	return re.sub("\<[^>]*\>", "", text)


def get_file_timestamp(fn):
	"""
	Returns timestamp of the given file
	"""
	from frappe.utils import cint

	try:
		return str(cint(os.stat(fn).st_mtime))
	except OSError as e:
		if e.args[0] != 2:
			raise
		else:
			return None


# to be deprecated
def make_esc(esc_chars):
	"""
	Function generator for Escaping special characters
	"""
	return lambda s: "".join(["\\" + c if c in esc_chars else c for c in s])


# esc / unescape characters -- used for command line
def esc(s, esc_chars):
	"""
	Escape special characters
	"""
	if not s:
		return ""
	for c in esc_chars:
		esc_str = "\\" + c
		s = s.replace(c, esc_str)
	return s


def unesc(s, esc_chars):
	"""
	UnEscape special characters
	"""
	for c in esc_chars:
		esc_str = "\\" + c
		s = s.replace(esc_str, c)
	return s


def execute_in_shell(cmd, verbose=False, low_priority=False, check_exit_code=False):
	# using Popen instead of os.system - as recommended by python docs
	import tempfile
	from subprocess import Popen

	with tempfile.TemporaryFile() as stdout:
		with tempfile.TemporaryFile() as stderr:
			kwargs = {"shell": True, "stdout": stdout, "stderr": stderr}

			if low_priority:
				kwargs["preexec_fn"] = lambda: os.nice(10)

			p = Popen(cmd, **kwargs)
			exit_code = p.wait()

			stdout.seek(0)
			out = stdout.read()

			stderr.seek(0)
			err = stderr.read()

	failed = check_exit_code and exit_code

	if verbose or failed:
		if err:
			print(err)
		if out:
			print(out)

	if failed:
		raise Exception("Command failed")

	return err, out


def get_path(*path, **kwargs):
	base = kwargs.get("base")
	if not base:
		base = frappe.local.site_path
	return os.path.join(base, *path)


def get_site_base_path(sites_dir=None, hostname=None):
	return frappe.local.site_path


def get_site_path(*path):
	return get_path(*path, base=get_site_base_path())


def get_files_path(*path, **kwargs):
	return get_site_path("private" if kwargs.get("is_private") else "public", "files", *path)


def get_bench_path():
	return os.path.realpath(os.path.join(os.path.dirname(frappe.__file__), "..", "..", ".."))


def get_backups_path():
	return get_site_path("private", "backups")


def get_request_site_address(full_address=False):
	return get_url(full_address=full_address)


def get_site_url(site):
	return "http://{site}:{port}".format(site=site, port=frappe.get_conf(site).webserver_port)


def encode_dict(d, encoding="utf-8"):
	for key in d:
		if isinstance(d[key], str) and isinstance(d[key], str):
			d[key] = d[key].encode(encoding)

	return d


def decode_dict(d, encoding="utf-8"):
	for key in d:
		if isinstance(d[key], str) and not isinstance(d[key], str):
			d[key] = d[key].decode(encoding, "ignore")

	return d


@functools.lru_cache()
def get_site_name(hostname):
	return hostname.split(":")[0]


def get_disk_usage():
	"""get disk usage of files folder"""
	files_path = get_files_path()
	if not os.path.exists(files_path):
		return 0
	err, out = execute_in_shell("du -hsm {files_path}".format(files_path=files_path))
	return cint(out.split("\n")[-2].split("\t")[0])


def touch_file(path):
	with open(path, "a"):
		os.utime(path, None)
	return path


def get_test_client():
	from frappe.app import application

	return Client(application)


def get_hook_method(hook_name, fallback=None):
	method = frappe.get_hooks().get(hook_name)
	if method:
		method = frappe.get_attr(method[0])
		return method
	if fallback:
		return fallback


def call_hook_method(hook, *args, **kwargs):
	out = None
	for method_name in frappe.get_hooks(hook):
		out = out or frappe.get_attr(method_name)(*args, **kwargs)

	return out


def is_cli() -> bool:
	"""Returns True if current instance is being run via a terminal"""
	invoked_from_terminal = False
	try:
		invoked_from_terminal = bool(os.get_terminal_size())
	except Exception:
		invoked_from_terminal = sys.stdin and sys.stdin.isatty()
	return invoked_from_terminal


def update_progress_bar(txt, i, l):
	if os.environ.get("CI"):
		if i == 0:
			sys.stdout.write(txt)

		sys.stdout.write(".")
		sys.stdout.flush()
		return

	if not getattr(frappe.local, "request", None) or is_cli():
		lt = len(txt)
		try:
			col = 40 if os.get_terminal_size().columns > 80 else 20
		except OSError:
			# in case function isn't being called from a terminal
			col = 40

		if lt < 36:
			txt = txt + " " * (36 - lt)

		complete = int(float(i + 1) / l * col)
		completion_bar = ("=" * complete).ljust(col, " ")
		percent_complete = str(int(float(i + 1) / l * 100))
		sys.stdout.write("\r{0}: [{1}] {2}%".format(txt, completion_bar, percent_complete))
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
	if not sites_path:
		sites_path = getattr(frappe.local, "sites_path", None) or "."

	sites = []
	for site in os.listdir(sites_path):
		path = os.path.join(sites_path, site)

		if (
			os.path.isdir(path)
			and not os.path.islink(path)
			and os.path.exists(os.path.join(path, "site_config.json"))
		):
			# is a dir and has site_config.json
			sites.append(site)

	return sorted(sites)


def get_request_session(max_retries=3):
	import requests
	from urllib3.util import Retry

	session = requests.Session()
	session.mount(
		"http://", requests.adapters.HTTPAdapter(max_retries=Retry(total=5, status_forcelist=[500]))
	)
	session.mount(
		"https://", requests.adapters.HTTPAdapter(max_retries=Retry(total=5, status_forcelist=[500]))
	)
	return session


def watch(path, handler=None, debug=True):
	import time

	from watchdog.events import FileSystemEventHandler
	from watchdog.observers import Observer

	class Handler(FileSystemEventHandler):
		def on_any_event(self, event):
			if debug:
				print("File {0}: {1}".format(event.event_type, event.src_path))

			if not handler:
				print("No handler specified")
				return

			handler(event.src_path, event.event_type)

	event_handler = Handler()
	observer = Observer()
	observer.schedule(event_handler, path, recursive=True)
	observer.start()
	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()


def markdown(text, sanitize=True, linkify=True):
	html = text if is_html(text) else frappe.utils.md_to_html(text)

	if sanitize:
		html = html.replace("<!-- markdown -->", "")
		html = sanitize_html(html, linkify=linkify)

	return html


def sanitize_email(emails):
	sanitized = []
	for e in split_emails(emails):
		if not validate_email_address(e):
			continue

		full_name, email_id = parse_addr(e)
		sanitized.append(formataddr((full_name, email_id)))

	return ", ".join(sanitized)


def parse_addr(email_string):
	"""
	Return email_id and user_name based on email string
	Raise error if email string is not valid
	"""
	name, email = parseaddr(email_string)
	if check_format(email):
		name = get_name_from_email_string(email_string, email, name)
		return (name, email)
	else:
		email_regex = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
		email_list = re.findall(email_regex, email_string)
		if len(email_list) > 0 and check_format(email_list[0]):
			# take only first email address
			email = email_list[0]
			name = get_name_from_email_string(email_string, email, name)
			return (name, email)
	return (None, email)


def check_format(email_id):
	"""
	Check if email_id is valid. valid email:text@example.com
	String check ensures that email_id contains both '.' and
	'@' and index of '@' is less than '.'
	"""
	is_valid = False
	try:
		pos = email_id.rindex("@")
		is_valid = pos > 0 and (email_id.rindex(".") > pos) and (len(email_id) - pos > 4)
	except Exception:
		# print(e)
		pass
	return is_valid


def get_name_from_email_string(email_string, email_id, name):
	name = email_string.replace(email_id, "")
	name = re.sub("[^A-Za-z0-9\u00C0-\u024F\/\_' ]+", "", name).strip()
	if not name:
		name = email_id
	return name


def get_installed_apps_info():
	out = []
	from frappe.utils.change_log import get_versions

	for app, version_details in get_versions().items():
		out.append(
			{
				"app_name": app,
				"version": version_details.get("branch_version") or version_details.get("version"),
				"branch": version_details.get("branch"),
			}
		)

	return out


def get_site_info():
	from frappe.core.doctype.user.user import STANDARD_USERS
	from frappe.email.queue import get_emails_sent_this_month
	from frappe.utils.user import get_system_managers

	# only get system users
	users = frappe.get_all(
		"User",
		filters={"user_type": "System User", "name": ("not in", STANDARD_USERS)},
		fields=["name", "enabled", "last_login", "last_active", "language", "time_zone"],
	)
	system_managers = get_system_managers(only_name=True)
	for u in users:
		# tag system managers
		u.is_system_manager = 1 if u.name in system_managers else 0
		u.full_name = get_fullname(u.name)
		u.email = u.name
		del u["name"]

	system_settings = frappe.db.get_singles_dict("System Settings")
	space_usage = frappe._dict((frappe.local.conf.limits or {}).get("space_usage", {}))

	kwargs = {
		"fields": ["user", "creation", "full_name"],
		"filters": {"Operation": "Login", "Status": "Success"},
		"limit": "10",
	}

	site_info = {
		"installed_apps": get_installed_apps_info(),
		"users": users,
		"country": system_settings.country,
		"language": system_settings.language or "english",
		"time_zone": system_settings.time_zone,
		"setup_complete": cint(system_settings.setup_complete),
		"scheduler_enabled": system_settings.enable_scheduler,
		# usage
		"emails_sent": get_emails_sent_this_month(),
		"space_used": flt((space_usage.total or 0) / 1024.0, 2),
		"database_size": space_usage.database_size,
		"backup_size": space_usage.backup_size,
		"files_size": space_usage.files_size,
		"last_logins": frappe.get_all("Activity Log", **kwargs),
	}

	# from other apps
	for method_name in frappe.get_hooks("get_site_info"):
		site_info.update(frappe.get_attr(method_name)(site_info) or {})

	# dumps -> loads to prevent datatype conflicts
	return json.loads(frappe.as_json(site_info))


def parse_json(val):
	"""
	Parses json if string else return
	"""
	if isinstance(val, str):
		val = json.loads(val)
	if isinstance(val, dict):
		val = frappe._dict(val)
	return val


def get_db_count(*args):
	"""
	Pass a doctype or a series of doctypes to get the count of docs in them
	Parameters:
	        *args: Variable length argument list of doctype names whose doc count you need

	Returns:
	        dict: A dict with the count values.

	Example:
	        via terminal:
	                bench --site erpnext.local execute frappe.utils.get_db_count --args "['DocType', 'Communication']"
	"""
	db_count = {}
	for doctype in args:
		db_count[doctype] = frappe.db.count(doctype)

	return json.loads(frappe.as_json(db_count))


def call(fn, *args, **kwargs):
	"""
	Pass a doctype or a series of doctypes to get the count of docs in them
	Parameters:
	        fn: frappe function to be called

	Returns:
	        based on the function you call: output of the function you call

	Example:
	        via terminal:
	                bench --site erpnext.local execute frappe.utils.call --args '''["frappe.get_all", "Activity Log"]''' --kwargs '''{"fields": ["user", "creation", "full_name"], "filters":{"Operation": "Login", "Status": "Success"}, "limit": "10"}'''
	"""
	return json.loads(frappe.as_json(frappe.call(fn, *args, **kwargs)))


# Following methods are aken as-is from Python 3 codebase
# since gzip.compress and gzip.decompress are not available in Python 2.7
def gzip_compress(data, compresslevel=9):
	"""Compress data in one shot and return the compressed string.
	Optional argument is the compression level, in range of 0-9.
	"""
	buf = io.BytesIO()
	with GzipFile(fileobj=buf, mode="wb", compresslevel=compresslevel) as f:
		f.write(data)
	return buf.getvalue()


def gzip_decompress(data):
	"""Decompress a gzip compressed string in one shot.
	Return the decompressed string.
	"""
	with GzipFile(fileobj=io.BytesIO(data)) as f:
		return f.read()


def get_safe_filters(filters):
	try:
		filters = json.loads(filters)

		if isinstance(filters, (int, float)):
			filters = frappe.as_unicode(filters)

	except (TypeError, ValueError):
		# filters are not passed, not json
		pass

	return filters


def create_batch(iterable: Iterable, size: int) -> Generator[Iterable, None, None]:
	"""Convert an iterable to multiple batches of constant size of batch_size

	Args:
	        iterable (Iterable): Iterable object which is subscriptable
	        size (int): Maximum size of batches to be generated

	Yields:
	        Generator[List]: Batched iterable of maximum length `size`
	"""
	total_count = len(iterable)
	for i in range(0, total_count, size):
		yield iterable[i : min(i + size, total_count)]


def set_request(**kwargs):
	from werkzeug.test import EnvironBuilder
	from werkzeug.wrappers import Request

	builder = EnvironBuilder(**kwargs)
	frappe.local.request = Request(builder.get_environ())


def get_html_for_route(route):
	from frappe.website import render

	set_request(method="GET", path=route)
	response = render.render()
	html = frappe.safe_decode(response.get_data())
	return html


def get_file_size(path, format=False):
	num = os.path.getsize(path)

	if not format:
		return num

	suffix = "B"

	for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
		if abs(num) < 1024:
			return "{0:3.1f}{1}{2}".format(num, unit, suffix)
		num /= 1024

	return "{0:.1f}{1}{2}".format(num, "Yi", suffix)


def get_build_version():
	try:
		return str(os.path.getmtime(os.path.join(frappe.local.sites_path, ".build")))
	except OSError:
		# .build can sometimes not exist
		# this is not a major problem so send fallback
		return frappe.utils.random_string(8)


def get_bench_relative_path(file_path):
	"""Fixes paths relative to the bench root directory if exists and returns the absolute path

	Args:
	        file_path (str, Path): Path of a file that exists on the file system

	Returns:
	        str: Absolute path of the file_path
	"""
	if not os.path.exists(file_path):
		base_path = ".."
	elif file_path.startswith(os.sep):
		base_path = os.sep
	else:
		base_path = "."

	file_path = os.path.join(base_path, file_path)

	if not os.path.exists(file_path):
		print("Invalid path {0}".format(file_path[3:]))
		sys.exit(1)

	return os.path.abspath(file_path)


def groupby_metric(iterable: typing.Dict[str, list], key: str):
	"""Group records by a metric.

	Usecase: Lets assume we got country wise players list with the ranking given for each player(multiple players in a country can have same ranking aswell).
	We can group the players by ranking(can be any other metric) using this function.

	>>> d = {
	        'india': [{'id':1, 'name': 'iplayer-1', 'ranking': 1}, {'id': 2, 'ranking': 1, 'name': 'iplayer-2'}, {'id': 2, 'ranking': 2, 'name': 'iplayer-3'}],
	        'Aus': [{'id':1, 'name': 'aplayer-1', 'ranking': 1}, {'id': 2, 'ranking': 1, 'name': 'aplayer-2'}, {'id': 2, 'ranking': 2, 'name': 'aplayer-3'}]
	}
	>>> groupby(d, key='ranking')
	{1: {'Aus': [{'id': 1, 'name': 'aplayer-1', 'ranking': 1},
	                        {'id': 2, 'name': 'aplayer-2', 'ranking': 1}],
	        'india': [{'id': 1, 'name': 'iplayer-1', 'ranking': 1},
	                        {'id': 2, 'name': 'iplayer-2', 'ranking': 1}]},
	2: {'Aus': [{'id': 2, 'name': 'aplayer-3', 'ranking': 2}],
	        'india': [{'id': 2, 'name': 'iplayer-3', 'ranking': 2}]}}
	"""
	records = {}
	for category, items in iterable.items():
		for item in items:
			records.setdefault(item[key], {}).setdefault(category, []).append(item)
	return records


def get_table_name(table_name: str) -> str:
	return f"tab{table_name}" if not table_name.startswith("__") else table_name


def squashify(what):
	if isinstance(what, Sequence) and len(what) == 1:
		return what[0]

	return what


def safe_json_loads(*args):
	results = []

	for arg in args:
		try:
			arg = json.loads(arg)
		except Exception:
			pass

		results.append(arg)

	return squashify(results)


def dictify(arg):
	if isinstance(arg, MutableSequence):
		for i, a in enumerate(arg):
			arg[i] = dictify(a)
	elif isinstance(arg, MutableMapping):
		arg = frappe._dict(arg)

	return arg
