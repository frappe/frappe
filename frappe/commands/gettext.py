import click

from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError
from frappe.utils.bench_helper import CliCtxObj


@click.command("generate-pot-file", help="Translation: generate POT file")
@click.option("--app", help="Only generate for this app. eg: frappe")
@pass_context
def generate_pot_file(context: CliCtxObj, app: str | None = None):
	from frappe.gettext.translate import generate_pot

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	generate_pot(app)


@click.command("compile-po-to-mo", help="Translation: compile PO files to MO files")
@click.option("--app", help="Only compile for this app. eg: frappe")
@click.option(
	"--force",
	is_flag=True,
	default=False,
	help="Force compile even if there are no changes to PO files",
)
@click.option("--locale", help="Compile transaltions only for this locale. eg: de")
@pass_context
def compile_translations(context: CliCtxObj, app: str | None = None, locale: str | None = None, force=False):
	from frappe.gettext.translate import compile_translations as _compile_translations

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	_compile_translations(app, locale, force=force)


@click.command("migrate-csv-to-po", help="Translation: migrate from CSV files (old) to PO files (new)")
@click.option("--app", help="Only migrate for this app. eg: frappe")
@click.option("--locale", help="Compile translations only for this locale. eg: de")
@pass_context
def csv_to_po(context: CliCtxObj, app: str | None = None, locale: str | None = None):
	from frappe.gettext.translate import migrate

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	migrate(app, locale)


@click.command(
	"update-po-files",
	help="""Translation: sync PO files with POT file.
You might want to run generate-pot-file first.""",
)
@click.option("--app", help="Only update for this app. eg: frappe")
@click.option("--locale", help="Update PO files only for this locale. eg: de")
@pass_context
def update_po_files(context: CliCtxObj, app: str | None = None, locale: str | None = None):
	from frappe.gettext.translate import update_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	update_po(app, locale=locale)


@click.command("create-po-file", help="Translation: create a new PO file for a locale")
@click.argument("locale", nargs=1)
@click.option("--app", help="Only create for this app. eg: frappe")
@pass_context
def create_po_file(context: CliCtxObj, locale: str, app: str | None = None):
	"""Create PO file for lang code"""
	from frappe.gettext.translate import new_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	new_po(locale, app)


def _get_po_catalog(app: str, locale: str):
	"""Load PO catalog with agent-friendly error handling.

	Bypasses get_catalog() to avoid the fallback to new_catalog()
	which requires site init via frappe.get_hooks().
	"""
	import json
	import sys

	from babel.messages.pofile import read_po

	from frappe.gettext.translate import get_po_path

	try:
		po_path = get_po_path(app, locale)
	except ModuleNotFoundError:
		click.echo(json.dumps({"error": "app_not_found", "app": app}), err=True)
		sys.exit(1)

	if not po_path.exists():
		click.echo(json.dumps({"error": "po_file_not_found", "path": str(po_path)}), err=True)
		sys.exit(1)

	with open(po_path, "rb") as f:
		return read_po(f)


def _get_apps() -> list[str]:
	"""Get list of installed apps from sites/apps.txt without requiring site init."""
	from pathlib import Path

	from frappe.utils import get_bench_path

	apps_txt = Path(get_bench_path()) / "sites" / "apps.txt"
	if not apps_txt.exists():
		return ["frappe"]
	return [line.strip() for line in apps_txt.read_text().splitlines() if line.strip()]


def _try_get_po_catalog(app: str, locale: str):
	"""Load PO catalog for an app/locale, returning None if the PO file doesn't exist."""
	from babel.messages.pofile import read_po

	from frappe.gettext.translate import get_po_path

	try:
		po_path = get_po_path(app, locale)
	except ModuleNotFoundError:
		return None

	if not po_path.exists():
		return None

	with open(po_path, "rb") as f:
		return read_po(f)


def _encode_po_string(s: str) -> str:
	"""Encode a string as a PO file msgstr value, matching common PO formatting.

	Single-line strings: msgstr "value"
	Multiline strings starting with \\n: msgstr ""\n"\\n"\n"rest..."
	Multiline strings not starting with \\n: msgstr "first line\\n"\n"rest..."
	"""
	s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t")
	if "\n" not in s:
		return f'"{s}"'
	lines = s.split("\n")
	parts = []
	for i, line in enumerate(lines):
		suffix = "\\n" if i < len(lines) - 1 else ""
		parts.append(f'"{line}{suffix}"')
	# If the string starts with \n, the first part is just "\\n" — use empty first line style
	if s.startswith("\n"):
		parts.insert(0, '""')
	return "\n".join(parts)


def _replace_msgstr(content: str, msgid: str, new_msgstr: str, context: str | None = None) -> str:
	"""Replace the msgstr of a specific entry in PO file content (text-based).

	Finds the entry by matching the msgid (and optional msgctxt), then replaces
	only the msgstr line(s), preserving all other content and formatting.
	"""
	import re

	lines = content.split("\n")
	i = 0
	while i < len(lines):
		line = lines[i]

		# Detect msgctxt
		entry_context = None
		if line.startswith("msgctxt "):
			entry_context = _decode_po_value(lines, i)
			i += 1
			while i < len(lines) and lines[i].startswith('"'):
				i += 1

		# Detect msgid
		if i < len(lines) and lines[i].startswith("msgid "):
			entry_msgid = _decode_po_value(lines, i)
			i += 1
			while i < len(lines) and lines[i].startswith('"'):
				i += 1
		else:
			i += 1
			continue

		# Detect msgstr
		if i < len(lines) and lines[i].startswith("msgstr "):
			msgstr_start = i
			i += 1
			while i < len(lines) and lines[i].startswith('"'):
				i += 1
			msgstr_end = i
		else:
			continue

		# Check if this is the entry we're looking for
		if entry_msgid == msgid and entry_context == context:
			encoded = _encode_po_string(new_msgstr)
			new_lines = lines[:msgstr_start]
			new_lines.append(f"msgstr {encoded}")
			new_lines.extend(lines[msgstr_end:])
			return "\n".join(new_lines)

		# i is already past msgstr, continue from there

	return content


def _decode_po_value(lines: list[str], start: int) -> str:
	"""Decode a msgid/msgstr/msgctxt value from PO file lines starting at `start`."""
	import re

	result_parts = []
	# First line: extract value after keyword (msgid "...", msgstr "...", msgctxt "...")
	m = re.match(r'^(?:msgid|msgstr|msgctxt)\s+"(.*)"$', lines[start])
	if m:
		result_parts.append(m.group(1))
	i = start + 1
	# Continuation lines: bare quoted strings
	while i < len(lines) and lines[i].startswith('"'):
		m = re.match(r'^"(.*)"$', lines[i])
		if m:
			result_parts.append(m.group(1))
		i += 1
	raw = "".join(result_parts)
	# Unescape PO escapes
	raw = raw.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")
	return raw


def _word_similarity(a: str, b: str) -> float:
	words_a = set(a.lower().split())
	words_b = set(b.lower().split())
	if not words_a or not words_b:
		return 0.0
	return len(words_a & words_b) / len(words_a | words_b)


@click.command("get-missing-translation", help="Translation: get one untranslated entry as JSON")
@click.option("--app", required=True, help="App name. eg: frappe")
@click.option("--locale", required=True, help="Locale code. eg: de")
@click.option(
	"--entry-start",
	default=0,
	type=click.IntRange(min=0),
	help="Inclusive absolute entry index to scan from",
)
@click.option(
	"--entry-end",
	default=None,
	type=click.IntRange(min=0),
	help="Exclusive absolute entry index to scan to",
)
@click.option(
	"--offset",
	default=0,
	type=click.IntRange(min=0),
	help="Skip first N missing entries within the selected entry range",
)
def get_missing_translation(
	app: str,
	locale: str,
	entry_start: int = 0,
	entry_end: int | None = None,
	offset: int = 0,
):
	"""Return one untranslated PO entry as JSON to stdout.

	Outputs a JSON object with the entry's msgid, context, locations, comments,
	and shard metadata. Use --entry-start/--entry-end to split the PO file by
	absolute entry index and --offset to skip missing entries within that range.
	When no missing entries remain in the selected range or offset exceeds the
	range's missing count, outputs shard metadata with no entry fields.

	Does not require a site connection.

	Usage:
	    bench get-missing-translation --app frappe --locale de
	    bench get-missing-translation --app frappe --locale de --offset 5
	    bench get-missing-translation --app frappe --locale de --entry-start 100 --entry-end 200
	"""
	import json

	catalog = _get_po_catalog(app, locale)

	entries = []
	for message in catalog:
		if not message.id or isinstance(message.id, tuple):
			continue

		entries.append(message)

	total_entries = len(entries)
	shard_start = min(entry_start, total_entries)
	shard_end = min(entry_end, total_entries) if entry_end is not None else total_entries
	shard_end = max(shard_start, shard_end)
	shard_entries = entries[shard_start:shard_end]

	missing = [
		(shard_start + shard_index, message)
		for shard_index, message in enumerate(shard_entries)
		if not message.string
	]
	total_missing = len(missing)
	response = {
		"total_missing": total_missing,
		"total_entries": total_entries,
		"total_entries_in_shard": len(shard_entries),
		"entry_start": shard_start,
		"entry_end": shard_end,
	}

	if total_missing == 0 or offset >= total_missing:
		click.echo(json.dumps(response))
		return

	entry_index, message = missing[offset]
	response.update(
		{
			"index": offset,
			"entry_index": entry_index,
			"msgid": message.id,
			"context": message.context,
			"locations": list(message.locations),
			"comments": list(message.auto_comments),
		}
	)
	click.echo(json.dumps(response))


@click.command("search-translated", help="Translation: search translated entries by terms across all apps")
@click.option("--app", default=None, help="Limit to this app. eg: frappe. Searches all apps if omitted.")
@click.option("--locale", required=True, help="Locale code. eg: de")
@click.option("--terms", required=True, help="Comma-separated search terms. eg: invoice,sales")
@click.option("--limit", default=5, type=int, help="Max results to return")
def search_translated(app: str | None, locale: str, terms: str, limit: int = 5):
	"""Search already-translated PO entries by keyword and return matches as JSON.

	Searches across all installed apps by default, or a single app with --app.
	Performs case-insensitive substring matching with OR logic — an entry matches
	if its msgid contains ANY of the comma-separated terms. Results are sorted by
	number of matched terms (most relevant first) and include the translated msgstr
	for reference.

	Only returns entries that have a non-empty translation.
	Does not require a site connection.

	Usage:
	    bench search-translated --locale de --terms "invoice,sales"
	    bench search-translated --app frappe --locale de --terms "email" --limit 3
	"""
	import json

	terms_lower = [t.strip().lower() for t in terms.split(",") if t.strip()]
	if not terms_lower:
		click.echo("[]")
		return

	if app:
		app_catalogs = [(app, _get_po_catalog(app, locale))]
	else:
		app_catalogs = []
		for app_name in _get_apps():
			catalog = _try_get_po_catalog(app_name, locale)
			if catalog is not None:
				app_catalogs.append((app_name, catalog))

	results = []
	for app_name, catalog in app_catalogs:
		for message in catalog:
			if not message.id or isinstance(message.id, tuple):
				continue
			if not message.string:
				continue

			msgid_lower = message.id.lower()
			matched = [t for t in terms_lower if t in msgid_lower]
			if matched:
				results.append(
					{
						"msgid": message.id,
						"msgstr": message.string,
						"context": message.context,
						"locations": list(message.locations),
						"comments": list(message.auto_comments),
						"matched_terms": matched,
						"app": app_name,
					}
				)

	results.sort(key=lambda r: len(r["matched_terms"]), reverse=True)
	click.echo(json.dumps(results[:limit]))


@click.command("update-translation", help="Translation: update translations from JSON stdin")
@click.option("--app", required=True, help="App name. eg: frappe")
@click.option("--locale", required=True, help="Locale code. eg: de")
def update_translation(app: str, locale: str):
	"""Update translations in a PO file from JSON provided via stdin.

	Accepts a JSON object or array of objects, each with "msgid", "msgstr", and
	optional "context" fields. Validates all msgids exist in the catalog before
	writing any changes (atomic: no partial updates).

	On success, outputs {"updated": N} to stdout.
	On error (msgid not found, invalid JSON), outputs error JSON to stderr and
	exits with code 1. Error includes similar msgids to help self-correct typos.

	Does not require a site connection.

	Usage:
	    echo '{"msgid":"Hello","msgstr":"Hallo"}' | bench update-translation --app frappe --locale de
	    echo '[{"msgid":"A","msgstr":"X"},{"msgid":"B","msgstr":"Y"}]' | bench update-translation --app frappe --locale de
	"""
	import json
	import sys

	try:
		raw = click.get_text_stream("stdin").read()
		data = json.loads(raw)
	except (json.JSONDecodeError, ValueError) as e:
		click.echo(json.dumps({"error": "invalid_json", "detail": str(e)}), err=True)
		sys.exit(1)

	if isinstance(data, dict):
		data = [data]
	elif not isinstance(data, list):
		click.echo(json.dumps({"error": "invalid_json", "detail": "Expected object or array"}), err=True)
		sys.exit(1)

	normalized_entries = []
	for index, entry in enumerate(data):
		if not isinstance(entry, dict):
			click.echo(
				json.dumps(
					{
						"error": "invalid_json",
						"detail": "Expected each array item to be an object",
						"index": index,
					}
				),
				err=True,
			)
			sys.exit(1)

		normalized_entries.append((entry.get("msgid", ""), entry.get("context"), entry.get("msgstr", "")))

	catalog = _get_po_catalog(app, locale)

	validated = []
	for msgid, context, msgstr in normalized_entries:
		message = catalog.get(msgid, context)
		if message is None:
			similarities = []
			for m in catalog:
				if not m.id or isinstance(m.id, tuple) or not m.id.strip():
					continue
				score = _word_similarity(msgid, m.id)
				if score > 0:
					similarities.append((score, m.id))
			similarities.sort(reverse=True)
			similar = [s[1] for s in similarities[:3]]

			click.echo(
				json.dumps(
					{
						"error": "msgid_not_found",
						"msgid": msgid,
						"context": context,
						"similar": similar,
					}
				),
				err=True,
			)
			sys.exit(1)

		validated.append((msgid, context, msgstr))

	from frappe.gettext.translate import get_po_path

	po_path = get_po_path(app, locale)
	content = po_path.read_text(encoding="utf-8")
	for msgid, context, msgstr in validated:
		content = _replace_msgstr(content, msgid, msgstr, context)
	po_path.write_text(content, encoding="utf-8")

	click.echo(json.dumps({"updated": len(validated)}))


def connect_to_site(site):
	from frappe import connect

	if not site:
		raise SiteNotSpecifiedError

	connect(site=site)


commands = [
	generate_pot_file,
	compile_translations,
	csv_to_po,
	update_po_files,
	create_po_file,
	get_missing_translation,
	search_translated,
	update_translation,
]
