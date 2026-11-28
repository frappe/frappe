# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from pathlib import Path

import click

import frappe
from frappe.commands import get_site, pass_context

only_option = click.option("--only", multiple=True, help="Only this case; may be given more than once.")


@click.group("flow-eval")
def flow_eval():
	"""Test a change to what Flow's Assistant is given, against an app's cases in apps/<app>/evals/."""


@flow_eval.command("check")
@click.argument("app")
@only_option
@pass_context
def check(context, app, only):
	"""Play each case's PATH through Flow's tools as its user. Calls no model."""
	from frappe.flow.assistant import ASSISTANT_AGENT_NAME
	from frappe.flow.evals.play import play
	from frappe.flow.evals.report import check_table

	results = []
	with _evals(context, app, only) as (cases, snapshot):
		if not frappe.db.exists("Flow Agent", ASSISTANT_AGENT_NAME):
			raise click.ClickException(
				"Flow has no Assistant on this site. Add a Flow Model in Desk; check calls no model, so it needs no key."
			)
		with snapshot:
			for case in cases:
				snapshot.restore()
				results.append(play(case))
	click.echo(check_table(results))
	if any(r["status"] in ("fail", "error") for r in results):
		raise SystemExit(1)


@flow_eval.command("run")
@click.argument("app")
@click.option("--skill", help="Run every case with this skill off and on.")
@click.option("--runs", default=3, show_default=True, type=click.IntRange(1))
@only_option
@click.option("--model", help="A Flow Model; the Assistant's by default.")
@click.option("--label", default="latest", show_default=True, help="Where the runs are saved.")
@click.option(
	"--timeout", default=300, show_default=True, type=click.IntRange(1), help="Seconds a run may take."
)
@click.option(
	"--max-cost", default=1.0, show_default=True, help="Stop once the runs have cost this many dollars."
)
@pass_context
def run(context, app, label, **opts):
	"""Send each case's ask through Flow's chat as its user, on the site's model. Costs model calls."""
	from frappe.flow.evals.chat import Stop, preflight, run_all
	from frappe.flow.evals.report import LABEL, run_table

	if not LABEL.match(label):
		raise click.ClickException("--label may hold letters, digits, - and _ only.")
	if skill := opts["skill"]:
		skill = opts["skill"] = skill if "/" in skill else f"{app}/{skill}"
	with _evals(context, app, opts.pop("only")) as (cases, snapshot):
		if skill and not frappe.db.exists("Flow Skill", skill):
			names = ", ".join(frappe.get_all("Flow Skill", {"app": app}, pluck="name")) or "none"
			raise click.ClickException(f"No Flow Skill {skill}. Skills of {app}: {names}.")
		opts["model"] = preflight(opts["model"])
		model_id = frappe.db.get_value("Flow Model", opts["model"], "model_id")
		root = _root()
		arms = (
			[(root / f"{label}.without", 0), (root / f"{label}.with", 1)] if skill else [(root / label, None)]
		)
		click.echo(
			f"{len(cases) * opts['runs'] * len(arms)} runs on {model_id}, stops at ${opts['max_cost']:.2f}"
		)
		stopped = None
		with snapshot:
			try:
				records = run_all(cases, arms, opts, snapshot)
			except Stop as stop:
				stopped, records = stop, stop.records
	commits = records[0]["commits"] if records else {}
	header = f"flow-eval run {app}{f' --skill {skill}' if skill else ''}    {opts['runs']} runs a case · {model_id}"
	header += "".join(f" · {a} {commits.get(a, '?')}" for a in dict.fromkeys((app, "frappe")))
	by_arm = {folder.name: [r for r in records if r["label"] == folder.name] for folder, _ in arms}
	click.echo(run_table(by_arm, header, advice=True, max_cost=opts["max_cost"]))
	click.echo(
		"saved in " + " and ".join(f"sites/{get_site(context)}/private/flow-evals/{n}" for n in by_arm)
	)
	if stopped:
		click.echo(f"Stopped: {stopped}")
		raise SystemExit(1)


@flow_eval.command("compare")
@click.argument("first")
@click.argument("second")
@pass_context
def compare(context, first, second):
	"""Print the table for two saved runs, such as base and mine, or base and pr.with."""
	from frappe.flow.evals.report import compare

	frappe.init(get_site(context))
	try:
		click.echo(compare(_root(), first, second))
	finally:
		frappe.destroy()


def _root() -> Path:
	return Path(frappe.get_site_path("private", "flow-evals")).resolve()


@contextmanager
def _evals(context, app, only):
	"""Refuse a site not made for evals, lock it, recover a killed command, load the cases, and
	write this checkout's skills, tools and instructions to the site, as migrate does."""
	from frappe.flow.assistant import sync_builtin_assistant
	from frappe.flow.evals.case import load_cases
	from frappe.flow.evals.site import Snapshot, check_site, lock

	frappe.init(get_site(context))
	frappe.connect()
	try:
		check_site()
		with lock():
			if taken := Snapshot().recover():
				click.echo(
					"An earlier flow-eval was stopped part-way. The site is back to how it was when that "
					f"command started, at {taken}. Anything done to the site since, such as a migrate, is undone."
				)
			cases = load_cases(app, tuple(only))
			sync_builtin_assistant()
			frappe.db.commit()  # a bench command has no request to commit its writes; nosemgrep: frappe-manual-commit
			yield cases, Snapshot()
	finally:
		frappe.destroy()
