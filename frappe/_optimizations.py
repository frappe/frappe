"""This file houses all Frappe specific optimizations and hooks that run on startup or during fork.

Warning: This entire file is private as indicated by `_` prefix in filename.
"""

import faulthandler
import gc
import io
import os
import re
import signal
import sys


def optimize_all():
	"""Single entry point to enable all optimizations at right time automatically."""

	# Note:
	# - This function is ALWAYS executed as soon as `import frappe` ends.
	# - Any deferred work should be deferred using os module's fork hooks.
	# - Respect configurations using environement variables.
	# - fork hooks can not be unregistered, so care should be taken to execute them only when they
	#   make sense.
	optimize_regex_cache()
	optimize_gc_parameters()
	optimize_gc_for_copy_on_write()


def optimize_gc_parameters():
	from frappe.utils import sbool

	if not bool(sbool(os.environ.get("FRAPPE_TUNE_GC", True))):
		return

	# generational GC gets triggered after certain allocs (g0) which is 700 by default.
	# This number is quite small for frappe where a single query can potentially create 700+
	# objects easily.
	# Bump this number higher, this will make GC less aggressive but that improves performance of
	# everything else.
	g0, g1, g2 = gc.get_threshold()  # defaults are 700, 10, 10.
	gc.set_threshold(g0 * 10, g1 * 2, g2 * 2)


def optimize_regex_cache():
	# Remove references to pattern that are pre-compiled and loaded to global scopes.
	# Leave that cache for dynamically generated regex.
	os.register_at_fork(before=re.purge)


def preload_modules():
	"""Import modules before forking so that workers share their memory.

	These modules are used on the hot path of most requests but are not imported by
	``import frappe.app``. Importing them here lets forked workers share the memory
	through copy-on-write instead of each paying the import cost after the fork.

	Eager import by default.
	"""
	if os.environ.get("FRAPPE_PRELOAD_MODULES", "1").strip().lower() in ("0", "false"):
		return

	import gettext

	import babel
	import babel.dates
	import bs4
	import nh3
	import num2words
	import pydantic

	import frappe.boot
	import frappe.client
	import frappe.core.doctype.file.file
	import frappe.core.doctype.user.user
	import frappe.database.query
	import frappe.desk.desktop  # workspace
	import frappe.desk.form.save
	import frappe.model.db_query
	import frappe.query_builder
	import frappe.utils.background_jobs  # Enqueue is very common
	import frappe.utils.data  # common utils
	import frappe.utils.jinja  # web page rendering
	import frappe.utils.jinja_globals
	import frappe.utils.redis_wrapper  # Exact redis_wrapper
	import frappe.utils.safe_exec
	import frappe.utils.typing_validations  # any whitelisted method uses this
	import frappe.website.path_resolver  # all the page types and resolver
	import frappe.website.router  # Website router
	import frappe.website.website_generator  # web page doctypes


def preload_database_drivers():
	"""Import database drivers before forking so that workers share their memory.

	`FRAPPE_PRELOAD_DATABASE_DRIVERS` takes a comma separated list of driver names, e.g.
	"mariadb,postgres". Blank loads mariadb, "none" loads nothing.
	"""
	value = os.environ.get("FRAPPE_PRELOAD_DATABASE_DRIVERS", "").strip().lower() or "mariadb"
	if value == "none":
		return

	drivers = {driver.strip() for driver in value.split(",") if driver.strip()}

	if "mariadb" in drivers:
		import frappe.database.mariadb.mysqlclient

	if "postgres" in drivers:
		import frappe.database.postgres.database

	if "sqlite" in drivers:
		import frappe.database.sqlite.database


def register_fault_handler():
	# Some libraries monkey patch stderr, we need actual fd
	if isinstance(sys.__stderr__, io.TextIOWrapper):
		faulthandler.enable()
		faulthandler.register(signal.SIGUSR1, file=sys.__stderr__)


def optimize_gc_for_copy_on_write():
	from frappe.utils import sbool

	if not bool(sbool(os.environ.get("FRAPPE_TUNE_GC", True))):
		return

	os.register_at_fork(before=freeze_gc)


_gc_frozen = False


def freeze_gc():
	global _gc_frozen
	if _gc_frozen:
		return
	# Both Gunicorn and RQ use forking to spawn workers. In an ideal world, the fork should be sharing
	# most of the memory if there are no writes made to data because of Copy on Write, however,
	# python's GC is not CoW friendly and writes to data even if user-code doesn't. Specifically, the
	# generational GC which stores and mutates every python object: `PyGC_Head`
	#
	# Calling gc.freeze() moves all the objects imported so far into permanant generation and hence
	# doesn't mutate `PyGC_Head`
	#
	# Refer to issue for more info: https://github.com/frappe/frappe/issues/18927
	gc.collect()
	gc.freeze()
	# RQ workers constantly fork, there' no benefit in doing this in that case.
	_gc_frozen = True
