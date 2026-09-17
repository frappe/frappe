export const DRAFT_SETTING_FIELDS = [
	"font",
	"font_size",
	"page_number",
	"show_label_colon",
	"margin_top",
	"margin_bottom",
	"margin_left",
	"margin_right",
	"label_color",
	"value_color",
	"css",
	"pdf_generator",
];

function setting_label(fieldname) {
	return frappe.meta.get_docfield("Print Format", fieldname)?.label || frappe.unscrub(fieldname);
}

function show_value(fieldname, value) {
	if (value == null || value === "") return __("Default");
	if (fieldname === "show_label_colon") return value ? __("Yes") : __("No");
	if (fieldname === "css") return __("{0} lines", [String(value).split("\n").length]);
	return String(value);
}

function parse_layout(format_data) {
	if (!format_data) return null;
	const layout =
		typeof format_data === "string" ? frappe.utils.parse_json(format_data) : format_data;
	return layout && typeof layout === "object" && !Array.isArray(layout) ? layout : null;
}

function layout_fields(layout) {
	const out = new Map();
	const zones = [layout.header, ...(layout.sections || []), layout.footer].filter(Boolean);
	zones.forEach((zone, zi) => {
		if (zone.remove) return;
		(zone.columns || []).forEach((col, ci) => {
			(col.fields || []).forEach((f) => {
				if (f.remove || !f.fieldname) return;
				out.set(f.fieldname, { label: f.label || f.fieldname, zone: zi, col: ci });
			});
		});
	});
	return out;
}

function live_sections(layout) {
	return (layout.sections || []).filter((s) => !s.remove).length;
}

export function describe_draft_changes(applied, current) {
	const groups = [];

	const settings = DRAFT_SETTING_FIELDS.filter(
		(f) => String(applied[f] ?? "") !== String(current[f] ?? "")
	).map(
		(f) => `${setting_label(f)}: ${show_value(f, applied[f])} → ${show_value(f, current[f])}`
	);
	if (settings.length) groups.push({ title: __("Settings"), lines: settings });

	const base = parse_layout(applied.format_data);
	const next = parse_layout(current.format_data);
	const lines = [];
	if (!base && next) {
		lines.push(__("Layout created"));
	} else if (base && next) {
		const before = layout_fields(base);
		const after = layout_fields(next);
		for (const [key, f] of after) {
			if (!before.has(key)) lines.push(__("Added {0}", [f.label]));
			else if (before.get(key).zone !== f.zone || before.get(key).col !== f.col) {
				lines.push(__("Moved {0}", [f.label]));
			}
		}
		for (const [key, f] of before) {
			if (!after.has(key)) lines.push(__("Removed {0}", [f.label]));
		}
		const delta = live_sections(next) - live_sections(base);
		if (delta > 0) lines.push(__("{0} section(s) added", [delta]));
		if (delta < 0) lines.push(__("{0} section(s) removed", [-delta]));
		if ((base.letter_head ?? "") !== (next.letter_head ?? "")) {
			lines.push(
				`${__("Letter Head")}: ${base.letter_head || __("Default")} → ${
					next.letter_head || __("Default")
				}`
			);
		}
		if (!lines.length && JSON.stringify(base) !== JSON.stringify(next)) {
			lines.push(__("Styling, spacing or ordering changed"));
		}
	}
	if (lines.length) groups.push({ title: __("Layout"), lines });
	return groups;
}
