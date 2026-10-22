import re

import frappe

# Shift espresso text-size tokens to their v2 names in stored block styles.
# Espresso v2 inserted a new 17px stop (text-xl), shifting every size from xl upward by one name.
# Mirrors the unmigrated size shift in frappe-ui's tokens-v2 codemod (frappe-ui/tailwind/migrate-tokens-v2.js) and covers every form:
# bare sizes (text-xl), paragraph variants (text-p-xl) and the weighted component classes (text-xl-medium, ...).

SIZE_SHIFT = [
	("xl", "2xl"),
	("2xl", "3xl"),
	("3xl", "4xl"),
	("4xl", "5xl"),
	("5xl", "6xl"),
	("6xl", "7xl"),
	("7xl", "8xl"),
	("8xl", "9xl"),
	("9xl", "10xl"),
	("10xl", "11xl"),
	("11xl", "12xl"),
	("12xl", "13xl"),
	("13xl", "14xl"),
	("14xl", "15xl"),
	("15xl", "16xl"),
]

WEIGHTS = ("medium", "semibold", "bold", "black")


def _size_renames():
	renames = {}
	for old, new in SIZE_SHIFT:
		for prefix in ("text-", "text-p-"):
			renames[f"{prefix}{old}"] = f"{prefix}{new}"
			for weight in WEIGHTS:
				renames[f"{prefix}{old}-{weight}"] = f"{prefix}{new}-{weight}"
	return renames


TEXT_SIZE_RENAMES = _size_renames()

# Whole-token match (same boundary rules as the color-token patch): not preceded
# by a letter/digit, not followed by anything that extends the name (text-2xl
# must not match inside text-12xl or text-2xl-medium). Longest-first alternation
# + a single re.sub pass keeps the chained shifts from cascading.
_TOKEN_RE = re.compile(
	r"(?<![A-Za-z0-9])("
	+ "|".join(re.escape(token) for token in sorted(TEXT_SIZE_RENAMES, key=len, reverse=True))
	+ r")(?![A-Za-z0-9-])"
)


def _migrate(field_value):
	if not field_value:
		return field_value, False
	text = field_value if isinstance(field_value, str) else frappe.as_json(field_value, indent=None)
	updated = _TOKEN_RE.sub(lambda match: TEXT_SIZE_RENAMES[match.group(1)], text)
	return updated, updated != text


def execute():
	"""Shift espresso text-size tokens to their v2 names in stored block styles."""
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
			doc.add_tag("migrated-espresso-text-sizes-v2")
