import re

import frappe


def execute():
	"""rawStyles were dropped in favour of baseStyles; fold them into baseStyles.
	Saves through the controller so exported page/component files are rewritten too."""
	_migrate_doctype("Studio Page", ("blocks", "draft_blocks"))
	_migrate_doctype("Studio Component", ("block",))


def _migrate_doctype(doctype, fields):
	for row in frappe.get_all(doctype, fields=["name", *fields], limit_page_length=0):
		updates = {}
		for field in fields:
			raw_json = row.get(field)
			if not raw_json or "rawStyles" not in raw_json:
				continue
			blocks = frappe.parse_json(raw_json)
			if not blocks:
				continue
			# Studio Page stores a list of blocks, Studio Component a single root block
			is_single_block = isinstance(blocks, dict)
			folded = fold_raw_styles([blocks] if is_single_block else blocks)
			updates[field] = frappe.as_json(folded[0] if is_single_block else folded)
		if updates:
			doc = frappe.get_doc(doctype, row.name)
			doc.update(updates)
			doc.flags.ignore_links = True
			doc.save()


def fold_raw_styles(blocks):
	for block in blocks:
		if not isinstance(block, dict):
			continue

		raw_styles = block.pop("rawStyles", None) or {}
		if raw_styles:
			base_styles = block.get("baseStyles") or {}
			for key, value in raw_styles.items():
				if value in (None, ""):
					continue
				base_styles[to_camel_case(key)] = value
			block["baseStyles"] = base_styles

		if block.get("children"):
			block["children"] = fold_raw_styles(block["children"])
		if isinstance(block.get("componentSlots"), dict):
			for slot in block["componentSlots"].values():
				# older blocks store the block list directly on the slot, newer ones wrap it
				# in {slotContent: [...]}; slotContent may also be a plain string (text slot)
				content = slot.get("slotContent") if isinstance(slot, dict) else slot
				if isinstance(content, list):
					fold_raw_styles(content)

	return blocks


def to_camel_case(css_property):
	# custom properties (--card-color) are case-sensitive identifiers, never camelCased
	if css_property.startswith("--"):
		return css_property
	return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), css_property)
