
import os, json, inspect
import mimetypes
from html2text import html2text
from RestrictedPython import compile_restricted, safe_globals
import RestrictedPython.Guards
import frappe
import frappe.utils
import frappe.utils.data
from frappe.website.utils import (get_shade, get_toc, get_next_link)
from frappe.modules import scrub
from frappe.www.printview import get_visible_columns
import frappe.exceptions
import frappe.integrations.utils

class ServerScriptNotEnabled(frappe.PermissionError): pass

def safe_exec(script, _globals=None, _locals=None):
	# script reports must be enabled via site_config.json
	if not frappe.conf.server_script_enabled:
		frappe.throw('Please Enable Server Scripts', ServerScriptNotEnabled)

	# build globals
	exec_globals = get_safe_globals()
	if _globals:
		exec_globals.update(_globals)

	# execute script compiled by RestrictedPython
	exec(compile_restricted(script), exec_globals, _locals) # pylint: disable=exec-used

def get_safe_globals():
	datautils = frappe._dict()
	if frappe.db:
		date_format = frappe.db.get_default("date_format") or "yyyy-mm-dd"
		time_format = frappe.db.get_default("time_format") or "HH:mm:ss"
	else:
		date_format = "yyyy-mm-dd"
		time_format = "HH:mm:ss"

	add_module_properties(frappe.utils.data, datautils, lambda obj: hasattr(obj, "__call__"))

	if "_" in getattr(frappe.local, 'form_dict', {}):
		del frappe.local.form_dict["_"]

	user = getattr(frappe.local, "session", None) and frappe.local.session.user or "Guest"

	out = frappe._dict(
		# make available limited methods of frappe
		json=json,
		dict=dict,
		_dict=frappe._dict,
		frappe=frappe._dict(
			flags=frappe.flags,
			format=frappe.format_value,
			format_value=frappe.format_value,
			date_format=date_format,
			time_format=time_format,
			format_date=frappe.utils.data.global_date_format,
			form_dict=getattr(frappe.local, 'form_dict', {}),

			get_meta=frappe.get_meta,
			get_doc=frappe.get_doc,
			get_cached_doc=frappe.get_cached_doc,
			get_list=frappe.get_list,
			get_all=frappe.get_all,
			get_system_settings=frappe.get_system_settings,

			utils=datautils,
			get_url=frappe.utils.get_url,
			render_template=frappe.render_template,
			msgprint=frappe.msgprint,
			throw=frappe.throw,
			sendmail = frappe.sendmail,

			user=user,
			get_fullname=frappe.utils.get_fullname,
			get_gravatar=frappe.utils.get_gravatar_url,
			full_name=frappe.local.session.data.full_name if getattr(frappe.local, "session", None) else "Guest",
			request=getattr(frappe.local, 'request', {}),
			session=frappe._dict(
				user=user,
				csrf_token=frappe.local.session.data.csrf_token if getattr(frappe.local, "session", None) else ''
			),
			make_get_request = frappe.integrations.utils.make_get_request,
			make_post_request = frappe.integrations.utils.make_post_request,
			socketio_port=frappe.conf.socketio_port,
			get_hooks=frappe.get_hooks,
			sanitize_html=frappe.utils.sanitize_html
		),
		style=frappe._dict(
			border_color='#d1d8dd'
		),
		get_toc=get_toc,
		get_next_link=get_next_link,
		_=frappe._,
		get_shade=get_shade,
		scrub=scrub,
		guess_mimetype=mimetypes.guess_type,
		html2text=html2text,
		dev_server=1 if os.environ.get('DEV_SERVER', False) else 0
	)

	add_module_properties(frappe.exceptions, out.frappe, lambda obj: inspect.isclass(obj) and issubclass(obj, Exception))

	if not frappe.flags.in_setup_help:
		out.get_visible_columns = get_visible_columns
		out.frappe.date_format = date_format
		out.frappe.time_format = time_format
		out.frappe.db = frappe._dict(
			get_list = frappe.get_list,
			get_all = frappe.get_all,
			get_value = frappe.db.get_value,
			set_value = frappe.db.set_value,
			get_single_value = frappe.db.get_single_value,
			get_default = frappe.db.get_default,
			escape = frappe.db.escape,
		)

	if frappe.response:
		out.frappe.response = frappe.response

	out.update(safe_globals)

	# default writer allows write access
	out._write_ = _write
	out._getitem_ = _getitem

	# allow iterators and list comprehension
	out._getiter_ = iter
	out._iter_unpack_sequence_ = RestrictedPython.Guards.guarded_iter_unpack_sequence
	out.sorted = sorted

	return out

def _getitem(obj, key):
	# guard function for RestrictedPython
	# allow any key to be accessed as long as it does not start with underscore
	if isinstance(key, str) and key.startswith('_'):
		raise SyntaxError('Key starts with _')
	return obj[key]

def _write(obj):
	# guard function for RestrictedPython
	# allow writing to any object
	return obj

def add_module_properties(module, data, filter_method):
	for key, obj in module.__dict__.items():
		if key.startswith("_"):
			# ignore
			continue

		if filter_method(obj):
			# only allow functions
			data[key] = obj
