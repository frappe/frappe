# Copyright (c) 2015, Maxwell Morais and contributors
# License: MIT. See LICENSE

import cgitb
import datetime
import functools
import inspect
import json
import linecache
import os
import sys
import traceback

import frappe
from frappe.utils import cstr, encode

EXCLUDE_EXCEPTIONS = (
	frappe.AuthenticationError,
	frappe.CSRFTokenError,  # CSRF covers OAuth too
	frappe.SecurityException,
	frappe.InReadOnlyMode,
)

LDAP_BASE_EXCEPTION = "LDAPException"


def _is_ldap_exception(e):
	"""Check if exception is from LDAP library.

	This is a hack but ensures that LDAP is not imported unless it's required. This is tested in
	unittests in case the exception changes in future.
	"""

	for t in type(e).__mro__:
		if t.__name__ == LDAP_BASE_EXCEPTION:
			return True

	return False


def make_error_snapshot(exception):
	if frappe.conf.disable_error_snapshot:
		return

	if isinstance(exception, EXCLUDE_EXCEPTIONS) or _is_ldap_exception(exception):
		return

	logger = frappe.logger(with_more_info=True)

	try:
		error_id = "{timestamp:s}-{ip:s}-{hash:s}".format(
			timestamp=cstr(datetime.datetime.now()),
			ip=frappe.local.request_ip or "127.0.0.1",
			hash=frappe.generate_hash(length=3),
		)
		snapshot_folder = get_error_snapshot_path()
		frappe.create_folder(snapshot_folder)

		snapshot_file_path = os.path.join(snapshot_folder, f"{error_id}.json")
		snapshot = get_snapshot(exception)

		with open(encode(snapshot_file_path), "wb") as error_file:
			error_file.write(encode(frappe.as_json(snapshot)))

		logger.error(f"New Exception collected with id: {error_id}")

	except Exception as e:
		logger.error(f"Could not take error snapshot: {e}", exc_info=True)


def get_snapshot(exception, context=10):
	import pydoc

	"""
	Return a dict describing a given traceback (based on cgitb.text)
	"""

	etype, evalue, etb = sys.exc_info()
	if isinstance(etype, type):
		etype = etype.__name__

	# creates a snapshot dict with some basic information

	s = {
		"pyver": "Python {version:s}: {executable:s} (prefix: {prefix:s})".format(
			version=sys.version.split(maxsplit=1)[0], executable=sys.executable, prefix=sys.prefix
		),
		"timestamp": cstr(datetime.datetime.now()),
		"traceback": traceback.format_exc(),
		"frames": [],
		"etype": cstr(etype),
		"evalue": cstr(repr(evalue)),
		"exception": {},
		"locals": {},
	}

	# start to process frames
	records = inspect.getinnerframes(etb, 5)

	for frame, file, lnum, func, lines, index in records:
		file = file and os.path.abspath(file) or "?"
		args, varargs, varkw, locals = inspect.getargvalues(frame)
		call = ""

		if func != "?":
			call = inspect.formatargvalues(
				args, varargs, varkw, locals, formatvalue=lambda value: f"={pydoc.text.repr(value)}"
			)

		# basic frame information
		f = {"file": file, "func": func, "call": call, "lines": {}, "lnum": lnum}

		def reader(lnum=[lnum]):  # noqa
			try:
				# B023: function is evaluated immediately, binding not necessary
				return linecache.getline(file, lnum[0])  # noqa: B023
			finally:
				lnum[0] += 1

		vars = cgitb.scanvars(reader, frame, locals)

		# if it is a view, replace with generated code
		# if file.endswith('html'):
		# 	lmin = lnum > context and (lnum - context) or 0
		# 	lmax = lnum + context
		# 	lines = code.split("\n")[lmin:lmax]
		# 	index = min(context, lnum) - 1

		if index is not None:
			i = lnum - index
			for line in lines:
				f["lines"][i] = line.rstrip()
				i += 1

		# dump local variable (referenced in current line only)
		f["dump"] = {}
		for name, where, value in vars:
			if name in f["dump"]:
				continue
			if value is not cgitb.__UNDEF__:
				if where == "global":
					name = f"global {name:s}"
				elif where != "local":
					name = where + " " + name.split(".")[-1]
				f["dump"][name] = pydoc.text.repr(value)
			else:
				f["dump"][name] = "undefined"

		s["frames"].append(f)

	# add exception type, value and attributes
	if isinstance(evalue, BaseException):
		for name in dir(evalue):
			if name != "messages" and not name.startswith("__"):
				value = pydoc.text.repr(getattr(evalue, name))
				s["exception"][name] = encode(value)

	# add all local values (of last frame) to the snapshot
	for name, value in locals.items():
		s["locals"][name] = value if isinstance(value, str) else pydoc.text.repr(value)

	return s


def collect_error_snapshots():
	"""Scheduled task to collect error snapshots from files and push into Error Snapshot table"""
	if frappe.conf.disable_error_snapshot:
		return

	try:
		path = get_error_snapshot_path()
		if not os.path.exists(path):
			return

		for fname in os.listdir(path):
			fullpath = os.path.join(path, fname)

			try:
				with open(fullpath) as filedata:
					data = json.load(filedata)

			except ValueError:
				# empty file
				os.remove(fullpath)
				continue

			for field in ["locals", "exception", "frames"]:
				data[field] = frappe.as_json(data[field])

			doc = frappe.new_doc("Error Snapshot")
			doc.update(data)
			doc.save()

			frappe.db.commit()

			os.remove(fullpath)

		clear_old_snapshots()

	except Exception as e:
		make_error_snapshot(e)

		# prevent creation of unlimited error snapshots
		raise


def clear_old_snapshots():
	"""Clear snapshots that are older than a month"""
	from frappe.query_builder import DocType, Interval
	from frappe.query_builder.functions import Now

	ErrorSnapshot = DocType("Error Snapshot")
	frappe.db.delete(ErrorSnapshot, filters=(ErrorSnapshot.creation < (Now() - Interval(months=1))))

	path = get_error_snapshot_path()
	today = datetime.datetime.now()

	for file in os.listdir(path):
		p = os.path.join(path, file)
		ctime = datetime.datetime.fromtimestamp(os.path.getctime(p))
		if (today - ctime).days > 31:
			os.remove(os.path.join(path, p))


def get_error_snapshot_path():
	return frappe.get_site_path("error-snapshots")


def get_default_args(func):
	"""Get default arguments of a function from its signature."""
	signature = inspect.signature(func)
	return {
		k: v.default for k, v in signature.parameters.items() if v.default is not inspect.Parameter.empty
	}


def raise_error_on_no_output(error_message, error_type=None, keep_quiet=None):
	"""Decorate any function to throw error incase of missing output.

	TODO: Remove keep_quiet flag after testing and fixing sendmail flow.

	:param error_message: error message to raise
	:param error_type: type of error to raise
	:param keep_quiet: control error raising with external factor.
	:type error_message: str
	:type error_type: Exception Class
	:type keep_quiet: function

	>>> @raise_error_on_no_output("Ingradients missing")
	... def get_indradients(_raise_error=1): return
	...
	>>> get_ingradients()
	`Exception Name`: Ingradients missing
	"""

	def decorator_raise_error_on_no_output(func):
		@functools.wraps(func)
		def wrapper_raise_error_on_no_output(*args, **kwargs):
			response = func(*args, **kwargs)
			if callable(keep_quiet) and keep_quiet():
				return response

			default_kwargs = get_default_args(func)
			default_raise_error = default_kwargs.get("_raise_error")
			raise_error = kwargs.get("_raise_error") if "_raise_error" in kwargs else default_raise_error

			if (not response) and raise_error:
				frappe.throw(error_message, error_type or Exception)
			return response

		return wrapper_raise_error_on_no_output

	return decorator_raise_error_on_no_output
