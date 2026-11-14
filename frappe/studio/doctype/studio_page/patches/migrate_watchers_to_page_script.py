import re

import frappe

MARKER = "// Migrated from page watchers — review the generated watch() calls."

# A bare variable is a ref in the page-script context, so `watch(name, ...)` watches its value.
# Anything else (member paths like `user.name`, expressions) needs a getter, `watch(() => expr, ...)`.
IDENTIFIER = re.compile(r"^[A-Za-z_$][\w$]*$")


def execute():
	"""Fold legacy `Studio Page Watcher` rows into each page's `script` as watch()/watchDebounced()
	calls. The doctype/table was retired in favour of page scripts (lifecycle now owned by the page
	script's effectScope).

	Only non-exported (interpreted) pages are migrated: exported pages run in code mode where the
	script lives in the on-disk `<page>.ts`, so the DB `script` field isn't loaded there."""
	if not frappe.db.table_exists("Studio Page Watcher"):
		return

	watchers_by_page = _read_watchers()
	for page_name, watchers in watchers_by_page.items():
		_migrate_page(page_name, watchers)


def _read_watchers() -> dict[str, list[frappe._dict]]:
	watcher = frappe.qb.DocType("Studio Page Watcher")
	rows = (
		frappe.qb.from_(watcher)
		.select(
			watcher.parent, watcher.source, watcher.script, watcher.immediate, watcher.deep, watcher.debounce
		)
		.where(watcher.parenttype == "Studio Page")
		.orderby(watcher.parent)
		.orderby(watcher.idx)
		.run(as_dict=True)
	)
	grouped: dict[str, list[frappe._dict]] = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def _migrate_page(page_name: str, watchers: list[frappe._dict]) -> None:
	if not frappe.db.exists("Studio Page", page_name):
		return

	page = frappe.get_doc("Studio Page", page_name)
	# Exported pages run in code mode — their script is the on-disk <page>.ts, not this DB field —
	# so appending here would be dead code. Only interpreted (non-exported) pages use page.script.
	if page.is_standard:
		return

	existing = page.script or ""
	if MARKER in existing:
		return  # already migrated

	generated = MARKER + "\n\n" + "\n\n".join(_generate_watcher(w) for w in watchers)
	page.script = (existing.rstrip() + "\n\n" + generated + "\n") if existing.strip() else generated + "\n"
	page.save()


def _generate_watcher(watcher: frappe._dict) -> str:
	source = (watcher.source or "").strip()
	source_arg = source if IDENTIFIER.match(source) else "() => " + source
	body = _indent((watcher.script or "").strip())
	handler = "() => {\n" + body + "\n}"

	fn = "watchDebounced" if _debounce(watcher) else "watch"
	args = [source_arg, handler]
	options = _watch_options(watcher)
	if options:
		args.append(options)
	return fn + "(" + ", ".join(args) + ")"


def _watch_options(watcher: frappe._dict) -> str:
	parts = []
	if _debounce(watcher):
		parts.append("debounce: " + str(_debounce(watcher)))
	if watcher.immediate:
		parts.append("immediate: true")
	if watcher.deep:
		parts.append("deep: true")
	return "{ " + ", ".join(parts) + " }" if parts else ""


def _debounce(watcher: frappe._dict) -> int:
	return int(watcher.debounce or 0)


def _indent(code: str, tab: str = "\t") -> str:
	return "\n".join((tab + line) if line.strip() else "" for line in code.splitlines())
