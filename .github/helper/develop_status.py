"""
Post a "Develop status" commit status on open develop pull requests: failing while the latest
full server or UI run on develop failed, unless the pull request has the fix label.

Usage:
    python develop_status.py refresh       # every open develop pull request
    python develop_status.py pr <number>   # one pull request
    python develop_status.py start [all]   # start the suites the new develop commits need
"""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from functools import cache

from roulette import FIX_DEVELOP_LABEL as FIX_LABEL
from roulette import is_ci, is_docs, is_frontend_code, is_server_side_code

REPO = os.environ["GITHUB_REPOSITORY"]
CONTEXT = "Develop status"
SUITES = {"server-tests.yml": "Server Success", "ui-tests.yml": "UI Success"}
TEST_JOBS = {"server-tests.yml": "Integration", "ui-tests.yml": "UI Test"}


def gh(*args):
	return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def gate_conclusion(run, gate_job):
	"""The gate job's result, or None for a run that hasn't finished or was cancelled."""
	jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs")["jobs"]
	if any(job["conclusion"] == "cancelled" for job in jobs):
		return None
	return next((job["conclusion"] for job in jobs if job["name"] == gate_job), None)


def suite_passed(run, workflow):
	"""Did the suite pass with its test jobs actually run? The gate job alone also passes when they are skipped."""
	jobs = {
		job["name"]: job["conclusion"] for job in gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs")["jobs"]
	}
	tests = [conclusion for name, conclusion in jobs.items() if name.startswith(TEST_JOBS[workflow])]
	return jobs.get(SUITES[workflow]) == "success" and bool(tests) and all(c == "success" for c in tests)


def fixed_after(workflow, failed_run):
	"""Was a fixes-develop pull request merged into develop after this failure, with this suite passing in full on it?"""
	query = f"repo:{REPO} is:pr is:merged base:develop label:{FIX_LABEL} merged:>={failed_run['created_at']}"
	for item in gh("-X", "GET", "search/issues", "-f", f"q={query}")["items"]:
		sha = gh(f"repos/{REPO}/pulls/{item['number']}")["head"]["sha"]
		runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?head_sha={sha}&event=pull_request")
		run = next(iter(runs["workflow_runs"]), None)
		if run and run["run_started_at"] > failed_run["created_at"] and suite_passed(run, workflow):
			return True
	return False


def failed_job_url(run, gate_job):
	"""The first failed job, whose log shows the error, or the run if none failed."""
	jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs")["jobs"]
	failed = (job["html_url"] for job in jobs if job["conclusion"] == "failure" and job["name"] != gate_job)
	return next(failed, run["html_url"])


@cache
def failing_suites():
	"""{workflow: failed job url} for each suite whose latest finished full run on develop failed."""
	failing = {}
	for workflow, gate_job in SUITES.items():
		runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?branch=develop")
		for run in runs["workflow_runs"]:
			if run["event"] not in ("schedule", "workflow_dispatch"):
				continue
			conclusion = gate_conclusion(run, gate_job)
			if conclusion == "failure" and not fixed_after(workflow, run):
				failing[workflow] = failed_job_url(run, gate_job)
			if conclusion in ("success", "failure"):
				break
	return failing


def develop_state():
	"""(passing, url of a failed run)."""
	failing = failing_suites()
	return not failing, next(iter(failing.values()), "")


def post(pr, develop, started=None):
	passing, url = develop
	if passing:
		state, description = "success", "develop is passing"
	elif any(label["name"] == FIX_LABEL for label in pr["labels"]):
		state, description = "success", f"develop is failing, allowed by the {FIX_LABEL} label"
	else:
		state, description = "failure", "develop is failing, see the failed run"

	sha = pr["head"]["sha"]
	current = next(
		(s for s in gh(f"repos/{REPO}/commits/{sha}/status")["statuses"] if s["context"] == CONTEXT), None
	)
	if current and (current["state"], current["description"]) == (state, description):
		return
	if current and started and current["updated_at"] >= started:
		return

	fields = ["-f", f"state={state}", "-f", f"context={CONTEXT}", "-f", f"description={description}"]
	if url:
		fields += ["-f", f"target_url={url}"]
	gh("-X", "POST", f"repos/{REPO}/statuses/{sha}", *fields)
	print(f"#{pr['number']}: {state}")
	time.sleep(1)


def needs_suite(workflow, files):
	"""Can these changed files affect this suite? Same rules as the pull request plan in roulette.py."""
	if files is None or any(is_ci(f) for f in files):
		return True
	if workflow == "server-tests.yml":
		return any(not (is_docs(f) or is_frontend_code(f)) for f in files)
	return any(not (is_docs(f) or is_server_side_code(f)) for f in files)


def start(force=False):
	head = gh(f"repos/{REPO}/commits/develop")["sha"]
	for workflow in SUITES:
		runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?branch=develop")["workflow_runs"]
		last = next((run for run in runs if run["event"] in ("schedule", "workflow_dispatch")), None)
		if not force and last:
			if last["status"] != "completed" or last["head_sha"] == head:
				continue
			changes = gh(f"repos/{REPO}/compare/{last['head_sha']}...{head}")["files"]
			files = [path for f in changes for path in (f["filename"], f.get("previous_filename")) if path]
			if not needs_suite(workflow, None if len(changes) >= 300 else files):
				print(f"{workflow}: no changes it can see since {last['head_sha'][:7]}")
				continue
		subprocess.run(["gh", "workflow", "run", workflow, "--repo", REPO, "--ref", "develop"], check=True)
		print(f"{workflow}: started on {head[:7]}")


if __name__ == "__main__":
	if sys.argv[1] == "start":
		start(force=sys.argv[2:] == ["all"])
		sys.exit()

	develop = develop_state()
	print(f"develop: {develop}")
	if sys.argv[1] == "pr":
		post(gh(f"repos/{REPO}/pulls/{sys.argv[2]}"), develop)
	else:
		started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
		for page in gh("--paginate", "--slurp", f"repos/{REPO}/pulls?base=develop&state=open&per_page=100"):
			for pr in page:
				post(pr, develop, started)
