"""Generate a review-friendly summary for large translation PRs.

This helper runs in GitHub Actions for bot-authored `.po` pull requests.
It compares the trusted base checkout against the PR head translation files,
groups similarly sized file diffs, and renders a markdown comment with the
high-signal translation changes that are hard to inspect in GitHub's UI.
"""

import argparse
import html
import io
import json
import os
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from babel.messages.pofile import read_po

COMMENT_MARKER = "<!-- po-translation-review -->"
SIMILARITY_TOLERANCE = 0.02
REVIEW_HIDDEN_PO_FILES = {"eo.po"}


@dataclass(frozen=True)
class TranslationEntry:
	"""Normalized representation of a gettext entry used for diffing."""

	context: str
	msgid: str
	msgid_plural: str | None
	translation: tuple[str, ...]

	@property
	def key(self) -> tuple[str, str, str]:
		return (self.context, self.msgid, self.msgid_plural or "")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Build a PR review comment for .po file changes in a GitHub pull request."
	)
	parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
	parser.add_argument("--pr", type=int, default=os.environ.get("PR_NUMBER"))
	parser.add_argument("--head-sha", default=os.environ.get("PR_HEAD_SHA"))
	parser.add_argument("--output", default="po-pr-review-comment.md")
	return parser.parse_args()


def request_url(url: str, *, accept: str, allow_missing: bool = False) -> bytes | None:
	"""Fetch bytes from GitHub with auth, retries, and optional 404 handling."""

	headers = {
		"Accept": accept,
		"X-GitHub-Api-Version": "2022-11-28",
		"User-Agent": "frappe-po-review-helper",
	}
	token = os.environ.get("GITHUB_TOKEN")
	if token:
		headers["Authorization"] = f"Bearer {token}"

	retries = 0
	while True:
		try:
			request = urllib.request.Request(url, headers=headers)
			with urllib.request.urlopen(request) as response:
				return response.read()
		except HTTPError as exc:
			if exc.code == 404 and allow_missing:
				return None

			if exc.code in {403, 429, 500, 502, 503, 504} and retries < 5:
				retries += 1
				time.sleep(retries)
				continue

			raise


def request_json(url: str) -> Any:
	response = request_url(url, accept="application/vnd.github+json")
	if response is None:
		return None
	return json.loads(response.decode("utf-8"))


def fetch_pr_files(repo: str, pr_number: int) -> list[dict[str, Any]]:
	"""Return the full changed-file list for a PR, following GitHub pagination."""

	files: list[dict[str, Any]] = []
	page = 1

	while True:
		url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files?per_page=100&page={page}"
		page_files = request_json(url) or []
		if not page_files:
			break

		files.extend(page_files)
		if len(page_files) < 100:
			break

		page += 1

	return files


def read_local_file(path: str | None) -> str | None:
	"""Read a file from the trusted base checkout while preventing path traversal."""

	if not path:
		return None

	repo_root = Path.cwd().resolve()
	file_path = (repo_root / path).resolve()
	try:
		file_path.relative_to(repo_root)
	except ValueError as exc:
		raise ValueError(f"Unexpected repository path: {path}") from exc

	if not file_path.exists():
		return None

	return file_path.read_text(encoding="utf-8")


def fetch_file_content(repo: str, path: str | None, ref: str | None) -> str | None:
	"""Fetch the raw content for a repository file at a specific git ref."""

	if not path or not ref:
		return None

	quoted_path = urllib.parse.quote(path, safe="/")
	quoted_ref = urllib.parse.quote(ref, safe="")
	url = f"https://api.github.com/repos/{repo}/contents/{quoted_path}?ref={quoted_ref}"
	response = request_url(url, accept="application/vnd.github.raw", allow_missing=True)
	if response is None:
		return None
	return response.decode("utf-8")


def is_po_file(change: dict[str, Any]) -> bool:
	current_path = change.get("filename", "")
	previous_path = change.get("previous_filename", "")
	return current_path.endswith(".po") or previous_path.endswith(".po")


def base_path_for_file(change: dict[str, Any]) -> str | None:
	if change.get("status") == "renamed":
		return change.get("previous_filename") or change.get("filename")
	return change.get("filename")


def head_path_for_file(change: dict[str, Any]) -> str | None:
	if change.get("status") == "removed":
		return None
	return change.get("filename")


def normalize_translation(value: Any) -> tuple[str, ...]:
	if value is None:
		return ("",)
	if isinstance(value, (tuple, list)):
		return tuple("" if part is None else str(part) for part in value)
	return (str(value),)


def is_translation_empty(translation: tuple[str, ...]) -> bool:
	"""Return whether every translated value in the entry is empty or whitespace."""

	return not any(part.strip() for part in translation)


def normalize_message(message: Any) -> TranslationEntry:
	if isinstance(message.id, tuple):
		msgid, msgid_plural = message.id
	else:
		msgid, msgid_plural = message.id, None

	return TranslationEntry(
		context=message.context or "",
		msgid=str(msgid),
		msgid_plural=None if msgid_plural is None else str(msgid_plural),
		translation=normalize_translation(message.string),
	)


def load_translation_entries(
	content: str | None,
) -> tuple[str | None, dict[tuple[str, str, str], TranslationEntry]]:
	"""Parse `.po` content into normalized entries keyed for translation diffing.

	The gettext header entry is skipped, and both singular and plural messages are
	flattened into `TranslationEntry` objects so they can be compared uniformly.
	"""

	if not content:
		return None, {}

	catalog = read_po(io.StringIO(content))
	language = str(catalog.locale) if catalog.locale else None
	entries: dict[tuple[str, str, str], TranslationEntry] = {}

	for message in catalog:
		if not message.id:
			continue

		entry = normalize_message(message)
		entries[entry.key] = entry

	return language, entries


def compare_entries(
	base_entries: dict[tuple[str, str, str], TranslationEntry],
	head_entries: dict[tuple[str, str, str], TranslationEntry],
) -> list[dict[str, TranslationEntry | str | None]]:
	"""Return only the translations that are new or changed in the PR head.

	Removed entries are not included here because reviewers primarily need to
	inspect what was introduced or modified in the new translation state. Brand
	new entries with empty `msgstr` values are also skipped to avoid noisy review
	tables for untranslated strings.
	"""

	changes: list[dict[str, TranslationEntry | str | None]] = []

	for key in sorted(head_entries, key=lambda item: (item[0].lower(), item[1].lower(), item[2].lower())):
		head_entry = head_entries[key]
		base_entry = base_entries.get(key)

		if base_entry is None:
			if is_translation_empty(head_entry.translation):
				continue
			changes.append({"status": "added", "before": None, "after": head_entry})
			continue

		if base_entry.translation != head_entry.translation:
			changes.append({"status": "changed", "before": base_entry, "after": head_entry})

	return changes


def within_tolerance(value: int, reference: float, tolerance: float = SIMILARITY_TOLERANCE) -> bool:
	if reference == 0:
		return value == 0

	allowed_delta = max(1, round(reference * tolerance))
	return abs(value - reference) <= allowed_delta


def cluster_similar_change_sizes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Group files whose added and removed line counts are within the tolerance.

	This helps spot bulk-generated translation updates where many locale files were
	changed in nearly the same way.
	"""

	clusters: list[dict[str, Any]] = []

	sorted_changes = sorted(
		changes,
		key=lambda item: (-item.get("additions", 0), -item.get("deletions", 0), item.get("filename", "")),
	)

	for change in sorted_changes:
		additions = change.get("additions", 0)
		deletions = change.get("deletions", 0)

		for cluster in clusters:
			if within_tolerance(additions, cluster["avg_additions"]) and within_tolerance(
				deletions, cluster["avg_deletions"]
			):
				cluster["files"].append(change)
				cluster["avg_additions"] = sum(file["additions"] for file in cluster["files"]) / len(
					cluster["files"]
				)
				cluster["avg_deletions"] = sum(file["deletions"] for file in cluster["files"]) / len(
					cluster["files"]
				)
				break
		else:
			clusters.append(
				{
					"files": [change],
					"avg_additions": float(additions),
					"avg_deletions": float(deletions),
				}
			)

	return sorted(
		[cluster for cluster in clusters if len(cluster["files"]) > 1],
		key=lambda cluster: (-len(cluster["files"]), -cluster["avg_additions"], -cluster["avg_deletions"]),
	)


def format_translation(translation: tuple[str, ...]) -> str:
	if len(translation) == 1:
		return translation[0]

	return "\n".join(f"[{index}] {value or '(empty)'}" for index, value in enumerate(translation))


def escape_table_cell(value: str) -> str:
	if not value:
		return "<em>empty</em>"

	return html.escape(value).replace("|", "&#124;").replace("\n", "<br>")


def render_msgid(entry: TranslationEntry) -> str:
	parts = [entry.msgid]
	if entry.msgid_plural:
		parts.append(f"[plural] {entry.msgid_plural}")
	return "\n".join(parts)


def should_hide_report_from_review(report: dict[str, Any]) -> bool:
	"""Return whether a file should be omitted from reviewer-facing language details."""

	return Path(str(report["path"])).name in REVIEW_HIDDEN_PO_FILES


def build_language_section(report: dict[str, Any]) -> list[str]:
	"""Render one language's added or changed translations as a markdown table."""

	lines = [
		f"### `{report['language']}` (`{report['path']}`)",
		"",
		"| Status | Msgid | Previous | Current |",
		"| --- | --- | --- | --- |",
	]

	for change in report["changes"]:
		before = change["before"]
		after = change["after"]
		after = after if isinstance(after, TranslationEntry) else None
		before = before if isinstance(before, TranslationEntry) else None

		if after is None:
			continue

		lines.append(
			"| "
			+ " | ".join(
				[
					str(change["status"]),
					escape_table_cell(render_msgid(after)),
					escape_table_cell("" if before is None else format_translation(before.translation)),
					escape_table_cell(format_translation(after.translation)),
				]
			)
			+ " |"
		)

	lines.append("")
	return lines


def build_comment(
	po_files: list[dict[str, Any]],
	language_reports: list[dict[str, Any]],
	similar_groups: list[dict[str, Any]],
	parse_errors: list[dict[str, str]],
) -> str:
	"""Build the final PR comment with stats, grouped diffs, and translation tables.

	The result is intentionally compact at the top and expandable below so large
	translation PRs stay reviewable even when GitHub cannot render the raw diff.
	"""

	status_counts = Counter(change.get("status", "modified") for change in po_files)
	total_files = len(po_files)
	added_files = status_counts["added"]
	removed_files = status_counts["removed"]
	reviewable_language_reports = [
		report for report in language_reports if not should_hide_report_from_review(report)
	]

	grouped_files_count = sum(len(group["files"]) for group in similar_groups)
	translation_change_count = sum(
		len(report["changes"]) for report in reviewable_language_reports if report["changes"]
	)
	changed_languages_count = sum(1 for report in reviewable_language_reports if report["changes"])
	removed_reports = [report for report in reviewable_language_reports if report["status"] == "removed"]
	metadata_only_reports = [
		report
		for report in reviewable_language_reports
		if not report["changes"] and report["status"] != "removed"
	]

	lines = [
		COMMENT_MARKER,
		"Here is a summary of the `.po` file changes:",
		"",
		f"- Changed files: `{total_files}`",
		f"- Added files: `{added_files}`",
		f"- Removed files: `{removed_files}`",
		f"- Files in similar change-size groups within 2% tolerance: `{grouped_files_count}`",
		f"- Added or changed translations detected: `{translation_change_count}` across `{changed_languages_count}` file(s)",
	]

	if parse_errors:
		lines.append(f"- Files that could not be parsed: `{len(parse_errors)}`")

	lines.extend(["", "### Similar Change-Size Groups", ""])

	if similar_groups:
		for group in similar_groups:
			representative_additions = round(group["avg_additions"])
			representative_deletions = round(group["avg_deletions"])
			file_names = ", ".join(f"`{Path(file['filename']).name}`" for file in group["files"])
			lines.append(
				f"- Around `+{representative_additions} / -{representative_deletions}` lines: "
				f"`{len(group['files'])}` files ({file_names})"
			)
	else:
		lines.append("- No repeated change-size groups were found within the 2% tolerance.")

	lines.extend(
		[
			"",
			"<details>",
			f"<summary>Added or changed translations by language ({translation_change_count} entries across {changed_languages_count} file(s))</summary>",
			"",
		]
	)

	if translation_change_count:
		for report in reviewable_language_reports:
			if not report["changes"]:
				continue
			lines.extend(build_language_section(report))
	else:
		lines.extend(
			[
				"No added or changed translations were detected. The `.po` changes appear to be metadata, comment, or source reference updates only.",
				"",
			]
		)

	if metadata_only_reports:
		lines.extend(["### Metadata-Only File Changes", ""])
		for report in metadata_only_reports:
			lines.append(f"- `{report['language']}` (`{report['path']}`)")
		lines.append("")

	if removed_reports:
		lines.extend(["### Removed Translation Files", ""])
		for report in removed_reports:
			lines.append(f"- `{report['language']}` (`{report['path']}`)")
		lines.append("")

	if parse_errors:
		lines.extend(["### Parse Errors", ""])
		for error in parse_errors:
			lines.append(f"- `{error['path']}`: {html.escape(error['error'])}")
		lines.append("")

	lines.append("</details>")
	lines.append("")

	return "\n".join(lines)


def build_language_report(
	repo: str,
	change: dict[str, Any],
	head_sha: str,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
	"""Compare one changed `.po` file between the base checkout and PR head blob.

	The base side is read from the trusted local checkout, while the head side is
	fetched by SHA from GitHub so the workflow does not have to execute PR code.
	"""

	base_path = base_path_for_file(change)
	head_path = head_path_for_file(change)
	base_po_path = base_path if (base_path or "").endswith(".po") else None
	head_po_path = head_path if (head_path or "").endswith(".po") else None
	display_path = head_path or base_path or change.get("filename")

	try:
		base_content = read_local_file(base_po_path)
		head_content = fetch_file_content(repo, head_po_path, head_sha)

		base_language, base_entries = load_translation_entries(base_content)
		head_language, head_entries = load_translation_entries(head_content)
		language = head_language or base_language or Path(display_path).stem

		return (
			{
				"language": language,
				"path": display_path,
				"status": change.get("status"),
				"changes": compare_entries(base_entries, head_entries),
			},
			None,
		)
	except Exception as exc:
		return None, {"path": display_path, "error": str(exc)}


def main() -> None:
	"""Generate the comment body for the current PR and write it to disk."""

	args = parse_args()
	if not args.repo or not args.pr or not args.head_sha:
		raise SystemExit("Missing required pull request context.")

	all_files = fetch_pr_files(args.repo, args.pr)
	po_files = [change for change in all_files if is_po_file(change)]
	language_reports: list[dict[str, Any]] = []
	parse_errors: list[dict[str, str]] = []

	for change in po_files:
		report, error = build_language_report(args.repo, change, args.head_sha)
		if report:
			language_reports.append(report)
		if error:
			parse_errors.append(error)

	language_reports.sort(key=lambda report: (str(report["language"]).lower(), str(report["path"]).lower()))
	comment = build_comment(po_files, language_reports, cluster_similar_change_sizes(po_files), parse_errors)
	Path(args.output).write_text(comment, encoding="utf-8")


if __name__ == "__main__":
	main()
