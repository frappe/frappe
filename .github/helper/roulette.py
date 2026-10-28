"""
GitHub Pull Request Analysis and CI Build Decision Script

This script analyzes changes in a GitHub pull request and determines whether to run specific CI builds.
It checks for file types changed, presence of certain labels, and other criteria to make decisions about
which parts of the CI pipeline should run. The script is designed to optimize CI resources by skipping
unnecessary builds based on the nature of changes in the pull request.

Key features:
- Fetches pull request data from GitHub API
- Analyzes changed files
- Checks for specific labels on the pull request
- Determines whether to run server-side, UI, or all tests
- Handles rate limiting for GitHub API requests
- Supports environment variables for configuration

Usage:
This script is intended to be run as part of a CI pipeline, with the necessary environment variables set.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from functools import cache
from urllib.error import HTTPError

FULL_CI_LABEL = "run-full-ci"
FIX_DEVELOP_LABEL = "fixes-develop"


@cache
def fetch_pr_data(pr_number, repo, endpoint=""):
	"""
	Fetch pull request data from GitHub API.

	:param pr_number: Pull request number
	:param repo: Repository name (e.g., "frappe/frappe")
	:param endpoint: Additional API endpoint (e.g., "files")
	:return: JSON response from GitHub API
	"""
	api_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
	if endpoint:
		api_url += f"/{endpoint}"
	res = req(api_url)
	return json.loads(res.read().decode("utf8"))


def req(url):
	"""
	Make a resilient request to handle rate limits.

	:param url: URL to request
	:return: URLResponse object
	"""
	headers = None
	token = os.environ.get("GITHUB_TOKEN")
	if token:
		headers = {"authorization": f"Bearer {token}"}

	retries = 0
	while True:
		try:
			req = urllib.request.Request(url, headers=headers)
			return urllib.request.urlopen(req)
		except HTTPError as exc:
			if exc.code == 403 and retries < 5:
				retries += 1
				time.sleep(retries)
				continue
			raise


def get_files_list(pr_number, repo="frappe/frappe"):
	"""
	Get list of files changed in the pull request.

	:param pr_number: Pull request number
	:param repo: Repository name
	:return: List of changed file names
	"""
	files, page = [], 1
	while changes := fetch_pr_data(pr_number, repo, f"files?per_page=100&page={page}"):
		files += [change["filename"] for change in changes]
		page += 1
	return files


def get_output(command, shell=True):
	"""
	Execute a shell command and return its output.

	:param command: Command to execute
	:param shell: Whether to use shell
	:return: Command output as string
	"""
	print(command)
	command = shlex.split(command)
	return subprocess.check_output(command, shell=shell, encoding="utf8").strip()


def has_skip_ci_label(pr_number, repo="frappe/frappe"):
	"""Check if the PR has the 'Skip CI' label."""
	return has_label(pr_number, "Skip CI", repo)


def has_run_server_tests_label(pr_number, repo="frappe/frappe"):
	"""Check if the PR has the 'Run Server Tests' or full CI label, or fixes failing server tests on develop."""
	return any(has_label(pr_number, label, repo) for label in ("Run Server Tests", FULL_CI_LABEL)) or (
		has_label(pr_number, FIX_DEVELOP_LABEL, repo) and base_failing(pr_number, repo, "server-tests.yml")
	)


def has_run_ui_tests_label(pr_number, repo="frappe/frappe"):
	"""Check if the PR has the 'Run UI Tests' or full CI label, or fixes failing UI tests on develop."""
	return any(has_label(pr_number, label, repo) for label in ("Run UI Tests", FULL_CI_LABEL)) or (
		has_label(pr_number, FIX_DEVELOP_LABEL, repo) and base_failing(pr_number, repo, "ui-tests.yml")
	)


def base_failing(pr_number, repo, workflow):
	"""Is this suite's latest full run failing on the branch the PR targets, or on develop for other branches?"""
	from develop_status import BRANCHES, failing_suites

	base = fetch_pr_data(pr_number, repo)["base"]["ref"]
	return workflow in failing_suites(base if base in BRANCHES else "develop")


def skips_test_suites(pr_number, repo="frappe/frappe"):
	"""Check if the PR targets develop, desk-v2 or a hotfix branch: develop runs the suites every hour, hotfix on the release PR."""
	base = fetch_pr_data(pr_number, repo)["base"]["ref"]
	return base in ("develop", "desk-v2") or base.endswith("-hotfix")


def has_label(pr_number, label, repo="frappe/frappe"):
	"""
	Check if the pull request has a specific label.

	:param pr_number: Pull request number
	:param label: Label to check for
	:param repo: Repository name
	:return: Boolean indicating presence of label
	"""
	return any(
		[
			fetched_label["name"]
			for fetched_label in fetch_pr_data(pr_number, repo)["labels"]
			if fetched_label["name"] == label
		]
	)


def is_server_side_code(file):
	"""Check if the file is server-side code (Python or .po files)."""
	return file.endswith("py") or file.endswith(".po")


def is_ci(file):
	"""Check if the file is related to CI configuration."""
	return ".github" in file and "VOUCHED.td" not in file and not file.endswith(".md")


def is_frontend_code(file):
	"""Check if the file is frontend code. `.html` in the `frappe` package outside `public` is Jinja rendered on the server."""
	if os.path.basename(file) in ("package.json", "yarn.lock") and not file.startswith("frappe/"):
		return True
	if (
		file.startswith("frontend/")
		and file.endswith(".json")
		and not os.path.basename(file).startswith("package")
	):
		return True
	if file.endswith(".html") and file.startswith("frappe/") and not file.startswith("frappe/public/"):
		return False
	return file.lower().endswith(
		(".css", ".scss", ".less", ".sass", ".styl", ".js", ".mjs", ".ts", ".vue", ".html", ".svg")
	)


def is_desk_frontend(file):
	"""The desk-v2 frontend, and the pages, records and settings an app contributes to it."""
	return file.startswith(("frontend/", "ui/")) or (file.startswith("frappe/") and "/frontend/" in file)


def matches_postgres_filenames(files_list):
	"""Check if any changed files suggest database involvement."""
	db_keywords = ["database", "query", "schema", "postgres"]
	return any(any(word in f.lower() for word in db_keywords) for f in files_list)


def is_docs(file):
	"""Check if the file is documentation, an image or font, repo tooling config or the translation template (no runtime effect)."""
	regex = re.compile(
		r"\.(md|png|jpg|jpeg|gif|webp|ico|csv|svg|woff2?|ttf|otf|eot)$|^.github|LICENSE|/locale/main\.pot$"
		r"|^(\.gitignore|\.eslintignore|\.releaserc|\.pre-commit-config\.yaml|CODEOWNERS)$"
	)
	return bool(regex.search(file))


def _selftest():
	assert is_docs("frappe/locale/main.pot"), "translation template alone must skip tests"
	assert not is_docs("frappe/locale/de.po"), "translations change output, must run tests"
	assert not is_frontend_code("frappe/templates/print_format/print_format.html"), (
		"Jinja must run server tests"
	)
	assert is_frontend_code("studio/frontend/index.html"), "app pages outside the frappe package are frontend"
	assert is_desk_frontend("ui/src/index.ts"), "desk-v2's server tests read ui/"
	assert is_desk_frontend("frappe/desk/navigation_item_type/page/frontend/item.js"), (
		"test_shell.py reads contributions"
	)
	assert not is_desk_frontend("frappe/public/js/frappe/ui/dialog.js"), "desk v1 is not desk-v2's frontend"
	print("roulette selftest OK")


if __name__ == "__main__":
	if sys.argv[1:] == ["selftest"]:
		_selftest()
		sys.exit(0)

	files_list = sys.argv[1:]
	build_type = os.environ.get("TYPE")
	pr_number = os.environ.get("PR_NUMBER")
	repo = os.environ.get("REPO_NAME")

	# If it's a push build, run all builds
	if not pr_number:
		os.system('echo "build=strawberry" >> $GITHUB_OUTPUT')
		sys.exit(0)

	# Get list of changed files if not provided
	files_list = files_list or get_files_list(pr_number=pr_number, repo=repo)

	if not files_list:
		print("No files' changes detected. Build is shutting")
		sys.exit(0)

	# Analyze changed files
	ci_files_changed = any(f for f in files_list if is_ci(f))
	only_docs_changed = len(list(filter(is_docs, files_list))) == len(files_list)
	only_frontend_code_changed = len(list(filter(is_frontend_code, files_list))) == len(files_list)
	updated_py_file_count = len(list(filter(is_server_side_code, files_list)))
	only_py_changed = updated_py_file_count == len(files_list)
	run_postgres = has_label(pr_number, "postgres", repo)

	if build_type == "server":
		tests_requested = has_run_server_tests_label(pr_number, repo)
	else:
		tests_requested = has_run_ui_tests_label(pr_number, repo)

	if os.environ.get("SKIP_ON_PRS") and skips_test_suites(pr_number, repo) and not tests_requested:
		print(
			"Develop and hotfix PRs skip the test suites, they run on the branch instead; stopping build process."
		)
		sys.exit(0)

	# Check for Skip CI label and other conditions
	if has_skip_ci_label(pr_number, repo):
		if build_type == "ui" and has_run_ui_tests_label(pr_number, repo):
			print("Running UI tests only.")
		elif build_type == "server" and has_run_server_tests_label(pr_number, repo):
			print("Running server tests only.")
		else:
			print("Found `Skip CI` label on pr, stopping build process.")
			sys.exit(0)
	elif ci_files_changed:
		print("CI related files were updated, running all build processes.")
	elif only_docs_changed:
		print("Only docs were updated, stopping build process.")
		sys.exit(0)
	elif only_frontend_code_changed and build_type == "server" and not tests_requested:
		print("Only Frontend code was updated; Stopping Python build process.")
		sys.exit(0)
	elif build_type == "ui" and only_py_changed and not has_run_ui_tests_label(pr_number, repo):
		print("Only Python code was updated, stopping UI test build process.")
		sys.exit(0)

	# If we reach here, run the build
	os.system('echo "build=strawberry" >> $GITHUB_OUTPUT')
	os.system(f'echo "run_postgres={"true" if run_postgres else "false"}" >> $GITHUB_OUTPUT')
