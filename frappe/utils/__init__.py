# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import functools
import io
import os
import shutil
import sys
import traceback
from collections import deque
from collections.abc import (
	Callable,
	Container,
	Generator,
	Iterable,
	MutableMapping,
	MutableSequence,
	Sequence,
)
from email.header import decode_header, make_header
from email.utils import formataddr, parseaddr
from typing import Any, Generic, TypeAlias, TypedDict

import orjson
from werkzeug.test import Client

from frappe.deprecation_dumpster import gzip_compress, gzip_decompress, make_esc

# utility functions like cint, int, flt, etc.
from frappe.utils.data import *
from frappe.utils.html_utils import sanitize_html

EMAIL_NAME_PATTERN = re.compile(r"[^A-Za-z0-9\u00C0-\u024F\/\_\' ]+")
EMAIL_STRING_PATTERN = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
NON_MD_HTML_PATTERN = re.compile(r"<p[\s]*>|<br[\s]*>")
HTML_TAGS_PATTERN = re.compile(r"\<[^>]*\>")
INCLUDE_DIRECTIVE_PATTERN = re.compile("""({% include ['"]([^'"]*)['"] %})""")
PHONE_NUMBER_PATTERN = re.compile(r"([0-9\ \+\_\-\,\.\*\#\(\)]){1,20}$")
PERSON_NAME_PATTERN = re.compile(r"^[\w][\w\'\-]*( \w[\w\'\-]*)*$")
WHITESPACE_PATTERN = re.compile(r"[\t\n\r]")
MULTI_EMAIL_STRING_PATTERN = re.compile(r'[,\n](?=(?:[^"]|"[^"]*")*$)')
EMAIL_MATCH_PATTERN = re.compile(
	r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?",
	re.IGNORECASE,
)

UNSET = object()

PropertyType: TypeAlias = property | functools.cached_property


if sys.version_info < (3, 11):

	def exception():
		_exc_type, exc_value, _exc_traceback = sys.exc_info()
		return exc_value

	sys.exception = exception


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
	return cstr(parse_addr(email)[1])


def validate_phone_number_with_country_code(phone_number: str, fieldname: str) -> None:
	from phonenumbers import NumberParseException, is_valid_number, parse

	from frappe import _

	if not phone_number:
		return

	valid_number = False
	error_message = _("Phone Number {0} set in field {1} is not valid.")
	error_title = _("Invalid Phone Number")
	try:
		if valid_number := is_valid_number(parse(phone_number)):
			return True
	except NumberParseException as e:
		if e.error_type == NumberParseException.INVALID_COUNTRY_CODE:
			error_message = _("Please select a country code for field {1}.")
			error_title = _("Country Code Required")
	finally:
		if not valid_number:
			frappe.throw(
				error_message.format(frappe.bold(phone_number), frappe.bold(fieldname)),
				title=error_title,
				exc=frappe.InvalidPhoneNumberError,
			)


def validate_phone_number(phone_number, throw=False):
	"""Return True if valid phone number."""
	if not phone_number:
		return False

	phone_number = phone_number.strip()
	match = PHONE_NUMBER_PATTERN.match(phone_number)

	if not match and throw:
		frappe.throw(
			frappe._("{0} is not a valid Phone Number").format(phone_number), frappe.InvalidPhoneNumberError
		)

	return bool(match)


def validate_name(name, throw=False):
	"""Return True if the name is valid

	* valid names may have unicode and ascii characters, dash, quotes, numbers
	* anything else is considered invalid

	Note: "Name" here is name of a person, not the primary key in Frappe doctypes.
	"""
	if not name:
		return False

	name = name.strip()
	match = PERSON_NAME_PATTERN.match(name)

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
			match = EMAIL_MATCH_PATTERN.match(email_id) if email_id else None

			if not match:
				_valid = False

		if not _valid:
			if throw:
				invalid_email = frappe.utils.escape_html(e)
				frappe.throw(
					frappe._("{0} is not a valid Email Address").format(invalid_email),
					frappe.InvalidEmailAddressError,
				)
			return None
		else:
			return email_id

	out = []
	for e in email_str.split(","):
		if not e:
			continue
		email = _check(e.strip())
		if email:
			out.append(email)

	return ", ".join(out)


def split_emails(txt):
	email_list = []

	# emails can be separated by comma or newline
	s = WHITESPACE_PATTERN.sub(" ", cstr(txt))
	for email in MULTI_EMAIL_STRING_PATTERN.split(s):
		email = strip(cstr(email))
		if email:
			email_list.append(email)

	return email_list


def validate_url(
	txt: str,
	throw: bool = False,
	valid_schemes: str | Container[str] | None = None,
) -> bool:
	"""
	Return True if `txt` represents a valid URL.

	Args:
	        throw: throws a validationError if URL is not valid
	        valid_schemes: if provided checks the given URL's scheme against this
	"""
	url = urlparse(txt)
	is_valid = bool(url.scheme and (url.netloc or url.path)) or bool(txt and txt.startswith("/"))

	# Handle scheme validation
	if isinstance(valid_schemes, str):
		is_valid = is_valid and (url.scheme == valid_schemes)
	elif isinstance(valid_schemes, list | tuple | set):
		is_valid = is_valid and (url.scheme in valid_schemes)

	if not is_valid and throw:
		frappe.throw(frappe._("'{0}' is not a valid URL").format(frappe.bold(txt)))

	return is_valid


def random_string(length: int) -> str:
	"""generate a random string"""
	import string
	from random import choice

	return "".join(choice(string.ascii_letters + string.digits) for i in range(length))


def has_gravatar(email: str) -> str:
	"""Return gravatar url if user has set an avatar at gravatar.com."""
	import requests

	if frappe.flags.in_import or frappe.flags.in_install or frappe.in_test:
		# no gravatar if via upload
		# since querying gravatar for every item will be slow
		return ""

	gravatar_url = get_gravatar_url(email, "404")
	try:
		res = requests.get(gravatar_url, timeout=5)
		if res.status_code == 200:
			return gravatar_url
		else:
			return ""
	except requests.exceptions.RequestException:
		return ""


def get_gravatar_url(email: str, default: Literal["mm", "404"] = "mm") -> str:
	"""Return gravatar URL for the given email.

	If `default` is set to "404", gravatar URL will return 404 if no avatar is found.
	If `default` is set to "mm", a placeholder image will be returned.
	"""
	hexdigest = hashlib.md5(frappe.as_unicode(email).encode("utf-8"), usedforsecurity=False).hexdigest()
	return f"https://secure.gravatar.com/avatar/{hexdigest}?d={default}&s=200"


def get_gravatar(email: str) -> str:
	"""Return gravatar URL if user has set an avatar at gravatar.com.

	Else return identicon image (base64)."""
	from frappe.utils.identicon import Identicon

	return has_gravatar(email) or Identicon(email).base64()


def get_traceback(with_context: bool = False) -> str:
	"""Return the traceback of the Exception."""
	from traceback_with_variables import iter_exc_lines

	exc_type, exc_value, exc_tb = sys.exc_info()

	if not any([exc_type, exc_value, exc_tb]):
		return ""

	if with_context:
		trace_list = iter_exc_lines(fmt=_get_traceback_sanitizer())
		tb = "\n".join(trace_list)
	else:
		trace_list = traceback.format_exception(exc_type, exc_value, exc_tb)
		tb = "".join(cstr(t) for t in trace_list)

	bench_path = get_bench_path() + "/"
	return tb.replace(bench_path, "")


@functools.lru_cache(maxsize=1)
def _get_traceback_sanitizer():
	from traceback_with_variables import Format

	blocklist = [
		"password",
		"passwd",
		"secret",
		"token",
		"key",
		"pwd",
	]

	placeholder = "********"

	def dict_printer(v: dict) -> str:
		from copy import deepcopy

		v = deepcopy(v)
		for key in blocklist:
			if key in v:
				v[key] = placeholder

		return str(v)

	# Adapted from https://github.com/andy-landy/traceback_with_variables/blob/master/examples/format_customized.py
	# Reused under MIT license: https://github.com/andy-landy/traceback_with_variables/blob/master/LICENSE

	return Format(
		custom_var_printers=[
			# redact variables
			*[(variable_name, lambda *a, **kw: placeholder) for variable_name in blocklist],
			# redact dictionary keys
			(["_secret", dict, lambda *a, **kw: False], dict_printer),
			(["_secret", frappe._dict, lambda *a, **kw: False], dict_printer),
		],
	)


def log(event, details):
	frappe.logger(event).info(details)


def dict_to_str(args: dict[str, Any], sep: str = "&") -> str:
	"""Convert a dictionary to URL."""
	return sep.join(f"{k!s}=" + quote(str(args[k] or "")) for k in list(args))


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


def remove_blanks(d: dict) -> dict:
	"""Return d with empty ('' or None) values stripped. Mutates inplace."""
	for k, v in tuple(d.items()):
		if not v:
			del d[k]
	return d


def strip_html_tags(text: str) -> str:
	"""Remove html tags from the given `text`."""
	return HTML_TAGS_PATTERN.sub("", text)


def get_file_timestamp(fn):
	"""Return timestamp of the given file."""
	from frappe.utils import cint

	try:
		return str(cint(os.stat(fn).st_mtime))
	except OSError as e:
		if e.args[0] != 2:
			raise
		else:
			return None


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
	import shlex
	import tempfile
	from subprocess import Popen

	if isinstance(cmd, list):
		# ensure it's properly escaped; only a single string argument executes via shell
		cmd = shlex.join(cmd)

	with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
		kwargs = {
			"shell": True,
			"stdout": stdout,
			"stderr": stderr,
			"executable": shutil.which("bash") or "/bin/bash",
		}

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
		raise frappe.CommandFailedError(
			"Command failed", out.decode(errors="replace"), err.decode(errors="replace")
		)

	return err, out


def get_path(*path, **kwargs):
	base = kwargs.get("base")
	if not base:
		base = frappe.local.site_path
	return os.path.join(base, *path)


def get_site_base_path():
	return frappe.local.site_path


def get_site_path(*path):
	return get_path(*path, base=get_site_base_path())


def get_files_path(*path, **kwargs):
	return get_site_path("private" if kwargs.get("is_private") else "public", "files", *path)


def get_bench_path():
	return os.environ.get("FRAPPE_BENCH_ROOT") or os.path.realpath(
		os.path.join(os.path.dirname(frappe.__file__), "..", "..", "..")
	)


def get_bench_id():
	return frappe.get_conf().get("bench_id", get_bench_path().strip("/").replace("/", "-"))


def get_site_id(site=None):
	return f"{site or frappe.local.site}@{get_bench_id()}"


def get_backups_path():
	return get_site_path("private", "backups")


def get_request_site_address(full_address=False):
	return get_url(full_address=full_address)


def get_site_url(site):
	conf = frappe.get_conf(site)
	if conf.host_name:
		return conf.host_name
	return f"http://{site}:{conf.webserver_port}"


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


@functools.lru_cache
def get_site_name(hostname):
	return hostname.split(":", 1)[0]


def get_disk_usage():
	"""get disk usage of files folder"""
	files_path = get_files_path()
	if not os.path.exists(files_path):
		return 0
	err, out = execute_in_shell(f"du -hsm {files_path}")
	return cint(out.split("\n")[-2].split("\t")[0])


def touch_file(path):
	with open(path, "a"):
		os.utime(path, None)
	return path


def get_test_client(use_cookies=True) -> Client:
	"""Return an test instance of the Frappe WSGI."""
	from frappe.app import application

	return Client(application, use_cookies=use_cookies)


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
	"""Return True if current instance is being run via a terminal."""
	invoked_from_terminal = False
	try:
		invoked_from_terminal = bool(os.get_terminal_size())
	except Exception:
		invoked_from_terminal = sys.stdin and sys.stdin.isatty()
	return invoked_from_terminal


def update_progress_bar(txt, i, l, absolute=False):
	if os.environ.get("CI"):
		if i == 0:
			sys.stdout.write(txt)

		sys.stdout.write(".")
		sys.stdout.flush()
		return

	if not getattr(frappe.local, "request", None) or is_cli():  # pragma: no cover
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
		percent_complete = f"{int(float(i + 1) / l * 100)!s}%"
		status = f"{i} of {l}" if absolute else percent_complete
		sys.stdout.write(f"\r{txt}: [{completion_bar}] {status}")
		sys.stdout.flush()


def get_html_format(print_path):
	html_format = None
	if os.path.exists(print_path):
		with open(print_path) as f:
			html_format = f.read()

		for include_directive, path in INCLUDE_DIRECTIVE_PATTERN.findall(html_format):
			for app_name in frappe.get_installed_apps():
				include_path = frappe.get_app_path(app_name, *path.split(os.path.sep))
				if os.path.exists(include_path):
					with open(include_path) as f:
						html_format = html_format.replace(include_directive, f.read())
					break

	return html_format


def is_markdown(text):
	if "<!-- markdown -->" in text:
		return True
	elif "<!-- html -->" in text:
		return False
	else:
		return not NON_MD_HTML_PATTERN.search(text)


def is_a_property(x) -> bool:
	"""Get properties (@property, @cached_property) in a controller class"""
	return isinstance(x, PropertyType)


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


def get_request_session(max_retries=5):
	import requests
	from requests.adapters import HTTPAdapter, Retry

	session = requests.Session()
	http_adapter = HTTPAdapter(max_retries=Retry(total=max_retries, status_forcelist=[500]))

	session.mount("http://", http_adapter)
	session.mount("https://", http_adapter)

	return session


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
		email_list = EMAIL_STRING_PATTERN.findall(email_string)
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
	name = EMAIL_NAME_PATTERN.sub("", name).strip()
	if not name:
		name = email_id
	return name


def get_installed_apps_info():
	out = []
	from frappe.utils.change_log import get_versions

	out.extend(
		{
			"app_name": app,
			"version": version_details.get("branch_version") or version_details.get("version"),
			"branch": version_details.get("branch"),
		}
		for app, version_details in get_versions().items()
	)
	return out


def get_site_info():
	from frappe.email.queue import get_emails_sent_this_month
	from frappe.utils.user import get_system_managers

	# only get system users
	users = frappe.get_all(
		"User",
		filters={"user_type": "System User", "name": ("not in", frappe.STANDARD_USERS)},
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
		"filters": {"operation": "Login", "status": "Success"},
		"limit": "10",
	}

	site_info = {
		"installed_apps": get_installed_apps_info(),
		"users": users,
		"country": system_settings.country,
		"language": system_settings.language or "english",
		"time_zone": system_settings.time_zone,
		"setup_complete": frappe.is_setup_complete(),
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
	return orjson.loads(frappe.as_json(site_info))


def get_db_count(*args):
	"""
	Pass a doctype or a series of doctypes to get the count of docs in them.

	Parameters:
	        *args: Variable length argument list of doctype names whose doc count you need

	Return:
	        dict: A dict with the count values.

	Example:
	        via terminal:
	                bench --site erpnext.local execute frappe.utils.get_db_count --args "['DocType', 'Communication']"
	"""
	db_count = {}
	for doctype in args:
		db_count[doctype] = frappe.db.count(doctype)

	return orjson.loads(frappe.as_json(db_count))


def call(fn, *args, **kwargs):
	"""
	Pass a doctype or a series of doctypes to get the count of docs in them
	Parameters:
	        fn: frappe function to be called

	Return:
	        based on the function you call: output of the function you call

	Example:
	        via terminal:
	                bench --site erpnext.local execute frappe.utils.call --args '''["frappe.get_all", "Activity Log"]''' --kwargs '''{"fields": ["user", "creation", "full_name"], "filters":{"Operation": "Login", "Status": "Success"}, "limit": "10"}'''
	"""
	return orjson.loads(frappe.as_json(frappe.call(fn, *args, **kwargs)))


def get_safe_filters(filters):
	try:
		filters = orjson.loads(filters)

		if isinstance(filters, int | float):
			filters = frappe.as_unicode(filters)

	except (TypeError, ValueError):
		# filters are not passed, not json
		pass

	return filters


def create_batch(iterable: Iterable, size: int) -> Generator[Iterable, None, None]:
	"""Convert an iterable to multiple batches of constant size of batch_size.

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
	from frappe.website.serve import get_response

	set_request(method="GET", path=route)
	response = get_response()
	return frappe.safe_decode(response.get_data())


def get_file_size(path, format=False):
	num = os.path.getsize(path)

	if not format:
		return num

	suffix = "B"

	for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
		if abs(num) < 1024:
			return f"{num:3.1f}{unit}{suffix}"
		num /= 1024

	return "{:.1f}{}{}".format(num, "Yi", suffix)


def get_build_version():
	try:
		return str(os.path.getmtime(os.path.join(frappe.local.sites_path, "assets/assets.json")))
	except OSError:
		# .build can sometimes not exist
		# this is not a major problem so send fallback
		return frappe.utils.random_string(8)


def get_assets_json():
	def _get_assets():
		# get merged assets.json and assets-rtl.json
		assets = frappe.parse_json(frappe.read_file("assets/assets.json"))

		if assets_rtl := frappe.read_file("assets/assets-rtl.json"):
			assets.update(frappe.parse_json(assets_rtl))

		return assets

	if not frappe.conf.developer_mode:
		return frappe.client_cache.get_value(
			"assets_json",
			shared=True,
			generator=_get_assets,
		)

	else:
		return _get_assets()


def get_bench_relative_path(file_path):
	"""Fix paths relative to the bench root directory if exists and return the absolute path.

	Args:
	        file_path (str, Path): Path of a file that exists on the file system

	Return:
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
		print(f"Invalid path {file_path[3:]}")
		sys.exit(1)

	return os.path.abspath(file_path)


def groupby_metric(iterable: dict[str, list], key: str):
	"""Group records by a metric.

	Usecase: Lets assume we got country wise players list with the ranking given for each player(multiple players in a country can have same ranking aswell).
	We can group the players by ranking(can be any other metric) using this function.

	>>> d = {
	        'india': [{'id':1, 'name': 'iplayer-1', 'ranking': 1}, {'id': 2, 'ranking': 1, 'name': 'iplayer-2'}, {'id': 2, 'ranking': 2, 'name': 'iplayer-3'}],
	        'Aus': [{'id':1, 'name': 'aplayer-1', 'ranking': 1}, {'id': 2, 'ranking': 1, 'name': 'aplayer-2'}, {'id': 2, 'ranking': 2, 'name': 'aplayer-3'}]
	}
	>>> groupby(d, key="ranking")
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


def get_table_name(table_name: str, wrap_in_backticks: bool = False) -> str:
	name = f"tab{table_name}" if not table_name.startswith("__") else table_name

	if wrap_in_backticks:
		return f"`{name}`"

	return name


def squashify(what):
	if isinstance(what, Sequence) and len(what) == 1:
		return what[0]

	return what


def safe_json_loads(*args):
	results = []

	for arg in args:
		try:
			arg = orjson.loads(arg)
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


class _UserInfo(TypedDict):
	fullname: str
	image: str
	name: str
	email: str
	time_zone: str


def add_user_info(user: str | list[str] | set[str], user_info: dict[str, _UserInfo]) -> None:
	if not user:
		return

	if isinstance(user, str):
		user = [user]

	missing_users = [u for u in user if u not in user_info]
	if not missing_users:
		return

	missing_info = frappe.get_all(
		"User",
		{"name": ("in", missing_users)},
		["full_name", "user_image", "name", "email", "time_zone"],
	)

	for info in missing_info:
		user_info.setdefault(info.name, frappe._dict()).update(
			fullname=info.full_name or info.name,
			image=info.user_image,
			name=info.name,
			email=info.email,
			time_zone=info.time_zone,
		)


def is_git_url(url: str) -> bool:
	# modified to allow without the tailing .git from https://github.com/jonschlinkert/is-git-url.git
	pattern = r"(?:git|ssh|https?|\w*@[-\w.]+):(\/\/)?(.*?)(\.git)?(\/?|\#[-\d\w._]+?)$"
	return bool(re.match(pattern, url))


class CallbackManager:
	"""Manage callbacks.

	```
	# Capture callacks
	callbacks = CallbackManager()

	# Put a function call in queue
	callbacks.add(func)

	# Run all pending functions in queue
	callbacks.run()

	# Reset queue
	callbacks.reset()
	```

	Example usage: frappe.db.after_commit
	"""

	__slots__ = ("_functions",)

	def __init__(self) -> None:
		self._functions = deque()

	def add(self, func: Callable) -> None:
		"""Add a function to queue, functions are executed in order of addition."""
		self._functions.append(func)

	def __call__(self, func: Callable) -> None:
		self.add(func)

	def run(self):
		"""Run all functions in queue"""
		while self._functions:
			_func = self._functions.popleft()
			_func()

	def reset(self):
		self._functions.clear()


def safe_eval(code, eval_globals=None, eval_locals=None):
	"""A safer `eval`"""

	from frappe.utils.safe_exec import safe_eval

	return safe_eval(code, eval_globals, eval_locals)


def create_folder(path, with_init=False):
	"""Create a folder in the given path and add an `__init__.py` file (optional).

	:param path: Folder path.
	:param with_init: Create `__init__.py` in the new folder."""
	from frappe.utils import touch_file

	if not os.path.exists(path):
		os.makedirs(path)

		if with_init:
			touch_file(os.path.join(path, "__init__.py"))


cached_property = functools.cached_property
if sys.version_info.minor < 12:
	T = TypeVar("T")

	class cached_property(functools.cached_property, Generic[T]):
		"""
		A simpler `functools.cached_property` implementation without locks.
		This isn't needed in Python 3.12+, since lock was removed in newer versions.
		Hence, in those versions, it returns the `functools.cached_property` object.

		This does not prevent a possible race condition in multi-threaded usage.
		The getter function could run more than once on the same instance,
		with the latest run setting the cached value. If the cached property is
		idempotent or otherwise not harmful to run more than once on an instance,
		this is fine. If synchronization is needed, implement the necessary locking
		inside the decorated getter function or around the cached property access.
		"""

		def __init__(self, func: Callable[[Any], T]):
			self.func = func
			self.attrname = None
			self.__doc__ = func.__doc__
			self.__module__ = func.__module__

		def __set_name__(self, owner, name):
			if self.attrname is None:
				self.attrname = name

			elif name != self.attrname:
				raise TypeError(
					"Cannot assign the same cached_property to two different names "
					f"({self.attrname!r} and {name!r})."
				)

		def __get__(self, instance, owner=None) -> T:
			if instance is None:
				return self

			value = self.func(instance)
			instance.__dict__[self.attrname] = value
			return value
# end: custom cached_property implementation
