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
					json: JSON.stringify(f),
				});
			});
		});
	});
	return out;
}

function layout_sections(layout) {
	return (layout.sections || [])
		.filter((s) => !s.remove)
		.map((s) => ({
			json: JSON.stringify({
				...s,
				columns: (s.columns || []).map(({ fields, ...col }) => col),
			}),
		}));
}

export function describe_draft_changes(saved_format_data, draft_format_data) {
	const added = [];
	const moved = [];
	const changed = [];
	const sections = [];
	const base = parse_layout(saved_format_data);
	const next = parse_layout(draft_format_data);
	if (base && next) {
		const before = layout_fields(base);
		const after = layout_fields(next);
		for (const [key, f] of after) {
			const old = before.get(key);
			if (!old) added.push(f.fieldname);
			else if (old.zone !== f.zone || old.col !== f.col) moved.push(f.fieldname);
			else if (old.json !== f.json) changed.push(f.fieldname);
		}
		const old_sections = layout_sections(base);
		layout_sections(next).forEach((sec, i) => {
			if (old_sections[i] && old_sections[i].json !== sec.json) sections.push(i);
		});
	}
	return { sections, highlight: [...new Set([...added, ...moved, ...changed])] };
}
