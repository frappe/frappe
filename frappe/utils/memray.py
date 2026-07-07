# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import subprocess
import threading
from datetime import datetime
from enum import Enum
from functools import wraps

import frappe
from frappe.recorder import RecorderConfig

try:
	import memray
except ImportError:
	memray = None


class MemrayModule(Enum):
	API = "api"
	WEBSITE = "website"
	RPC = "rpc"
	BACKGROUND_JOBS = "background_jobs"
	SCHEDULER = "scheduler"
	CLI = "cli"


_memray_lock = threading.Lock()


def _memray_enabled():
	conf = getattr(frappe.local, "conf", None)
	if not conf:
		return False

	if getattr(frappe.conf, "memray_profile", False):
		return True

	if RecorderConfig.retrieve() is not None:
		return RecorderConfig.retrieve().memray_profile

	return False


def _enabled_modules():
	if RecorderConfig.retrieve() is not None and RecorderConfig.retrieve().memray_profile:
		if hasattr(RecorderConfig.retrieve(), "memray_modules"):
			return [m.strip() for m in RecorderConfig.retrieve().memray_modules.split(",")]

	return getattr(frappe.conf, "memray_modules", [])


def _generate_and_replace_flamegraph(dump_path):
	flamegraph_path = os.path.splitext(dump_path)[0] + "-flamegraph.html"

	try:
		subprocess.run(
			["memray", "flamegraph", "-o", flamegraph_path, dump_path],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.PIPE,
			text=True,
			check=True,
		)
	except subprocess.CalledProcessError as e:
		frappe.logger().error(
			"Failed to generate flamegraph: %s",
			e.stderr.strip(),
		)
		return None
	except Exception:
		frappe.logger().exception("Failed to generate flamegraph")
		return None

	try:
		os.remove(dump_path)
	except OSError:
		frappe.logger().warning("Generated flamegraph but failed to remove %s", dump_path)

	return flamegraph_path


def memray_profile(module: MemrayModule):
	def decorator(func):
		@wraps(func)
		def wrapper(*args, **kwargs):
			if not _memray_enabled():
				return func(*args, **kwargs)

			if memray is None:
				raise RuntimeError("Memray profiling enabled but Memray is not installed")

			if module.value not in _enabled_modules():
				return func(*args, **kwargs)

			filename = f"memray-{module.value}-{datetime.now():%Y%m%d-%H%M%S-%f}-{os.getpid()}"

			dump_path = frappe.get_site_path("profiler", "memray", f"{filename}.bin")
			os.makedirs(os.path.dirname(dump_path), exist_ok=True)

			if not _memray_lock.acquire(blocking=False):
				return func(*args, **kwargs)

			try:
				frappe.logger().info("Memray profiling started for %s: %s", module.value, dump_path)
				with memray.Tracker(
					destination=memray.FileDestination(dump_path, overwrite=True),
					follow_fork=True,
				):
					return func(*args, **kwargs)
			finally:
				_memray_lock.release()

				flamegraph_path = _generate_and_replace_flamegraph(dump_path)
				if flamegraph_path is not None:
					frappe.local.memray_capture = os.path.abspath(flamegraph_path)
					frappe.logger().info(
						"Generated memray flamegraph for %s: %s",
						module.value,
						frappe.local.memray_capture,
					)

		return wrapper

	return decorator
