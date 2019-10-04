
import os, json
import mimetypes
from html2text import html2text

def get_safe_globals():
	import frappe
	import frappe.utils
	import frappe.utils.data
	from frappe.model.document import get_controller
	from frappe.website.utils import (get_shade, get_toc, get_next_link)
	from frappe.modules import scrub
	from frappe.www.printview import get_visible_columns

	datautils = {}
	if frappe.db:
		date_format = frappe.db.get_default("date_format") or "yyyy-mm-dd"
	else:
		date_format = 'yyyy-mm-dd'

	for key, obj in frappe.utils.data.__dict__.items():
		if key.startswith("_"):
			# ignore
			continue

		if hasattr(obj, "__call__"):
			# only allow functions
			datautils[key] = obj

	if "_" in getattr(frappe.local, 'form_dict', {}):
		del frappe.local.form_dict["_"]

	user = getattr(frappe.local, "session", None) and frappe.local.session.user or "Guest"

	out = frappe._dict(
		# make available limited methods of frappe
		frappe =  frappe._dict({
			"_": frappe._,
			'flags': frappe.flags,
			"get_url": frappe.utils.get_url,
			'format': frappe.format_value,
			"format_value": frappe.format_value,
			'date_format': date_format,
			"format_date": frappe.utils.data.global_date_format,
			"form_dict": getattr(frappe.local, 'form_dict', {}),
			"get_hooks": frappe.get_hooks,
			"get_meta": frappe.get_meta,
			"get_doc": frappe.get_doc,
			"get_cached_doc": frappe.get_cached_doc,
			"get_list": frappe.get_list,
			"get_all": frappe.get_all,
			'get_system_settings': frappe.get_system_settings,
			"utils": datautils,
			"user": user,
			"get_fullname": frappe.utils.get_fullname,
			"get_gravatar": frappe.utils.get_gravatar_url,
			"full_name": frappe.local.session.data.full_name if getattr(frappe.local, "session", None) else "Guest",
			"render_template": frappe.render_template,
			"request": getattr(frappe.local, 'request', {}),
			'session': frappe._dict(
				user =  user,
				csrf_token = frappe.local.session.data.csrf_token if getattr(frappe.local, "session", None) else ''
			),
			"socketio_port": frappe.conf.socketio_port,
		}),
		style = frappe._dict(
			border_color = '#d1d8dd'
		),
		get_toc =  get_toc,
		get_next_link = get_next_link,
		_ =  frappe._,
		get_shade = get_shade,
		scrub =  scrub,
		guess_mimetype = mimetypes.guess_type,
		html2text = html2text,
		json = json,
		dev_server =  1 if os.environ.get('DEV_SERVER', False) else 0
	)

	if not frappe.flags.in_setup_help:
		out.get_visible_columns = get_visible_columns
		out.frappe.date_format = date_format
		out.frappe.db = frappe._dict(
			get_value = frappe.db.get_value,
			get_single_value = frappe.db.get_single_value,
			get_default = frappe.db.get_default,
			escape = frappe.db.escape,
		)

	return out
