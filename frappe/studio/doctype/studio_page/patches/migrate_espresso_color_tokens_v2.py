import re

import frappe

# Rename old espresso semantic color tokens to their espresso v2 equivalents in
# stored block styles. Mirrors frappe-ui's tokens-v2 codemod
# (frappe-ui/tailwind/migrate-tokens-v2.js) so stored values stay in sync with
# the upgraded frappe-ui. Block styles reference tokens both as CSS variables
# (var(--surface-white)) and as tailwind utilities (bg-surface-white); both
# forms are rewritten.
#
# IMPORTANT: this is a single-pass, non-idempotent rename. Several renames chain
# (surface gray 5->8, 6->9, 7->10) and the v2 scheme reuses names with different
# values (surface-gray-5 exists in both scales), so it MUST run exactly once,
# right after the frappe-ui upgrade, before any v2-token content is authored.
# The patch framework guarantees single execution.


def _shift(families, pairs):
	return {f"{family}-{old}": f"{family}-{new}" for family in families for old, new in pairs}


ACCENTS = ("red", "blue", "green", "amber", "violet")

SURFACE_RENAMES = {
	"white": "base",
	"menu-bar": "sidebar",
	"card": "elevation-1",
	"cards": "elevation-1",
	"modal": "elevation-2",
	"selected": "elevation-3",
	"gray-2-contrast": "elevation-3",
	**_shift(["gray"], [(5, 8), (6, 9), (7, 10)]),
	**_shift(ACCENTS, [(5, 7), (6, 8), (7, 9)]),
}

INK_RENAMES = {
	"white": "base",
	**_shift(ACCENTS, [(2, 5), (3, 6), (4, 8)]),
}

OUTLINE_RENAMES = {
	"white": "base",
	"gray-modal": "elevation-2",
	"gray-modals": "elevation-2",
	**_shift(["gray"], [(5, 7)]),
	**_shift(ACCENTS, [(2, 3), (3, 4), (4, 5)]),
}


def _prefix(category, renames):
	return {f"{category}-{old}": f"{category}-{new}" for old, new in renames.items()}


COLOR_TOKEN_RENAMES = {
	**_prefix("surface", SURFACE_RENAMES),
	**_prefix("ink", INK_RENAMES),
	**_prefix("outline", OUTLINE_RENAMES),
}

# Match a token whole: a leading "-" is expected (bg-surface-white,
# var(--surface-white)) but the token must not be preceded by a letter/digit nor
# followed by anything that could extend the name (gray-1 must not match in
# gray-10, gray-modal not in gray-modals). Longest-first alternation + a single
# re.sub pass keeps chained renames from cascading.
_TOKEN_RE = re.compile(
	r"(?<![A-Za-z0-9])("
	+ "|".join(re.escape(token) for token in sorted(COLOR_TOKEN_RENAMES, key=len, reverse=True))
	+ r")(?![A-Za-z0-9-])"
)


def _migrate(field_value):
	if not field_value:
		return field_value, False
	text = field_value if isinstance(field_value, str) else frappe.as_json(field_value, indent=None)
	updated = _TOKEN_RE.sub(lambda match: COLOR_TOKEN_RENAMES[match.group(1)], text)
	return updated, updated != text


def execute():
	"""Rename espresso color tokens to their v2 equivalents in stored block styles."""
	_migrate_doctype("Studio Page", ("blocks", "draft_blocks"))
	_migrate_doctype("Studio Component", ("block",))


def _migrate_doctype(doctype, fields):
	for row in frappe.get_all(doctype, fields=["name", *fields], limit_page_length=0):
		updates = {}
		for field in fields:
			value, changed = _migrate(row.get(field))
			if changed:
				updates[field] = value
		if updates:
			doc = frappe.get_doc(doctype, row.name)
			doc.update(updates)
			doc.save()
			doc.add_tag("migrated-espresso-tokens-v2")
