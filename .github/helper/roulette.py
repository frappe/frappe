import json
import os
import re
import shlex
import subprocess
import sys
import urllib.request
from functools import lru_cache


@lru_cache(maxsize=None)
def fetch_pr_data(pr_number, repo, endpoint=""):
	api_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"

	if endpoint:
		api_url += f"/{endpoint}"

	req = urllib.request.Request(api_url)
	res = urllib.request.urlopen(req)
	return json.loads(res.read().decode("utf8"))


def get_files_list(pr_number, repo="frappe/frappe"):
	return [change["filename"] for change in fetch_pr_data(pr_number, repo, "files")]


def get_output(command, shell=True):
	print(command)
	command = shlex.split(command)
	return subprocess.check_output(command, shell=shell, encoding="utf8").strip()


def has_skip_ci_label(pr_number, repo="frappe/frappe"):
	return has_label(pr_number, "Skip CI", repo)


def has_run_server_tests_label(pr_number, repo="frappe/frappe"):
	return has_label(pr_number, "Run Server Tests", repo)


def has_run_ui_tests_label(pr_number, repo="frappe/frappe"):
	return has_label(pr_number, "Run UI Tests", repo)


def has_label(pr_number, label, repo="frappe/frappe"):
	return any(
		[
			fetched_label["name"]
			for fetched_label in fetch_pr_data(pr_number, repo)["labels"]
			if fetched_label["name"] == label
		]
	)


def is_py(file):
	return file.endswith("py")


def is_ci(file):
	return ".github" in file


def is_frontend_code(file):
	return file.lower().endswith(
		(".css", ".scss", ".less", ".sass", ".styl", ".js", ".ts", ".vue", ".html")
	)


def is_docs(file):
	regex = re.compile(r"\.(md|png|jpg|jpeg|csv|svg)$|^.github|LICENSE")
	return bool(regex.search(file))


if __name__ == "__main__":
	files_list = sys.argv[1:]
	build_type = os.environ.get("TYPE")
	pr_number = os.environ.get("PR_NUMBER")
	repo = os.environ.get("REPO_NAME")

	# this is a push build, run all builds
	if not pr_number:
		os.system('echo "::set-output name=build::strawberry"')
		sys.exit(0)

	files_list = files_list or get_files_list(pr_number=pr_number, repo=repo)

	if not files_list:
		print("No files' changes detected. Build is shutting")
		sys.exit(0)

	ci_files_changed = any(f for f in files_list if is_ci(f))
	only_docs_changed = len(list(filter(is_docs, files_list))) == len(files_list)
	only_frontend_code_changed = len(list(filter(is_frontend_code, files_list))) == len(files_list)
	updated_py_file_count = len(list(filter(is_py, files_list)))
	only_py_changed = updated_py_file_count == len(files_list)

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

	os.system('echo "::set-output name=build::strawberry"')
