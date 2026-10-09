import frappe

STYLE_PRESETS = {
	"Modern": {
		"table": {"table_style": "lined", "table_bordered": False, "table_radius": 6},
	},
	"Classic": {
		"section": {"field_borders": 1, "cell_padding": 6, "radius": 0},
		"table": {"table_style": "lined", "table_bordered": True, "table_radius": 0},
	},
	"Bold": {
		"table": {
			"table_style": "lined",
			"table_bordered": False,
			"table_radius": 6,
			"table_header_bg": "#171717",
		},
	},
	"Striped": {
		"table": {
			"table_style": "striped",
			"table_bordered": False,
			"table_header": "plain",
			"table_cell_padding": 5,
		},
	},
	"Monochrome": {
		"table": {"table_style": "lined", "table_bordered": True, "table_header": "plain", "table_radius": 0},
	},
}


def get_style_presets() -> dict:
	presets = dict(STYLE_PRESETS)
	for hook in frappe.get_hooks("print_style_presets"):
		presets.update(frappe.get_attr(hook)() or {})
	return presets


def apply_style_preset(layout: dict, style: str | None) -> dict:
	preset = get_style_presets().get(style) if style else None
	if not preset or not isinstance(layout, dict):
		return layout
	for section in layout.get("sections") or []:
		if section.get("columns") and any(
			f.get("fieldtype") != "Table" for col in section["columns"] for f in col.get("fields") or []
		):
			section.update(preset.get("section") or {})
		for col in section.get("columns") or []:
			for field in col.get("fields") or []:
				if field.get("fieldtype") == "Table":
					field.update(preset.get("table") or {})
	return layout
