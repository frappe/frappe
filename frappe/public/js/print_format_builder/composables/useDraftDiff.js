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
					zone: zi,
					col: ci,
					props: f,
				});
			});
		});
	});
	return out;
}

function layout_sections(layout) {
	return (layout.sections || [])
		.filter((s) => !s.remove)
		.map((s) => ({ ...s, columns: (s.columns || []).map(({ fields, ...col }) => col) }));
}

function show(value) {
	if (value == null || value === "") return __("none");
	if (typeof value === "object") {
		return Array.isArray(value)
			? __("{0} items", [value.length])
			: Object.values(value)
					.map((v) => (v == null || v === "" ? 0 : v))
					.join(" ");
	}
	if (typeof value === "boolean" || value === 0 || value === 1)
		return value ? __("on") : __("off");
	return String(value);
}

const SKIP = new Set(["columns", "fields", "id", "fieldname", "fieldtype", "custom", "remove"]);

function prop_notes(before, after) {
	const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
	const notes = [];
	for (const key of keys) {
		if (SKIP.has(key)) continue;
		const a = JSON.stringify(before[key] ?? null);
		const b = JSON.stringify(after[key] ?? null);
		if (a !== b)
			notes.push(`${frappe.unscrub(key)}: ${show(before[key])} → ${show(after[key])}`);
	}
	return notes;
}

export function describe_draft_changes(saved_format_data, draft_format_data) {
	const fields = [];
	const sections = [];
	const base = parse_layout(saved_format_data);
	const next = parse_layout(draft_format_data);
	if (base && next) {
		const before = layout_fields(base);
		for (const [key, f] of layout_fields(next)) {
			const old = before.get(key);
			if (!old) fields.push({ fieldname: f.fieldname, note: __("Added") });
			else if (old.zone !== f.zone || old.col !== f.col) {
				fields.push({ fieldname: f.fieldname, note: __("Moved") });
			} else {
				const notes = prop_notes(old.props, f.props);
				if (notes.length) fields.push({ fieldname: f.fieldname, note: notes.join(", ") });
			}
		}
		const old_sections = layout_sections(base);
		layout_sections(next).forEach((sec, i) => {
			if (!old_sections[i]) return;
			const notes = prop_notes(old_sections[i], sec);
			if (notes.length) sections.push({ index: i, note: notes.join(", ") });
		});
	}
	return { fields, sections };
}
