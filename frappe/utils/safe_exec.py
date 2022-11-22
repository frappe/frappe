import copy
import inspect
import json
import mimetypes
import types
from contextlib import contextmanager
from functools import lru_cache

import RestrictedPython.Guards
from html2text import html2text
from RestrictedPython import compile_restricted, safe_globals

import frappe
import frappe.exceptions
import frappe.integrations.utils
import frappe.utils
import frappe.utils.data
from frappe import _
from frappe.frappeclient import FrappeClient
from frappe.handler import execute_cmd
from frappe.modules import scrub
from frappe.utils.background_jobs import enqueue, get_jobs
from frappe.website.utils import get_next_link, get_shade, get_toc
from frappe.www.printview import get_visible_columns


class ServerScriptNotEnabled(frappe.PermissionError):
	pass


class NamespaceDict(frappe._dict):
	"""Raise AttributeError if function not found in namespace"""

	def __getattr__(self, key):
		ret = self.get(key)
		if (not ret and key.startswith("__")) or (key not in self):

			def default_function(*args, **kwargs):
				raise AttributeError(f"module has no attribute '{key}'")

			return default_function
		return ret


def safe_exec(script, _globals=None, _locals=None, restrict_commit_rollback=False):
	# server scripts can be disabled via site_config.json
	# they are enabled by default
	if "server_script_enabled" in frappe.conf:
		enabled = frappe.conf.server_script_enabled
	else:
		enabled = True

	if not enabled:
		frappe.throw(_("Please Enable Server Scripts"), ServerScriptNotEnabled)

	# build globals
	exec_globals = get_safe_globals()
	if _globals:
		exec_globals.update(_globals)

	if restrict_commit_rollback:
		exec_globals.frappe.db.pop("commit", None)
		exec_globals.frappe.db.pop("rollback", None)

	with safe_exec_flags(), patched_qb():
		# execute script compiled by RestrictedPython
		exec(compile_restricted(script), exec_globals, _locals)  # pylint: disable=exec-used

	return exec_globals, _locals


@contextmanager
def safe_exec_flags():
	frappe.flags.in_safe_exec = True
	yield
	frappe.flags.in_safe_exec = False


def get_safe_globals():
	datautils = frappe._dict()
	if frappe.db:
		date_format = frappe.db.get_default("date_format") or "yyyy-mm-dd"
		time_format = frappe.db.get_default("time_format") or "HH:mm:ss"
	else:
		date_format = "yyyy-mm-dd"
		time_format = "HH:mm:ss"

	add_data_utils(datautils)

	form_dict = getattr(frappe.local, "form_dict", frappe._dict())

	if "_" in form_dict:
		del frappe.local.form_dict["_"]

	user = getattr(frappe.local, "session", None) and frappe.local.session.user or "Guest"

	out = NamespaceDict(
		# make available limited methods of frappe
		json=NamespaceDict(loads=json.loads, dumps=json.dumps),
		dict=dict,
		log=frappe.log,
		_dict=frappe._dict,
		args=form_dict,
		frappe=NamespaceDict(
			call=call_whitelisted_function,
			flags=frappe._dict(),
			format=frappe.format_value,
			format_value=frappe.format_value,
			date_format=date_format,
			time_format=time_format,
			format_date=frappe.utils.data.global_date_format,
			form_dict=form_dict,
			bold=frappe.bold,
			copy_doc=frappe.copy_doc,
			errprint=frappe.errprint,
			qb=frappe.qb,
			get_meta=frappe.get_meta,
			get_doc=frappe.get_doc,
			get_cached_doc=frappe.get_cached_doc,
			get_list=frappe.get_list,
			get_all=frappe.get_all,
			get_system_settings=frappe.get_system_settings,
			rename_doc=frappe.rename_doc,
			utils=datautils,
			get_url=frappe.utils.get_url,
			render_template=frappe.render_template,
			msgprint=frappe.msgprint,
			throw=frappe.throw,
			sendmail=frappe.sendmail,
			get_print=frappe.get_print,
			attach_print=frappe.attach_print,
			user=user,
			get_fullname=frappe.utils.get_fullname,
			get_gravatar=frappe.utils.get_gravatar_url,
			full_name=frappe.local.session.data.full_name
			if getattr(frappe.local, "session", None)
			else "Guest",
			request=getattr(frappe.local, "request", {}),
			session=frappe._dict(
				user=user,
				csrf_token=frappe.local.session.data.csrf_token
				if getattr(frappe.local, "session", None)
				else "",
			),
			make_get_request=frappe.integrations.utils.make_get_request,
			make_post_request=frappe.integrations.utils.make_post_request,
			get_payment_gateway_controller=frappe.integrations.utils.get_payment_gateway_controller,
			make_put_request=frappe.integrations.utils.make_put_request,
			socketio_port=frappe.conf.socketio_port,
			get_hooks=get_hooks,
			enqueue=safe_enqueue,
			sanitize_html=frappe.utils.sanitize_html,
			log_error=frappe.log_error,
			lang=getattr(frappe.local, "lang", "en"),
		),
		FrappeClient=FrappeClient,
		style=frappe._dict(border_color="#d1d8dd"),
		get_toc=get_toc,
		get_next_link=get_next_link,
		_=frappe._,
		get_shade=get_shade,
		scrub=scrub,
		guess_mimetype=mimetypes.guess_type,
		html2text=html2text,
		dev_server=frappe.local.dev_server,
		run_script=run_script,
		is_job_queued=is_job_queued,
	)

	add_module_properties(
		frappe.exceptions, out.frappe, lambda obj: inspect.isclass(obj) and issubclass(obj, Exception)
	)

	if not frappe.flags.in_setup_help:
		out.get_visible_columns = get_visible_columns
		out.frappe.date_format = date_format
		out.frappe.time_format = time_format
		out.frappe.db = NamespaceDict(
			get_list=frappe.get_list,
			get_all=frappe.get_all,
			get_value=frappe.db.get_value,
			set_value=frappe.db.set_value,
			get_single_value=frappe.db.get_single_value,
			get_default=frappe.db.get_default,
			exists=frappe.db.exists,
			count=frappe.db.count,
			escape=frappe.db.escape,
			sql=read_sql,
			commit=frappe.db.commit,
			rollback=frappe.db.rollback,
		)

	if frappe.response:
		out.frappe.response = frappe.response

	out.update(safe_globals)

	# default writer allows write access
	out._write_ = _write
	out._getitem_ = _getitem
	out._getattr_ = _getattr

	# allow iterators and list comprehension
	out._getiter_ = iter
	out._iter_unpack_sequence_ = RestrictedPython.Guards.guarded_iter_unpack_sequence
	out.sorted = sorted

	return out


def is_job_queued(job_name, queue="default"):
	"""
	:param job_name: used to identify a queued job, usually dotted path to function
	:param queue: should be either long, default or short
	"""

	site = frappe.local.site
	queued_jobs = get_jobs(site=site, queue=queue, key="job_name").get(site)
	return queued_jobs and job_name in queued_jobs


def safe_enqueue(function, **kwargs):
	"""
	Enqueue function to be executed using a background worker
	Accepts frappe.enqueue params like job_name, queue, timeout, etc.
	in addition to params to be passed to function

	:param function: whitelised function or API Method set in Server Script
	"""

	return enqueue("frappe.utils.safe_exec.call_whitelisted_function", function=function, **kwargs)


def call_whitelisted_function(function, **kwargs):
	"""Executes a whitelisted function or Server Script of type API"""

	return call_with_form_dict(lambda: execute_cmd(function), kwargs)


def run_script(script, **kwargs):
	"""run another server script"""

	return call_with_form_dict(
		lambda: frappe.get_doc("Server Script", script).execute_method(), kwargs
	)


def call_with_form_dict(function, kwargs):
	# temporarily update form_dict, to use inside below call
	form_dict = getattr(frappe.local, "form_dict", frappe._dict())
	if kwargs:
		frappe.local.form_dict = form_dict.copy().update(kwargs)

	try:
		return function()
	finally:
		frappe.local.form_dict = form_dict


@contextmanager
def patched_qb():
	require_patching = isinstance(frappe.qb.terms, types.ModuleType)
	try:
		if require_patching:
			_terms = frappe.qb.terms
			frappe.qb.terms = _flatten(frappe.qb.terms)
		yield
	finally:
		if require_patching:
			frappe.qb.terms = _terms


@lru_cache()
def _flatten(module):
	new_mod = NamespaceDict()
	for name, obj in inspect.getmembers(module, lambda x: not inspect.ismodule(x)):
		if not name.startswith("_"):
			new_mod[name] = obj
	return new_mod


def get_hooks(hook=None, default=None, app_name=None):
	hooks = frappe.get_hooks(hook=hook, default=default, app_name=app_name)
	return copy.deepcopy(hooks)


def read_sql(query, *args, **kwargs):
	"""a wrapper for frappe.db.sql to allow reads"""
	query = str(query)
	if frappe.flags.in_safe_exec and not query.strip().lower().startswith("select"):
		raise frappe.PermissionError("Only SELECT SQL allowed in scripting")
	return frappe.db.sql(query, *args, **kwargs)


def _getitem(obj, key):
	# guard function for RestrictedPython
	# allow any key to be accessed as long as it does not start with underscore
	if isinstance(key, str) and key.startswith("_"):
		raise SyntaxError("Key starts with _")
	return obj[key]


def _getattr(object, name, default=None):
	# guard function for RestrictedPython
	# allow any key to be accessed as long as
	# 1. it does not start with an underscore (safer_getattr)
	# 2. it is not an UNSAFE_ATTRIBUTES

	UNSAFE_ATTRIBUTES = {
		# Generator Attributes
		"gi_frame",
		"gi_code",
		# Coroutine Attributes
		"cr_frame",
		"cr_code",
		"cr_origin",
		# Async Generator Attributes
		"ag_code",
		"ag_frame",
		# Traceback Attributes
		"tb_frame",
		"tb_next",
	}

	if isinstance(name, str) and (name in UNSAFE_ATTRIBUTES):
		raise SyntaxError("{name} is an unsafe attribute".format(name=name))

	if isinstance(object, (types.ModuleType, types.CodeType, types.TracebackType, types.FrameType)):
		raise SyntaxError(f"Reading {object} attributes is not allowed")

	return RestrictedPython.Guards.safer_getattr(object, name, default=default)


def _write(obj):
	# guard function for RestrictedPython
	# allow writing to any object
	return obj


def add_data_utils(data):
	for key, obj in frappe.utils.data.__dict__.items():
		if key in VALID_UTILS:
			data[key] = obj


def add_module_properties(module, data, filter_method):
	for key, obj in module.__dict__.items():
		if key.startswith("_"):
			# ignore
			continue

		if filter_method(obj):
			# only allow functions
			data[key] = obj


VALID_UTILS = (
	"DATE_FORMAT",
	"TIME_FORMAT",
	"DATETIME_FORMAT",
	"is_invalid_date_string",
	"getdate",
	"get_datetime",
	"to_timedelta",
	"get_timedelta",
	"add_to_date",
	"add_days",
	"add_months",
	"add_years",
	"date_diff",
	"month_diff",
	"time_diff",
	"time_diff_in_seconds",
	"time_diff_in_hours",
	"now_datetime",
	"get_timestamp",
	"get_eta",
	"get_time_zone",
	"convert_utc_to_user_timezone",
	"now",
	"nowdate",
	"today",
	"nowtime",
	"get_first_day",
	"get_quarter_start",
	"get_first_day_of_week",
	"get_year_start",
	"get_last_day_of_week",
	"get_last_day",
	"get_time",
	"get_datetime_in_timezone",
	"get_datetime_str",
	"get_date_str",
	"get_time_str",
	"get_user_date_format",
	"get_user_time_format",
	"format_date",
	"format_time",
	"format_datetime",
	"format_duration",
	"get_weekdays",
	"get_weekday",
	"get_timespan_date_range",
	"global_date_format",
	"has_common",
	"flt",
	"cint",
	"floor",
	"ceil",
	"cstr",
	"rounded",
	"remainder",
	"safe_div",
	"round_based_on_smallest_currency_fraction",
	"encode",
	"parse_val",
	"fmt_money",
	"get_number_format_info",
	"money_in_words",
	"in_words",
	"is_html",
	"is_image",
	"get_thumbnail_base64_for_image",
	"image_to_base64",
	"pdf_to_base64",
	"strip_html",
	"escape_html",
	"pretty_date",
	"comma_or",
	"comma_and",
	"comma_sep",
	"new_line_sep",
	"filter_strip_join",
	"get_url",
	"get_host_name_from_request",
	"url_contains_port",
	"get_host_name",
	"get_link_to_form",
	"get_link_to_report",
	"get_absolute_url",
	"get_url_to_form",
	"get_url_to_list",
	"get_url_to_report",
	"get_url_to_report_with_filters",
	"evaluate_filters",
	"compare",
	"get_filter",
	"make_filter_tuple",
	"make_filter_dict",
	"sanitize_column",
	"scrub_urls",
	"expand_relative_urls",
	"quoted",
	"quote_urls",
	"unique",
	"strip",
	"to_markdown",
	"md_to_html",
	"markdown",
	"is_subset",
	"generate_hash",
	"formatdate",
	"get_user_info_for_avatar",
	"get_abbr",
)
