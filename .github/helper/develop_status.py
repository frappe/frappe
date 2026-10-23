"""
Develop status: one commit status on every open develop pull request that fails while the full
server or UI suite is failing on develop, so nothing merges on top of a broken develop.

The full suites run on develop on a schedule (see `develop-status.yml`, which also holds every
setting this script reads). A pull request labelled with the fix label, or a revert by a member,
stays green so the fix can land. Develop is green again as soon as a later full run passes.

Usage:
    python develop_status.py refresh       # every open develop pull request
    python develop_status.py pr <number>   # one pull request
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

REPO = os.environ["GITHUB_REPOSITORY"]
CONTEXT = os.environ.get("STATUS_CONTEXT", "Develop status")
FIX_LABEL = os.environ.get("FIX_LABEL", "fixes-develop")
SUITES = {
	"server-tests.yml": os.environ.get("SERVER_GATE_JOB", "Server Success"),
	"ui-tests.yml": os.environ.get("UI_GATE_JOB", "UI Success"),
}
DEVELOP_EVENTS = ("schedule", "workflow_dispatch")
RETRIES = int(os.environ.get("RETRIES", "1"))
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")


def gh(path):
	return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def gh_pages(path):
	pages = json.loads(subprocess.check_output(["gh", "api", "--paginate", "--slurp", path], text=True))
	return [item for page in pages for item in page]


def suite_history(workflow):
	"""Full runs of a suite on develop, newest first, up to and including the latest green one."""
	runs = gh(f"repos/{REPO}/actions/workflows/{workflow}/runs?branch=develop&per_page=30")["workflow_runs"]
	history = []
	for run in runs:
		if run["event"] not in DEVELOP_EVENTS:
			continue
		if run["status"] != "completed" or retry_pending(run):
			continue
		jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
		gate = next((job for job in jobs if job["name"] == SUITES[workflow]), None)
		if not gate or gate["conclusion"] not in ("success", "failure"):
			continue
		history.append(
			{"sha": run["head_sha"], "passed": gate["conclusion"] == "success", "url": run["html_url"]}
		)
		if history[-1]["passed"]:
			break
	return history


def retry_pending(run):
	"""A failed run that the workflow is about to retry does not count yet."""
	updated = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
	return (
		run["conclusion"] == "failure"
		and run["run_attempt"] <= RETRIES
		and datetime.now(UTC) - updated < timedelta(minutes=30)
	)


def culprits(green_sha, red_sha):
	"""Pull requests merged after the last green run, up to the first red one."""
	if not green_sha:
		return []
	numbers = []
	for commit in gh(f"repos/{REPO}/compare/{green_sha}...{red_sha}")["commits"]:
		title = commit["commit"]["message"].split("\n")[0]
		if len(commit["parents"]) > 1:
			match = re.match(r"Merge pull request #(\d+)", title)
		elif (commit.get("committer") or {}).get("login") == "web-flow":
			match = re.search(r"\(#(\d+)\)$", title)
		else:
			match = None
		if match:
			numbers.append(match.group(1))
	return numbers


def develop_state():
	"""(passing, description, url) for develop, from the latest full run of each suite."""
	latest_url = ""
	for workflow in SUITES:
		history = suite_history(workflow)
		if not history:
			continue
		latest_url = latest_url or history[0]["url"]
		if history[0]["passed"]:
			continue
		failing = [run for run in history if not run["passed"]]
		green = history[-1]["sha"] if history[-1]["passed"] else None
		first_red = failing[-1]["sha"]
		prs = culprits(green, first_red)
		since = f"develop is failing since {first_red[:7]}"
		if prs:
			since += ": " + ", ".join(f"#{n}" for n in prs[:6])
		return False, since, history[0]["url"]
	return True, "develop is passing", latest_url


def pr_state(pr, develop):
	passing, description, url = develop
	if passing:
		return "success", description, url
	if any(label["name"] == FIX_LABEL for label in pr["labels"]):
		return "success", f"Allowed while develop is failing: {FIX_LABEL} label", url
	if pr["title"].startswith('Revert "') and pr["author_association"] in TRUSTED:
		return "success", "Allowed while develop is failing: revert", url
	return "failure", description, url


def post(pr, develop, started=None):
	"""Set the status on the pull request's head; returns whether anything was written.

	With `started`, a status written after that moment is newer than this run's view and is kept.
	"""
	state, description, url = pr_state(pr, develop)
	sha = pr["head"]["sha"]
	description = description[:140]
	current = next(
		(s for s in gh(f"repos/{REPO}/commits/{sha}/status")["statuses"] if s["context"] == CONTEXT), None
	)
	if current and current["state"] == state and current["description"] == description:
		return False
	if current and started and current["updated_at"] >= started:
		return False

	command = ["gh", "api", "-X", "POST", f"repos/{REPO}/statuses/{sha}"]
	fields = {"state": state, "context": CONTEXT, "description": description}
	if url:
		fields["target_url"] = url
	for key, value in fields.items():
		command += ["-f", f"{key}={value}"]
	subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
	print(f"#{pr['number']}: {state} ({description})")
	return True


if __name__ == "__main__":
	command, *args = sys.argv[1:]
	develop = develop_state()
	print(f"develop: {develop}")

	if command == "pr":
		post(gh(f"repos/{REPO}/pulls/{args[0]}"), develop)
	elif command == "refresh":
		started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
		for listed in gh_pages(f"repos/{REPO}/pulls?base=develop&state=open&per_page=100"):
			pr = gh(f"repos/{REPO}/pulls/{listed['number']}")
			if pr["state"] == "open" and post(pr, develop, started):
				time.sleep(1)
	else:
		sys.exit(f"unknown command: {command}")
