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

import glob
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from functools import cache
from pathlib import Path
from urllib.error import HTTPError

import impact_map

# Restored from the nightly run by the workflow; absent means "run everything".
IMPACT_MAP_FILE = "impact-map.json"
UI_IMPACT_MAP_FILE = "ui-impact-map.json"
SPEC_FILE = re.compile(r"^playwright/tests/[\w-]+\.spec\.js$")

# A change to the framework's spine or to test infrastructure can affect any test, so the map's
# answer is not worth trusting. Test modules under these paths are exempt -- see below.
CORE_PATHS = (
	"frappe/__init__.py",
	"frappe/hooks.py",
	"frappe/database/",
	"frappe/model/",
	"frappe/parallel_test_runner.py",
	"frappe/tests/",
)

PATCH_TESTS = {"frappe/tests/test_patches.py"}


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


def matches_postgres_filenames(files_list):
	"""Check if any changed files suggest database involvement."""
	db_keywords = ["database", "query", "schema", "postgres"]
	return any(any(word in f.lower() for word in db_keywords) for f in files_list)


def select_tests(files_list):
	"""Test modules a pull request needs, according to the impact map. See #42028.

	Returns None for "run the full suite" and prints why; [] when nothing server-side changed.
	"""
	patch_files = [f for f in files_list if is_patch(f)]
	files_list = [f for f in files_list if f not in patch_files]

	# JSON outside the `frappe` package -- `ui/package.json` and the like -- is not schema.
	relevant_files = [
		f
		for f in files_list
		if f.endswith((".py", ".po")) or (f.endswith(".json") and f.startswith("frappe/"))
	]
	# Coverage cannot see dependency bumps and the like, so those force the full suite.
	ignorable_files = [f for f in files_list if is_docs(f) or is_frontend_code(f)]
	other_files = [f for f in files_list if f not in relevant_files and f not in ignorable_files]
	# A doctype's schema is exercised wherever its controller runs.
	code_files = [doctype_controller(f) or f for f in relevant_files]
	# A test module's content can only break its own tests and those of modules importing it.
	core_files = [f for f in code_files if f.startswith(CORE_PATHS) and not impact_map.is_test_module(f)]

	if other_files:
		print(f"Running full suite, changes coverage cannot see: {other_files}")
		return None
	if not code_files and not patch_files:
		return []
	if schema_files := [f for f in code_files if not f.endswith(".py")]:
		print(f"Running full suite, schema/translation changes: {schema_files}")
		return None
	if core_files:
		print(f"Running full suite, core changes: {core_files}")
		return None

	try:
		loaded_map = json.loads(Path(IMPACT_MAP_FILE).read_text())
	except (OSError, ValueError) as exc:
		if not all(impact_map.is_test_module(f) for f in code_files):
			print(f"Running full suite, no usable impact map ({exc})")
			return None
		selected = sorted(impact_map.importers(set(code_files)) | patch_tests(patch_files))
		print(f"Running {len(selected)} test modules for {relevant_files + patch_files} (no impact map):")
	else:
		if impact_map.is_stale(loaded_map):
			print(f"Running full suite, map from {loaded_map['generated_at']} is stale")
			return None
		if unmapped := impact_map.unmapped(loaded_map, code_files):
			print(f"Running full suite, no tests attributed to: {unmapped}")
			return None
		try:
			readers = doctype_readers([f for f in relevant_files if doctype_controller(f)])
		except (OSError, ValueError, KeyError) as exc:
			print(f"Running full suite, cannot read changed doctypes ({exc})")
			return None
		selected = sorted(set(impact_map.select(loaded_map, code_files)) | patch_tests(patch_files) | readers)
		total = len(impact_map.all_tests(loaded_map))
		print(f"Running {len(selected)}/{total} test modules for {relevant_files + patch_files}:")

	for test_file in selected:
		print(f"  {test_file}")
	return selected


def select_specs(files_list):
	"""Playwright specs a pull request needs, according to the UI impact map. None runs them all."""
	try:
		loaded_map = json.loads(Path(UI_IMPACT_MAP_FILE).read_text())
	except (OSError, ValueError) as exc:
		print(f"Running all specs, no usable UI impact map ({exc})")
		return None

	changed_specs = [f for f in files_list if SPEC_FILE.match(f)]
	code_files = [
		f for f in files_list if f not in changed_specs and not is_docs(f) and not is_server_side_code(f)
	]

	if other_files := [
		f
		for f in code_files
		if not (f.startswith("frappe/public/js/") and f.endswith((".js", ".ts", ".vue", ".html")))
	]:
		print(f"Running all specs, changes the UI map cannot see: {other_files}")
	elif impact_map.is_stale(loaded_map):
		print(f"Running all specs, UI map from {loaded_map['generated_at']} is stale")
	elif unmapped := impact_map.unmapped(loaded_map, code_files):
		print(f"Running all specs, no specs attributed to: {unmapped}")
	else:
		selected = sorted(set(changed_specs).union(*(loaded_map["map"][f] for f in code_files)))
		total = len(impact_map.all_tests(loaded_map))
		print(f"Running {len(selected)}/{total} specs for {changed_specs + code_files}:")
		for spec in selected:
			print(f"  {spec}")
		return selected

	return None


def shards(selected, full, per_shard):
	"""Shard indexes for the test matrix: fewer machines when only a few files run."""
	count = full if selected is None else max(1, min(full, -(-len(selected) // per_shard)))
	return list(range(1, count + 1))


def doctype_readers(schema_files, root="."):
	"""Tests that name a changed doctype: they can read its meta without running its controller."""
	if not schema_files:
		return set()
	names = [json.loads(Path(root, f).read_text())["name"] for f in schema_files]
	pattern = re.compile("|".join(rf"[\"']{re.escape(name)}[\"']" for name in names))
	return {
		os.path.relpath(path, root)
		for path in glob.iglob(os.path.join(root, impact_map.TEST_GLOB), recursive=True)
		if pattern.search(Path(path).read_text())
	}


def doctype_controller(file):
	"""`frappe/<module>/doctype/<name>/<name>.json` -> its controller `<name>.py`, else None."""
	parts = file.split("/")
	if len(parts) >= 4 and parts[-3] == "doctype" and parts[-1] == f"{parts[-2]}.json":
		return file[:-5] + ".py"
	return None


def is_docs(file):
	"""Check if the file is documentation, an image or font, repo tooling config or the translation template (no runtime effect)."""
	regex = re.compile(
		r"\.(md|png|jpg|jpeg|gif|webp|ico|csv|svg|woff2?|ttf|otf|eot)$|^.github|LICENSE|/locale/main\.pot$"
		r"|^(\.gitignore|\.eslintignore|\.releaserc|\.pre-commit-config\.yaml|CODEOWNERS)$"
	)
	return bool(regex.search(file))


def patch_tests(patch_files):
	"""`test_patches.py` plus every test that names a changed patch, or a patch importing one."""
	if not patch_files:
		return set()
	patches = impact_map.importers(
		{f for f in patch_files if f.endswith(".py")}, pattern="frappe/patches/**/*.py"
	)
	return (impact_map.importers(patches) - patches) | PATCH_TESTS


def is_patch(file):
	"""Patches run in the Migration job, their tests are found by `patch_tests`."""
	return file == "frappe/patches.txt" or file.startswith("frappe/patches/")


def _selftest():
	import tempfile
	from datetime import UTC, datetime

	assert is_docs("frappe/locale/main.pot"), "translation template alone must skip tests"
	assert not is_docs("frappe/locale/de.po"), "translations change output, must run tests"
	assert not is_frontend_code("frappe/templates/print_format/print_format.html"), (
		"Jinja must run server tests"
	)
	assert is_frontend_code("studio/frontend/index.html"), "app pages outside the frappe package are frontend"

	impact = {
		"generated_at": datetime.now(UTC).isoformat(),
		"map": {
			"frappe/a.py": ["frappe/tests/test_a.py"],
			"frappe/core/doctype/note/note.py": ["frappe/core/doctype/note/test_note.py"],
		},
	}
	cwd = os.getcwd()
	with tempfile.TemporaryDirectory() as tree:
		os.chdir(tree)
		try:
			with open(IMPACT_MAP_FILE, "w") as f:
				json.dump(impact, f)
			assert select_tests(["frappe/locale/main.pot", "frappe/a.py"]) == ["frappe/tests/test_a.py"], (
				"main.pot must not force the full suite"
			)
			assert select_tests(["frappe/locale/de.po", "frappe/a.py"]) is None, (
				".po must force the full suite"
			)
			os.makedirs("frappe/patches/v16_0")
			os.makedirs("frappe/tests")
			for path, src in {
				"frappe/patches/v16_0/base.py": "x = 1\n",
				"frappe/patches/v16_0/x.py": "from frappe.patches.v16_0.base import x\n",
				"frappe/tests/test_x.py": 'PATCH = "frappe.patches.v16_0.x"\n',
			}.items():
				Path(path).write_text(src)
			assert select_tests(["frappe/patches.txt", "frappe/patches/v16_0/base.py", "frappe/a.py"]) == [
				"frappe/tests/test_a.py",
				"frappe/tests/test_patches.py",
				"frappe/tests/test_x.py",
			], "patches must run the tests naming them or a patch importing them, not the full suite"
			assert select_tests(
				["frappe/public/images/a.webp", "frappe/public/js/a.html", "frappe/a.py"]
			) == ["frappe/tests/test_a.py"], "images and client-side templates must not force the full suite"
			assert select_tests(["frappe/www/a.html", "frappe/a.py"]) is None, (
				"Jinja templates must force the full suite"
			)
			os.makedirs("frappe/core/doctype/note")
			Path("frappe/core/doctype/note/note.json").write_text('{"name": "Note"}')
			Path("frappe/tests/test_timeline.py").write_text('meta = frappe.get_meta("Note")\n')
			assert select_tests(["frappe/core/doctype/note/note.json"]) == [
				"frappe/core/doctype/note/test_note.py",
				"frappe/tests/test_timeline.py",
			], "a doctype schema change must run its controller's tests and the tests naming it"
			assert select_tests(["frappe/core/doctype/todo/todo.json"]) is None, (
				"a doctype whose controller has no tests must force the full suite"
			)
			assert select_tests(["frappe/core/workspace/a/a.json"]) is None, "other JSON is still schema"

			os.remove(IMPACT_MAP_FILE)
			assert (
				select_tests(["frontend/speed-budgets.json", "frontend/src/a.vue", "frontend/README.md"])
				== []
			), "no server-side change must skip tests without a map"
			assert select_tests(["frappe/tests/test_x.py"]) == ["frappe/tests/test_x.py"], (
				"test-only changes must not need a map"
			)
			assert select_tests(["frappe/a.py"]) is None, "code changes without a map must run the full suite"
			assert select_tests(["frontend/package.base.json"]) is None, (
				"dependency bumps must run the full suite"
			)

			Path(UI_IMPACT_MAP_FILE).write_text(
				json.dumps(
					{
						"generated_at": datetime.now(UTC).isoformat(),
						"map": {
							"frappe/public/js/ws.js": ["playwright/tests/workspace.spec.js"],
							"frappe/public/js/pfb/Field.vue": [
								"playwright/tests/print_format_builder.spec.js"
							],
						},
					},
				)
			)
			assert select_specs(["frappe/public/js/pfb/Field.vue", "README.md"]) == [
				"playwright/tests/print_format_builder.spec.js"
			], "a mapped frontend change must run only its specs"
			assert select_specs(["frappe/public/js/ws.js", "playwright/tests/grid.spec.js"]) == [
				"playwright/tests/grid.spec.js",
				"playwright/tests/workspace.spec.js",
			], "a changed spec must run itself"
			assert select_specs(["frappe/public/js/new.js"]) is None, "an unmapped file must run all specs"
			assert select_specs(["frappe/public/js/ws.js", "frappe/a.py"]) == [
				"playwright/tests/workspace.spec.js"
			], "Python must not widen the selection, as Python alone skips UI tests"
			assert select_specs(["frappe/public/js/ws.js", "frappe/core/doctype/note/note.json"]) is None, (
				"schema changes must run all specs"
			)
			assert select_specs(["playwright/support/index.js"]) is None, "test support must run all specs"
			assert select_specs(["frappe/public/scss/desk.scss"]) is None, "styles must run all specs"
		finally:
			os.chdir(cwd)

	assert shards(None, full=4, per_shard=15) == [1, 2, 3, 4]
	assert shards(["a"], full=4, per_shard=15) == [1], "a few files must run on one machine"
	assert shards(["a"] * 16, full=4, per_shard=15) == [1, 2]
	assert shards(["a"] * 500, full=2, per_shard=40) == [1, 2]

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
		print("Only Python code was updated, stopping UI test build process.")
		sys.exit(0)

	# If we reach here, run the build
	selected_tests = None
	# An explicit request for server tests gets the full suite.
	if build_type == "server" and not ci_files_changed and not has_run_server_tests_label(pr_number, repo):
		selected_tests = select_tests(files_list)
		if selected_tests == []:
			print("No server-side changes; Stopping Python build process.")
			sys.exit(0)

	selected_specs = None
	if build_type == "ui" and not ci_files_changed and not has_run_ui_tests_label(pr_number, repo):
		selected_specs = select_specs(files_list)

	os.system('echo "build=strawberry" >> $GITHUB_OUTPUT')
	# Empty means the full suite. Written without a shell: these are PR-controlled file names.
	with open(os.environ["GITHUB_OUTPUT"], "a") as f:
		f.write(f"tests={' '.join(selected_tests or [])}\n")
		f.write(f"specs={' '.join(selected_specs or [])}\n")
		if build_type == "server":
			matrix = shards(None if run_postgres else selected_tests, full=2, per_shard=40)
		else:
			matrix = shards(selected_specs, full=4, per_shard=15)
		f.write(f"shards={json.dumps(matrix)}\nshard_total={len(matrix)}\n")
	os.system(f'echo "run_postgres={"true" if run_postgres else "false"}" >> $GITHUB_OUTPUT')
