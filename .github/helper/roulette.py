import os
import re
import shlex
import subprocess
import sys


def get_output(command, shell=True):
	print(command)
	command = shlex.split(command)
	return subprocess.check_output(command, shell=shell, encoding="utf8").strip()

def is_py(file):
	return file.endswith("py")

def is_ci(file):
	return file.endswith("yml") or ".github" in file

def is_js(file):
	return file.endswith("js")

def is_docs(file):
	regex = re.compile(r'\.(md|png|jpg|jpeg)$|^.github|LICENSE')
	return bool(regex.search(file))


if __name__ == "__main__":
	files_list = sys.argv[1:]
	build_type = os.environ.get("TYPE")

	if not files_list:
		print("No files' changes detected. Build is shutting")
		sys.exit(0)

	ci_files_changed = any(f for f in files_list if is_ci(f))
	only_docs_changed = len(list(filter(is_docs, files_list))) == len(files_list)
	only_js_changed = len(list(filter(is_js, files_list))) == len(files_list)
	only_py_changed = len(list(filter(is_py, files_list))) == len(files_list)

	if ci_files_changed:
		print("CI related files were updated, running all build processes.")

	if only_docs_changed:
		print("Only docs were updated, stopping build process.")
		sys.exit(0)

	if only_js_changed and build_type == "server":
		print("Only JavaScript code was updated; Stopping Python build process.")
		sys.exit(0)

	if only_py_changed and build_type == "ui":
		print("Only Python code was updated, stopping Cypress build process.")
		sys.exit(0)

	os.system('echo "::set-output name=build::strawberry"')
