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
	return [change["filename"] for change in fetch_pr_data(pr_number, repo, "files")]


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
	"""Check if the PR has the 'Run Server Tests' label."""
	return has_label(pr_number, "Run Server Tests", repo)


def has_run_ui_tests_label(pr_number, repo="frappe/frappe"):
	"""Check if the PR has the 'Run UI Tests' label."""
	return has_label(pr_number, "Run UI Tests", repo)


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
	return ".github" in file


def is_frontend_code(file):
	"""Check if the file is frontend code."""
	return file.lower().endswith((".css", ".scss", ".less", ".sass", ".styl", ".js", ".ts", ".vue", ".html"))


def is_docs(file):
	"""Check if the file is documentation or image."""
	regex = re.compile(r"\.(md|png|jpg|jpeg|csv|svg)$|^.github|LICENSE")
	return bool(regex.search(file))


if __name__ == "__main__":
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
	elif (
		only_frontend_code_changed
		and build_type == "server"
		and not has_run_server_tests_label(pr_number, repo)
	):
		print("Only Frontend code was updated; Stopping Python build process.")
		sys.exit(0)
	elif build_type == "ui" and only_py_changed and not has_run_ui_tests_label(pr_number, repo):
		print("Only Python code was updated, stopping Cypress build process.")
		sys.exit(0)

	# If we reach here, run the build
	os.system('echo "build=strawberry" >> $GITHUB_OUTPUT')
