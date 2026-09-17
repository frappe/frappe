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
	const seen = {};
	const zones = [layout.header, ...(layout.sections || []), layout.footer].filter(Boolean);
	zones.forEach((zone, zi) => {
		if (zone.remove) return;
		(zone.columns || []).forEach((col, ci) => {
			(col.fields || []).forEach((f) => {
				if (f.remove || !f.fieldname) return;
				seen[f.fieldname] = (seen[f.fieldname] || 0) + 1;
				out.set(`${f.fieldname}#${seen[f.fieldname]}`, {
					fieldname: f.fieldname,
					label: f.label || f.fieldname,
					zone: zi,
					col: ci,
					json: JSON.stringify(f),
				});
			});
		});
	});
	return out;
}

export function describe_draft_changes(saved, current) {
	const settings = DRAFT_SETTING_FIELDS.filter(
		(f) => String(saved[f] ?? "") !== String(current[f] ?? "")
	).map((f) => `${setting_label(f)}: ${show_value(f, saved[f])} → ${show_value(f, current[f])}`);

	const added = [];
	const moved = [];
	const changed = [];
	const removed = [];
	const base = parse_layout(saved.format_data);
	const next = parse_layout(current.format_data);
	if (base && next) {
		const before = layout_fields(base);
		const after = layout_fields(next);
		for (const [key, f] of after) {
			const old = before.get(key);
			if (!old) added.push(f.fieldname);
			else if (old.zone !== f.zone || old.col !== f.col) moved.push(f.fieldname);
			else if (old.json !== f.json) changed.push(f.fieldname);
		}
		for (const [key, f] of before) if (!after.has(key)) removed.push(f.label);
	}
	return {
		settings,
		added,
		moved,
		changed,
		removed,
		highlight: [...new Set([...added, ...moved, ...changed])],
	};
}
