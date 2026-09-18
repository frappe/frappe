import { clone_plain } from "../utils";

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

const SKIP = new Set(["columns", "fields", "id", "fieldname", "fieldtype", "custom", "remove"]);
const COLUMN_LISTS = new Set(["table_columns", "repeater_columns"]);

function parse_layout(format_data) {
	if (!format_data) return null;
	const layout =
		typeof format_data === "string" ? frappe.utils.parse_json(format_data) : format_data;
	return layout && typeof layout === "object" && !Array.isArray(layout) ? layout : null;
}

function same(a, b) {
	return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

function column_changes(before, after) {
	const name = (c, i) => c.label || c.fieldname || __("column {0}", [i + 1]);
	const out = [];
	after.forEach((col, i) => {
		const old = before[i];
		if (!old) out.push({ key: "column", column: name(col, i), kind: "added" });
		else if (!same(old, col)) {
			out.push({
				key: "column",
				column: name(col, i),
				kind: "changed",
				changes: prop_changes(old, col),
			});
		}
	});
	before.slice(after.length).forEach((col, i) => {
		out.push({ key: "column", column: name(col, after.length + i), kind: "removed" });
	});
	return out;
}

function prop_changes(before, after) {
	const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
	const out = [];
	for (const key of keys) {
		if (SKIP.has(key) || same(before[key], after[key])) continue;
		if (COLUMN_LISTS.has(key))
			out.push(...column_changes(before[key] || [], after[key] || []));
		else out.push({ key, before: before[key], after: after[key] });
	}
	return out;
}

function zones_of(layout) {
	const out = [];
	if (layout.header) out.push({ id: "header", section: layout.header });
	(layout.sections || []).forEach((s, i) => !s.remove && out.push({ id: `s${i}`, section: s }));
	if (layout.footer) out.push({ id: "footer", section: layout.footer });
	return out;
}

function fields_of(layout) {
	const out = new Map();
	zones_of(layout).forEach(({ id, section }) => {
		(section.columns || []).forEach((col, ci) => {
			const seen = {};
			(col.fields || []).forEach((f, pos) => {
				if (f.remove || !f.fieldname) return;
				seen[f.fieldname] = (seen[f.fieldname] || 0) + 1;
				out.set(`${id}/${ci}/${f.fieldname}#${seen[f.fieldname]}`, {
					fieldname: f.fieldname,
					zone: id,
					col: ci,
					pos,
					props: f,
				});
			});
		});
	});
	return out;
}

function section_shell(section) {
	return { ...section, columns: (section.columns || []).map(({ fields, ...col }) => col) };
}

export function describe_draft_changes(saved, draft) {
	const settings = DRAFT_SETTING_FIELDS.filter((f) => !same(saved[f], draft[f])).map((f) => ({
		key: f,
		before: saved[f],
		after: draft[f],
	}));

	const base = parse_layout(saved.format_data) || { sections: [] };
	const merged = clone_plain(parse_layout(draft.format_data) || { sections: [] });
	const before = fields_of(base);
	const after = fields_of(merged);
	const status = new Map();

	const unmatched_before = [];
	const unmatched_after = [];
	for (const [key, f] of after) {
		const old = before.get(key);
		if (!old) unmatched_after.push(f);
		else {
			const changes = prop_changes(old.props, f.props);
			if (changes.length) status.set(f.props, { kind: "changed", changes });
		}
	}
	for (const [key, old] of before) if (!after.has(key)) unmatched_before.push(old);
	for (const f of unmatched_after) {
		const i = unmatched_before.findIndex((old) => old.fieldname === f.fieldname);
		if (i >= 0) {
			const [old] = unmatched_before.splice(i, 1);
			status.set(f.props, { kind: "moved", changes: prop_changes(old.props, f.props) });
		} else status.set(f.props, { kind: "added", changes: [] });
	}

	const sections = [];
	const base_sections = (base.sections || []).filter((s) => !s.remove);
	const live_sections = merged.sections.filter((s) => !s.remove);
	live_sections.forEach((sec, i) => {
		const old = base_sections[i];
		if (!old) sections.push({ section: sec, kind: "added", changes: [] });
		else {
			const changes = prop_changes(section_shell(old), section_shell(sec));
			if (changes.length) sections.push({ section: sec, kind: "changed", changes });
		}
	});
	base_sections.slice(live_sections.length).forEach((old) => {
		const copy = clone_plain(old);
		merged.sections.push(copy);
		sections.push({ section: copy, kind: "removed", changes: [] });
		(copy.columns || []).forEach((col) =>
			(col.fields || []).forEach((f) => status.set(f, { kind: "removed", changes: [] }))
		);
	});

	const merged_zones = Object.fromEntries(zones_of(merged).map((z) => [z.id, z.section]));
	for (const old of unmatched_before) {
		const zone = merged_zones[old.zone];
		if (!zone) continue;
		const col = (zone.columns || [])[old.col] || (zone.columns || [])[zone.columns.length - 1];
		if (!col) continue;
		const copy = clone_plain(old.props);
		col.fields.splice(Math.min(old.pos, col.fields.length), 0, copy);
		status.set(copy, { kind: "removed", changes: [] });
	}

	const fields = [];
	const seen = {};
	zones_of(merged).forEach(({ section }) => {
		(section.columns || []).forEach((col) => {
			(col.fields || []).forEach((f) => {
				if (f.remove || !f.fieldname) return;
				seen[f.fieldname] = (seen[f.fieldname] || 0) + 1;
				const entry = status.get(f);
				if (entry) fields.push({ field: f, occurrence: seen[f.fieldname] - 1, ...entry });
			});
		});
	});

	return {
		settings,
		fields,
		sections: sections.map((s) => ({
			index: merged.sections.indexOf(s.section),
			section: s.section,
			kind: s.kind,
			changes: s.changes,
		})),
		merged,
	};
}
