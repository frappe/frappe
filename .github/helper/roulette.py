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
	api_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"

	if endpoint:
		api_url += f"/{endpoint}"

	res = req(api_url)
	return json.loads(res.read().decode("utf8"))


def req(url):
	"Simple resilient request call to handle rate limits."
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
<<<<<<< HEAD
	return file.lower().endswith((".css", ".scss", ".less", ".sass", ".styl", ".js", ".ts", ".vue", ".html"))
=======
	"""Check if the file is frontend code."""
	if os.path.basename(file) in ("package.json", "yarn.lock") and not file.startswith("frappe/"):
		return True
	return file.lower().endswith(
		(".css", ".scss", ".less", ".sass", ".styl", ".js", ".ts", ".vue", ".html", ".svg")
	)


def matches_postgres_filenames(files_list):
	"""Check if any changed files suggest database involvement."""
	db_keywords = ["database", "query", "schema", "postgres"]
	return any(any(word in f.lower() for word in db_keywords) for f in files_list)


def select_tests(files_list):
	"""Test modules a pull request needs, according to the impact map. See #42028.

	Returns None for "run the full suite" and prints why; [] when nothing server-side changed.
	"""
	try:
		with open(IMPACT_MAP_FILE) as f:
			loaded_map = json.load(f)
	except (OSError, ValueError) as exc:
		print(f"Running full suite, no usable impact map ({exc})")
		return None

	# JSON outside the `frappe` package -- `ui/package.json` and the like -- is not schema.
	relevant_files = [
		f
		for f in files_list
		if f.endswith((".py", ".po")) or (f.endswith(".json") and f.startswith("frappe/"))
	]
	# Coverage cannot see dependency bumps and the like, so those force the full suite. Frontend code
	# is safe to ignore, except `.html`: that is mostly Jinja rendered on the server.
	ignorable_files = [
		f for f in files_list if is_docs(f) or (is_frontend_code(f) and not f.endswith(".html"))
	]
	other_files = [f for f in files_list if f not in relevant_files and f not in ignorable_files]
	# A test module's content can only break its own tests and those of modules importing it.
	core_files = [f for f in relevant_files if f.startswith(CORE_PATHS) and not impact_map.is_test_module(f)]

	if other_files:
		print(f"Running full suite, changes coverage cannot see: {other_files}")
	elif schema_files := [f for f in relevant_files if not f.endswith(".py")]:
		print(f"Running full suite, schema/translation changes: {schema_files}")
	elif core_files:
		print(f"Running full suite, core changes: {core_files}")
	elif impact_map.is_stale(loaded_map):
		print(f"Running full suite, map from {loaded_map['generated_at']} is stale")
	elif unmapped := impact_map.unmapped(loaded_map, relevant_files):
		print(f"Running full suite, no tests attributed to: {unmapped}")
	else:
		selected = impact_map.select(loaded_map, relevant_files)
		total = len(impact_map.all_tests(loaded_map))
		print(f"Running {len(selected)}/{total} test modules for {relevant_files}:")
		for test_file in selected:
			print(f"  {test_file}")
		return selected

	return None
>>>>>>> 4e05ac6 (ci: skip server tests when only js dependencies change)


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
		os.system('echo "build=strawberry" >> $GITHUB_OUTPUT')
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

	os.system('echo "build=strawberry" >> $GITHUB_OUTPUT')
