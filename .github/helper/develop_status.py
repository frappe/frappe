"""
Post a "Develop status" commit status on open develop pull requests: failing while the latest
full server or UI run on develop failed, unless the pull request has the fix label.

Usage:
    python develop_status.py refresh       # every open develop pull request
    python develop_status.py pr <number>   # one pull request
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from functools import cache

from roulette import FIX_DEVELOP_LABEL as FIX_LABEL

REPO = os.environ["GITHUB_REPOSITORY"]
CONTEXT = "Develop status"
SUITES = {"server-tests.yml": "Server Success", "ui-tests.yml": "UI Success"}


def gh(*args):
	return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


@cache
def failing_suites():
	"""{workflow: failed run url} for each suite whose latest finished full run on develop failed."""
	failing = {}
	for workflow, gate_job in SUITES.items():
		runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?branch=develop&status=completed")
		for run in runs["workflow_runs"]:
			if run["event"] not in ("schedule", "workflow_dispatch"):
				continue
			jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs")["jobs"]
			conclusion = next((job["conclusion"] for job in jobs if job["name"] == gate_job), None)
			if conclusion == "failure":
				failing[workflow] = run["html_url"]
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


if __name__ == "__main__":
	develop = develop_state()
	print(f"develop: {develop}")
	if sys.argv[1] == "pr":
		post(gh(f"repos/{REPO}/pulls/{sys.argv[2]}"), develop)
	else:
		started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
		for page in gh("--paginate", "--slurp", f"repos/{REPO}/pulls?base=develop&state=open&per_page=100"):
			for pr in page:
				post(pr, develop, started)
