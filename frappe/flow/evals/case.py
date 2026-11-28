# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Eval cases: one Python file each in `apps/<app>/evals/`, with ASK, USER, setup() and check(run)."""

import runpy
import sys
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click

import frappe

REQUIRED = ("ASK", "USER", "setup", "check")


@dataclass
class Case:
	name: str
	ask: str
	user: str
	setup: Callable[[], Any]
	check: Callable[["Run"], None]
	path: list | Callable[[Any], list] | None = None


@dataclass
class Call:
	name: str
	args: dict
	result: str | None = None


@dataclass
class Run:
	"""What `check(run)` reads."""

	reply: str = ""
	tool_calls: list[Call] = field(default_factory=list)
	usage: dict = field(default_factory=dict)
	setup: Any = None

	def called(self, name: str, **args: Any) -> bool:
		"""Whether a call to `name` was made with every given argument at its top level."""
		return any(
			call.name == name and all(call.args.get(key) == value for key, value in args.items())
			for call in self.tool_calls
		)


def load_cases(app: str, only: tuple[str, ...] = ()) -> list[Case]:
	folder = Path(frappe.get_app_source_path(app, "evals"))
	files = sorted(path for path in folder.glob("*.py") if not path.name.startswith("_"))
	if not files:
		raise click.ClickException(f"No cases in {folder}.")
	if str(folder) not in sys.path:
		sys.path.insert(0, str(folder))  # so a case can import a helper such as _people.py
	names = [path.stem for path in files]
	if unknown := [name for name in only if name not in names]:
		raise click.ClickException(f"No case named {', '.join(unknown)}. Cases: {', '.join(names)}.")
	cases = []
	for path in files:
		if only and path.stem not in only:
			continue
		try:
			found = runpy.run_path(str(path))
		except Exception as exc:
			raise click.ClickException(f"{path} cannot be imported: {last_line(exc)}") from exc
		if missing := [name for name in REQUIRED if name not in found]:
			raise click.ClickException(f"{path} has no {', '.join(missing)}.")
		if found["USER"] in ("Administrator", "Guest"):
			raise click.ClickException(f"{path}: USER must be a normal user, not {found['USER']}.")
		cases.append(
			Case(path.stem, found["ASK"], found["USER"], found["setup"], found["check"], found.get("PATH"))
		)
	return cases


@contextmanager
def as_user(user: str):
	"""Act as `user`, and as Administrator again after, whatever the code inside switched to."""
	frappe.set_user(user)  # a bench command acts as the case's user; nosemgrep: frappe-setuser
	try:
		yield
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser


def run_setup(case: Case) -> Any:
	"""The case's setup() as Administrator, committed, since every tool call commits on its own."""
	with as_user("Administrator"):
		value = case.setup()
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
	if not frappe.db.get_value("User", case.user, "enabled"):
		raise frappe.ValidationError(f"USER {case.user} does not exist or is disabled after setup()")
	return value


def last_line(exc: BaseException) -> str:
	return traceback.format_exception_only(exc)[-1].strip()
