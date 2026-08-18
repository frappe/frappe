import os
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class NanoBenchmark:
	"""This class can be used to represent benchmarks that measure sub-milisecond operations.

	These measurement are affected by function call overhead, so instead directly executing the
	statement avoids it."""

	statement: str
	setup: str = "pass"
	teardown: str = "pass"
	globals: dict[str, Any] | None = None


# Copied from frappe/utils/change_log.py
# Modifications: Doesn't ignore errors and returns full commit id
def get_app_last_commit_ref(app):
	with open(os.devnull, "wb") as null_stream:
		result = subprocess.check_output(
			f"git -C ../apps/{app} rev-parse HEAD",
			shell=True,
			stdin=null_stream,
			stderr=null_stream,
		).decode()
	result = result.strip()
	return result


def get_app_last_commit_date(app):
	with open(os.devnull, "wb") as null_stream:
		result = subprocess.check_output(
			f"git -C ../apps/{app} show --no-patch --format=%ci HEAD",
			shell=True,
			stdin=null_stream,
			stderr=null_stream,
		).decode()
	result = result.strip()
	return result
