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
	_optimize_regex_cache()
	_optimize_gc_parameters()
	_optimize_gc_for_copy_on_write()
	_register_fault_handler()
	os.register_at_fork(after_in_child=_register_fault_handler)


def _optimize_gc_parameters():
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


def _optimize_regex_cache():
	# Remove references to pattern that are pre-compiled and loaded to global scopes.
	# Leave that cache for dynamically generated regex.
	os.register_at_fork(before=re.purge)


def _register_fault_handler():
	# Some libraries monkey patch stderr, we need actual fd
	if isinstance(sys.__stderr__, io.TextIOWrapper):
		faulthandler.register(signal.SIGUSR1, file=sys.__stderr__)


def _optimize_gc_for_copy_on_write():
	from frappe.utils import sbool

	if not bool(sbool(os.environ.get("FRAPPE_TUNE_GC", True))):
		return

	os.register_at_fork(before=_freeze_gc)


_gc_frozen = False


def _freeze_gc():
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
