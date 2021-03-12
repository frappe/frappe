# if the script ends with exit code 0, then no tests are run further, else all tests are run
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

def is_js(file):
    return file.endswith("js")

def is_docs(file):
    regex = re.compile('\.(md|png|jpg|jpeg)$|^.github|LICENSE')
    return bool(regex.search(file))


if __name__ == "__main__":
    build_type = os.environ.get("TYPE")
    before = os.environ.get("BEFORE")
    after = os.environ.get("AFTER")
    commit_range = before + '...' + after
    print("Build Type: {}".format(build_type))
    print("Commit Range: {}".format(commit_range))

    try:
        files_changed = get_output("git diff --name-only {}".format(commit_range), shell=False)
    except Exception:
        sys.exit(2)

    if "fatal" not in files_changed:
        files_list = files_changed.split()
        only_docs_changed = len(list(filter(is_docs, files_list))) == len(files_list)
        only_js_changed = len(list(filter(is_js, files_list))) == len(files_list)
        only_py_changed = len(list(filter(is_py, files_list))) == len(files_list)

        if only_docs_changed:
            print("Only docs were updated, stopping build process.")
            sys.exit(0)

        if only_js_changed and build_type == "server":
            print("Only JavaScript code was updated; Stopping Python build process.")
            sys.exit(0)

        if only_py_changed and build_type == "ui":
            print("Only Python code was updated, stopping Cypress build process.")
            sys.exit(0)

    sys.exit(2)
