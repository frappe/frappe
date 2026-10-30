"""
Post a "Develop status" commit status on open develop pull requests, and a "Desk-v2 status" on
desk-v2 ones: failing while the latest full server or UI run on that branch failed, unless the
pull request has the fix label and those suites passed on it.

Usage:
    python develop_status.py refresh       # every open develop and desk-v2 pull request
    python develop_status.py pr <number>   # one pull request
    python develop_status.py wait <number> # one pull request, until its fix tests finish
    python develop_status.py commit <sha>  # the pull requests whose head is this commit
    python develop_status.py start [all] [branch]  # start the suites the branch's new commits need, or both branches'
"""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from functools import cache

from roulette import FIX_DEVELOP_LABEL as FIX_LABEL
from roulette import is_ci, is_desk_frontend, is_docs, is_frontend_code, is_server_side_code

REPO = os.environ["GITHUB_REPOSITORY"]
BRANCHES = ("develop", "desk-v2")
SUITES = {"server-tests.yml": "Server Success", "ui-tests.yml": "UI Success"}
TEST_JOBS = {"server-tests.yml": "Integration", "ui-tests.yml": "UI Test"}
STATUS_JOB = "Update Develop Status"


def gh(*args):
	return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def gate_conclusion(run, gate_job):
	"""The gate job's result, or None for a run that hasn't finished or was cancelled. A re-run still going counts as its previous attempt."""
	path = f"repos/{REPO}/actions/runs/{run['id']}"
	if run["status"] != "completed" and run["run_attempt"] > 1:
		path += f"/attempts/{run['run_attempt'] - 1}"
	jobs = gh(f"{path}/jobs")["jobs"]
	if any(job["conclusion"] == "cancelled" and job["name"] != STATUS_JOB for job in jobs):
		return None
	return next((job["conclusion"] for job in jobs if job["name"] == gate_job), None)


def suite_result(run, workflow):
	"""("success", "failure" or "pending", failed job url) for a suite run, counting it passed only when its test jobs ran."""
	if not run or run["status"] != "completed":
		return "pending", ""
	jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs")["jobs"]
	if any(job["conclusion"] == "cancelled" and job["name"] != STATUS_JOB for job in jobs):
		return "pending", ""
	failed = next((job["html_url"] for job in jobs if job["conclusion"] == "failure"), None)
	if failed:
		return "failure", failed
	tests = [job["conclusion"] for job in jobs if job["name"].startswith(TEST_JOBS[workflow])]
	gate = next((job["conclusion"] for job in jobs if job["name"] == SUITES[workflow]), None)
	if gate == "success" and tests and all(c == "success" for c in tests):
		return "success", ""
	return "pending", ""


def pr_run(workflow, pr):
	"""The latest test run of this pull request, skipping runs of another pull request on the same commit."""
	sha = pr["head"]["sha"]
	runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?head_sha={sha}&event=pull_request")
	for run in runs["workflow_runs"]:
		if not run["pull_requests"] or any(p["number"] == pr["number"] for p in run["pull_requests"]):
			return run


def fixed_after(workflow, failed_run, branch):
	"""Was a fixes-develop pull request merged into the branch after this failure, with this suite passing in full on it?"""
	query = f"repo:{REPO} is:pr is:merged base:{branch} label:{FIX_LABEL} merged:>={failed_run['created_at']}"
	for item in gh("-X", "GET", "search/issues", "-f", f"q={query}")["items"]:
		pr = gh(f"repos/{REPO}/pulls/{item['number']}")
		if suite_result(pr_run(workflow, pr), workflow)[0] == "success":
			return True
	return False


def failed_job_url(run, gate_job):
	"""The first failed job, whose log shows the error, or the run if none failed."""
	jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs")["jobs"]
	failed = (job["html_url"] for job in jobs if job["conclusion"] == "failure" and job["name"] != gate_job)
	return next(failed, run["html_url"])


@cache
def failing_suites(branch="develop"):
	"""{workflow: failed job url} for each suite whose latest finished full run on the branch failed."""
	failing = {}
	for workflow, gate_job in SUITES.items():
		runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?branch={branch}")
		for run in runs["workflow_runs"]:
			if run["event"] not in ("schedule", "workflow_dispatch"):
				continue
			conclusion = gate_conclusion(run, gate_job)
			if conclusion == "failure" and not fixed_after(workflow, run, branch):
				failing[workflow] = failed_job_url(run, gate_job)
			if conclusion in ("success", "failure"):
				break
	return failing


def branch_state(branch):
	"""(passing, url of a failed run)."""
	failing = failing_suites(branch)
	return not failing, next(iter(failing.values()), "")


def fix_status(pr):
	"""A fix pull request can merge only once every suite failing on its branch passed on it."""
	branch = pr["base"]["ref"]
	results = [suite_result(pr_run(workflow, pr), workflow) for workflow in failing_suites(branch)]
	failed = next((url for state, url in results if state == "failure"), None)
	if failed:
		return "failure", f"{branch} is failing and the fix failed its tests", failed
	if any(state == "pending" for state, _ in results):
		return "pending", f"{branch} is failing, testing the fix", ""
	return "success", f"{branch} is failing, the fix passed its tests", ""


def post(pr, started=None):
	"""Set the pull request's branch status and return its state."""
	branch = pr["base"]["ref"]
	context = f"{branch.capitalize()} status"
	passing, url = branch_state(branch)
	if passing:
		state, description = "success", f"{branch} is passing"
	elif any(label["name"] == FIX_LABEL for label in pr["labels"]):
		state, description, url = fix_status(pr)
	else:
		state, description = "failure", f"{branch} is failing, see the failed run"

	sha = pr["head"]["sha"]
	current = next(
		(s for s in gh(f"repos/{REPO}/commits/{sha}/status")["statuses"] if s["context"] == context), None
	)
	if current and (current["state"], current["description"]) == (state, description):
		return state
	if current and started and current["updated_at"] >= started:
		return current["state"]

	fields = ["-f", f"state={state}", "-f", f"context={context}", "-f", f"description={description}"]
	if url:
		fields += ["-f", f"target_url={url}"]
	gh("-X", "POST", f"repos/{REPO}/statuses/{sha}", *fields)
	print(f"#{pr['number']}: {state}")
	time.sleep(1)
	return state


def needs_suite(workflow, files, branch="develop"):
	"""Can these changed files affect this suite? The pull request plan's rules in roulette.py, except that
	desk-v2's frontend counts for its server suite: desk-v2 pull requests skip the server tests that read it."""
	if files is None or any(is_ci(f) for f in files):
		return True
	if workflow == "server-tests.yml":
		return any(
			not (is_docs(f) or is_frontend_code(f))
			or (branch == "desk-v2" and is_desk_frontend(f) and not is_docs(f))
			for f in files
		)
	return any(not (is_docs(f) or is_server_side_code(f)) for f in files)


def start(force=False, branches=BRANCHES):
	for branch in branches:
		start_branch(branch, force)


def start_branch(branch, force):
	head = gh(f"repos/{REPO}/commits/{branch}")["sha"]
	for workflow in SUITES:
		runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?branch={branch}")["workflow_runs"]
		last = next((run for run in runs if run["event"] in ("schedule", "workflow_dispatch")), None)
		if not force and last:
			if last["status"] != "completed" or last["head_sha"] == head:
				continue
			changes = gh(f"repos/{REPO}/compare/{last['head_sha']}...{head}")["files"]
			files = [path for f in changes for path in (f["filename"], f.get("previous_filename")) if path]
			if not needs_suite(workflow, None if len(changes) >= 300 else files, branch):
				print(f"{workflow} on {branch}: no changes it can see since {last['head_sha'][:7]}")
				continue
		subprocess.run(["gh", "workflow", "run", workflow, "--repo", REPO, "--ref", branch], check=True)
		print(f"{workflow} on {branch}: started on {head[:7]}")


if __name__ == "__main__":
	if sys.argv[1] == "start":
		start("all" in sys.argv[2:], [b for b in sys.argv[2:] if b in BRANCHES] or BRANCHES)
		sys.exit()

	if sys.argv[1] == "wait":
		while post(gh(f"repos/{REPO}/pulls/{sys.argv[2]}")) == "pending":
			time.sleep(60)
			failing_suites.cache_clear()
		sys.exit()

	if sys.argv[1] == "pr":
		post(gh(f"repos/{REPO}/pulls/{sys.argv[2]}"))
	elif sys.argv[1] == "commit":
		query = f"repo:{REPO} is:pr is:open sha:{sys.argv[2]}"
		for item in gh("-X", "GET", "search/issues", "-f", f"q={query}")["items"]:
			pr = gh(f"repos/{REPO}/pulls/{item['number']}")
			if pr["head"]["sha"] == sys.argv[2] and pr["base"]["ref"] in BRANCHES:
				post(pr)
	else:
		for branch in BRANCHES:
			print(f"{branch}: {branch_state(branch)}")
			started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
			pulls = f"repos/{REPO}/pulls?base={branch}&state=open&per_page=100"
			for page in gh("--paginate", "--slurp", pulls):
				for pr in page:
					post(pr, started)
