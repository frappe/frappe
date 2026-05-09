"""Generate a review-friendly summary for large translation PRs.

This helper runs in GitHub Actions for bot-authored `.po` pull requests.
It compares the trusted base checkout against the PR head translation files,
groups similarly sized file diffs, and posts one or more markdown comments with
the high-signal translation changes that are hard to inspect in GitHub's UI
(split when content would exceed GitHub's comment size limit).
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
MAX_COMMENT_BODY_CHARS = 60_000 # GitHub caps issue comments at 65536 characters
TOO_MANY_CHANGES_MESSAGE = "Too many changes to fit into a comment."
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
		description="Build PR review comment(s) for .po file changes; write JSON with a `comments` array."
	)
	parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
	parser.add_argument("--pr", type=int, default=os.environ.get("PR_NUMBER"))
	parser.add_argument("--head-sha", default=os.environ.get("PR_HEAD_SHA"))
	parser.add_argument("--output", default="po-pr-review-comments.json")
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


def build_oversized_language_section(report: dict[str, Any]) -> str:
	"""Render a compact placeholder for language sections that exceed comment limits."""

	return "\n".join(
		[
			f"### `{report['language']}` (`{report['path']}`)",
			"",
			f"_{TOO_MANY_CHANGES_MESSAGE}_",
		]
	)


def _review_context(
	po_files: list[dict[str, Any]],
	language_reports: list[dict[str, Any]],
	similar_groups: list[dict[str, Any]],
	parse_errors: list[dict[str, str]],
) -> dict[str, Any]:
	"""Shared stats and report slices used to build one or more PR comments."""

	status_counts = Counter(change.get("status", "modified") for change in po_files)
	reviewable_language_reports = [
		report for report in language_reports if not should_hide_report_from_review(report)
	]
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

	return {
		"status_counts": status_counts,
		"total_files": len(po_files),
		"reviewable_language_reports": reviewable_language_reports,
		"grouped_files_count": sum(len(group["files"]) for group in similar_groups),
		"translation_change_count": translation_change_count,
		"changed_languages_count": changed_languages_count,
		"removed_reports": removed_reports,
		"metadata_only_reports": metadata_only_reports,
		"similar_groups": similar_groups,
		"parse_errors": parse_errors,
	}


def _build_prefix_lines(ctx: dict[str, Any]) -> list[str]:
	status_counts = ctx["status_counts"]
	total_files = ctx["total_files"]
	grouped_files_count = ctx["grouped_files_count"]
	translation_change_count = ctx["translation_change_count"]
	changed_languages_count = ctx["changed_languages_count"]
	parse_errors: list[dict[str, str]] = ctx["parse_errors"]
	similar_groups: list[dict[str, Any]] = ctx["similar_groups"]

	lines = [
		COMMENT_MARKER,
		"Here is a summary of the `.po` file changes:",
		"",
		f"- Changed files: `{total_files}`",
		f"- Added files: `{status_counts['added']}`",
		f"- Removed files: `{status_counts['removed']}`",
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
			file_names = ", ".join(f"`{Path(change['filename']).name}`" for change in group["files"])
			lines.append(
				f"- Around `+{representative_additions} / -{representative_deletions}` lines: "
				f"`{len(group['files'])}` files ({file_names})"
			)
	else:
		lines.append("- No repeated change-size groups were found within the 2% tolerance.")

	return lines


def _build_suffix_lines(ctx: dict[str, Any]) -> list[str]:
	metadata_only_reports: list[dict[str, Any]] = ctx["metadata_only_reports"]
	removed_reports: list[dict[str, Any]] = ctx["removed_reports"]
	parse_errors: list[dict[str, str]] = ctx["parse_errors"]

	lines: list[str] = []

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

	return lines


def _continuation_marker(part_index: int, total_parts: int) -> str:
	"""Marker for follow-up comments; part_index and total_parts are 1-based."""

	return f"<!-- po-translation-review part {part_index}/{total_parts} -->"


def _details_summary(
	*,
	part_index: int,
	total_parts: int,
	translation_change_count: int,
	changed_languages_count: int,
) -> str:
	if total_parts == 1:
		return (
			f"Added or changed translations by language ({translation_change_count} entries across "
			f"{changed_languages_count} file(s))"
		)
	return (
		f"Added or changed translations by language (part {part_index} of {total_parts}, "
		f"{translation_change_count} entries across {changed_languages_count} file(s))"
	)


def _render_review_comment(
	*,
	part_index: int,
	total_parts: int,
	prefix_text: str,
	section_bodies: list[str],
	suffix_text: str,
	translation_change_count: int,
	changed_languages_count: int,
	empty_translation_body: str | None,
) -> str:
	"""Assemble one GitHub issue comment body (single <details> block)."""

	head = prefix_text if part_index == 1 else f"{_continuation_marker(part_index, total_parts)}\n\n"
	summary = _details_summary(
		part_index=part_index,
		total_parts=total_parts,
		translation_change_count=translation_change_count,
		changed_languages_count=changed_languages_count,
	)
	if section_bodies:
		inner = "\n\n".join(section_bodies)
	else:
		inner = empty_translation_body or ""

	if inner and suffix_text:
		full_inner = f"{inner}\n{suffix_text}"
	elif suffix_text:
		full_inner = suffix_text
	else:
		full_inner = inner

	return (
		f"{head}<details>\n<summary>{summary}</summary>\n\n{full_inner}\n</details>\n"
	)


def _section_fits_in_comment(
	section: str,
	*,
	prefix_text: str,
	suffix_text: str,
	translation_change_count: int,
	changed_languages_count: int,
	max_body_chars: int,
	total_parts_upper_bound: int,
) -> bool:
	"""Return whether a language section can fit as a standalone comment body."""

	# Size against the longest plausible summary/marker text (multi-part copy scales with total_parts).
	t_parts = max(total_parts_upper_bound, 1)
	body = _render_review_comment(
		part_index=1,
		total_parts=t_parts,
		prefix_text=prefix_text,
		section_bodies=[section],
		suffix_text=suffix_text,
		translation_change_count=translation_change_count,
		changed_languages_count=changed_languages_count,
		empty_translation_body=None,
	)
	return len(body) <= max_body_chars


def _pack_sections_into_comments(
	flat_sections: list[str],
	*,
	prefix_text: str,
	suffix_text: str,
	translation_change_count: int,
	changed_languages_count: int,
	max_body_chars: int,
	total_parts_guess: int,
) -> list[list[str]]:
	"""Group section bodies into chunks that each fit GitHub comment limits."""

	groups: list[list[str]] = []
	cur: list[str] = []
	index = 0
	n = len(flat_sections)

	while index < n:
		sec = flat_sections[index]
		more_after = index < n - 1
		trial = [*cur, sec]
		part_no = len(groups) + 1
		is_last_segment = not more_after
		body_try = _render_review_comment(
			part_index=part_no,
			total_parts=total_parts_guess,
			prefix_text=prefix_text,
			section_bodies=trial,
			suffix_text=suffix_text if is_last_segment else "",
			translation_change_count=translation_change_count,
			changed_languages_count=changed_languages_count,
			empty_translation_body=None,
		)
		if len(body_try) <= max_body_chars:
			cur = trial
			index += 1
			continue

		if cur:
			groups.append(cur)
			cur = []
			continue

		raise RuntimeError(
			f"A single translation section does not fit in one comment ({len(body_try)} chars). "
			"Improve splitting or raise MAX_COMMENT_BODY_CHARS."
		)

	if cur:
		groups.append(cur)

	return groups


def build_comment_bodies(
	po_files: list[dict[str, Any]],
	language_reports: list[dict[str, Any]],
	similar_groups: list[dict[str, Any]],
	parse_errors: list[dict[str, str]],
	max_body_chars: int = MAX_COMMENT_BODY_CHARS,
) -> list[str]:
	"""Build one or more PR comment bodies, each under GitHub's size limit."""

	ctx = _review_context(po_files, language_reports, similar_groups, parse_errors)
	prefix_text = "\n".join(_build_prefix_lines(ctx)) + "\n\n"
	suffix_lines = _build_suffix_lines(ctx)
	suffix_text = "\n".join(suffix_lines) if suffix_lines else ""
	translation_change_count = ctx["translation_change_count"]
	changed_languages_count = ctx["changed_languages_count"]
	reviewable: list[dict[str, Any]] = ctx["reviewable_language_reports"]

	language_reports_with_changes = [report for report in reviewable if report["changes"]]
	max_comment_segments = len(language_reports_with_changes)

	if not language_reports_with_changes:
		empty_body = (
			"No added or changed translations were detected. The `.po` changes appear to be metadata, "
			"comment, or source reference updates only.\n"
		)
		body = _render_review_comment(
			part_index=1,
			total_parts=1,
			prefix_text=prefix_text,
			section_bodies=[],
			suffix_text=suffix_text,
			translation_change_count=translation_change_count,
			changed_languages_count=changed_languages_count,
			empty_translation_body=empty_body,
		)
		if len(body) > max_body_chars:
			raise RuntimeError("Single metadata-only review comment exceeds max_body_chars; shorten prefix or raise limit.")
		return [body]

	flat_sections: list[str] = []
	for report in language_reports_with_changes:
		section = "\n".join(build_language_section(report)).rstrip()
		if not _section_fits_in_comment(
			section,
			prefix_text=prefix_text,
			suffix_text=suffix_text,
			translation_change_count=translation_change_count,
			changed_languages_count=changed_languages_count,
			max_body_chars=max_body_chars,
			total_parts_upper_bound=max_comment_segments,
		):
			section = build_oversized_language_section(report)
		flat_sections.append(section)

	groups = _pack_sections_into_comments(
		flat_sections,
		prefix_text=prefix_text,
		suffix_text=suffix_text,
		translation_change_count=translation_change_count,
		changed_languages_count=changed_languages_count,
		max_body_chars=max_body_chars,
		total_parts_guess=max(len(flat_sections), 1),
	)
	total_parts = len(groups)
	bodies: list[str] = []

	for idx, sections_in_group in enumerate(groups):
		part_no = idx + 1
		is_last = part_no == total_parts
		body = _render_review_comment(
			part_index=part_no,
			total_parts=total_parts,
			prefix_text=prefix_text,
			section_bodies=sections_in_group,
			suffix_text=suffix_text if is_last else "",
			translation_change_count=translation_change_count,
			changed_languages_count=changed_languages_count,
			empty_translation_body=None,
		)
		if len(body) > max_body_chars:
			raise RuntimeError(
				f"PO review comment part {part_no}/{total_parts} is {len(body)} characters; "
				"raise MAX_COMMENT_BODY_CHARS or improve packing."
			)
		bodies.append(body)

	return bodies


def _oversized_review_fallback_body(exc: RuntimeError) -> str:
	"""Short marker comment when full review output cannot be packed under GitHub limits."""

	detail = html.escape(str(exc))
	max_detail = 800
	if len(detail) > max_detail:
		detail = f"{detail[:max_detail]}…"
	return (
		f"{COMMENT_MARKER}\n\n"
		"The automated `.po` translation review could not be split to fit GitHub's comment size limit.\n\n"
		f"**Reason:** {detail}\n"
	)


def build_comment(
	po_files: list[dict[str, Any]],
	language_reports: list[dict[str, Any]],
	similar_groups: list[dict[str, Any]],
	parse_errors: list[dict[str, str]],
) -> str:
	"""Build the first PR comment body (for tests and ad-hoc use)."""

	return build_comment_bodies(po_files, language_reports, similar_groups, parse_errors)[0]


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
	"""Generate PO review comment bodies for the current PR and write them as JSON."""

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
	try:
		similar_groups = cluster_similar_change_sizes(po_files)
		bodies = build_comment_bodies(po_files, language_reports, similar_groups, parse_errors)
	except RuntimeError as exc:
		bodies = [_oversized_review_fallback_body(exc)]
	Path(args.output).write_text(json.dumps({"comments": bodies}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
	main()
