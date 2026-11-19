"""Comment on a pull request the merge queue removed, naming the checks that failed.

The queue tests a pull request on a temporary branch, so its failed checks never show on the
pull request itself. Reads PR_NUMBER, REPO_NAME, GITHUB_TOKEN and REASON from the environment.
`DRY_RUN=1` prints the comment instead of posting it.
"""

import json
import os
import sys
import urllib.request

API = "https://api.github.com"
FAILED = {"FAILURE", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE"}

PULL_REQUEST = """
query($owner: String!, $name: String!, $number: Int!) {
	repository(owner: $owner, name: $name) {
		pullRequest(number: $number) {
			merged
			isInMergeQueue
			baseRefName
			comments(last: 50) { nodes { body } }
		}
	}
}
"""

CHECKS = """
query($owner: String!, $name: String!, $number: Int!, $oid: GitObjectID!) {
	repository(owner: $owner, name: $name) {
		object(oid: $oid) {
			... on Commit {
				checkSuites(first: 50) {
					nodes {
						checkRuns(first: 100) {
							nodes { name conclusion detailsUrl %s }
						}
					}
				}
			}
		}
	}
}
"""


def request(path, payload=None):
	req = urllib.request.Request(
		f"{API}{path}",
		data=json.dumps(payload).encode() if payload else None,
		headers={
			"authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
			"accept": "application/vnd.github+json",
		},
	)
	return json.loads(urllib.request.urlopen(req).read())


def graphql(query, **variables):
	result = request("/graphql", {"query": query, "variables": variables})
	if result.get("errors"):
		raise RuntimeError(result["errors"])
	return result["data"]["repository"]


def group_commit(repo, base, number):
	"""The commit of the last group the queue built for this pull request."""
	prefix = f"gh-readonly-queue/{base}/pr-{number}-"
	runs = []
	for page in (1, 2, 3):
		runs += request(f"/repos/{repo}/actions/runs?event=merge_group&per_page=100&page={page}")[
			"workflow_runs"
		]
	runs = [run for run in runs if run["head_branch"].startswith(prefix)]
	return max(runs, key=lambda run: run["created_at"])["head_sha"] if runs else None


def failed_checks(owner, name, number, commit):
	"""Failed checks of the workflows that failed a required check."""
	variables = {"owner": owner, "name": name, "number": number, "oid": commit}
	try:
		data = graphql(CHECKS % "isRequired(pullRequestNumber: $number)", **variables)
	except RuntimeError:
		data = graphql(CHECKS % "", **variables)

	failed = []
	for suite in data["object"]["checkSuites"]["nodes"]:
		runs = [run for run in suite["checkRuns"]["nodes"] if run["conclusion"] in FAILED]
		if any(run.get("isRequired", True) for run in runs):
			failed += runs
	return failed


def build_comment(base, commit, failed, reason):
	marker = f"<!-- merge-queue-failure:{commit} -->"
	if failed:
		checks = "\n".join(f"- [{run['name']}]({run['detailsUrl']})" for run in failed)
		return (
			f"The merge queue removed this pull request because these checks failed when it was"
			f" tested on top of `{base}`:\n\n{checks}\n\n"
			f"Once the failure is fixed, add it back with **Merge when ready**.\n{marker}"
		)
	if "timeout" in reason.lower():
		return (
			"The merge queue removed this pull request because its checks did not finish in time."
			f" Add it back with **Merge when ready**.\n{marker}"
		)
	return None


def main():
	repo = os.environ["REPO_NAME"]
	owner, name = repo.split("/")
	number = int(os.environ["PR_NUMBER"])
	reason = os.environ.get("REASON", "")

	pull = graphql(PULL_REQUEST, owner=owner, name=name, number=number)["pullRequest"]
	if pull["merged"] or pull["isInMergeQueue"]:
		print("Merged or back in the queue, nothing to report.")
		return

	commit = group_commit(repo, pull["baseRefName"], number)
	if not commit:
		print("No merge queue run found for this pull request.")
		return

	comment = build_comment(pull["baseRefName"], commit, failed_checks(owner, name, number, commit), reason)
	if not comment:
		print(f"No failed check on {commit}, removal reason: {reason or 'unknown'}.")
		return
	if any(comment.splitlines()[-1] in node["body"] for node in pull["comments"]["nodes"]):
		print("Already commented for this merge queue run.")
		return

	print(comment)
	if not os.environ.get("DRY_RUN"):
		request(f"/repos/{repo}/issues/{number}/comments", {"body": comment})


if __name__ == "__main__":
	sys.exit(main())
