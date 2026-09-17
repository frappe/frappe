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

function setting_label(fieldname) {
	return frappe.meta.get_docfield("Print Format", fieldname)?.label || frappe.unscrub(fieldname);
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
	if (typeof value === "boolean") return value ? __("on") : __("off");
	return String(value);
}

function column_notes(before, after) {
	const name = (c, i) => c.label || c.fieldname || __("column {0}", [i + 1]);
	const notes = [];
	after.forEach((col, i) => {
		const old = before[i];
		if (!old) notes.push(__("column {0} added", [name(col, i)]));
		else if (JSON.stringify(old) !== JSON.stringify(col)) {
			notes.push(`${name(col, i)}: ${prop_notes(old, col).join(", ") || __("changed")}`);
		}
	});
	before
		.slice(after.length)
		.forEach((col, i) => notes.push(__("column {0} removed", [name(col, after.length + i)])));
	return notes;
}

function prop_notes(before, after) {
	const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
	const notes = [];
	for (const key of keys) {
		if (SKIP.has(key)) continue;
		const a = JSON.stringify(before[key] ?? null);
		const b = JSON.stringify(after[key] ?? null);
		if (a === b) continue;
		if (COLUMN_LISTS.has(key))
			notes.push(...column_notes(before[key] || [], after[key] || []));
		else notes.push(`${frappe.unscrub(key)}: ${show(before[key])} → ${show(after[key])}`);
	}
	return notes;
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

function field_label(f) {
	return f.label || f.fieldname || f.fieldtype;
}

export function describe_draft_changes(saved, draft) {
	const settings = DRAFT_SETTING_FIELDS.filter(
		(f) => String(saved[f] ?? "") !== String(draft[f] ?? "")
	).map((f) => ({
		label: setting_label(f),
		note: `${show(saved[f])} → ${show(draft[f])}`,
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
			const notes = prop_notes(old.props, f.props);
			if (notes.length) status.set(f.props, { kind: "changed", notes });
		}
	}
	for (const [key, old] of before) if (!after.has(key)) unmatched_before.push(old);
	for (const f of unmatched_after) {
		const i = unmatched_before.findIndex((old) => old.fieldname === f.fieldname);
		if (i >= 0) {
			unmatched_before.splice(i, 1);
			status.set(f.props, { kind: "moved", notes: [] });
		} else status.set(f.props, { kind: "added", notes: [] });
	}

	const sections = [];
	const base_sections = (base.sections || []).filter((s) => !s.remove);
	const live_sections = merged.sections.filter((s) => !s.remove);
	live_sections.forEach((sec, i) => {
		const old = base_sections[i];
		if (!old) sections.push({ section: sec, kind: "added", notes: [] });
		else {
			const notes = prop_notes(section_shell(old), section_shell(sec));
			if (notes.length) sections.push({ section: sec, kind: "changed", notes });
		}
	});
	base_sections.slice(live_sections.length).forEach((old) => {
		const copy = clone_plain(old);
		merged.sections.push(copy);
		sections.push({ section: copy, kind: "removed", notes: [] });
		(copy.columns || []).forEach((col) =>
			(col.fields || []).forEach((f) => status.set(f, { kind: "removed", notes: [] }))
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
		status.set(copy, { kind: "removed", notes: [] });
	}

	const fields = [];
	const seen = {};
	zones_of(merged).forEach(({ section }) => {
		(section.columns || []).forEach((col) => {
			(col.fields || []).forEach((f) => {
				if (f.remove || !f.fieldname) return;
				seen[f.fieldname] = (seen[f.fieldname] || 0) + 1;
				const entry = status.get(f);
				if (!entry) return;
				fields.push({
					fieldname: f.fieldname,
					occurrence: seen[f.fieldname] - 1,
					label: field_label(f),
					...entry,
				});
			});
		});
	});

	const section_entries = sections.map((s) => ({
		index: merged.sections.indexOf(s.section),
		label: s.section.label || __("Section {0}", [merged.sections.indexOf(s.section) + 1]),
		kind: s.kind,
		notes: s.notes,
	}));

	return { settings, fields, sections: section_entries, merged };
}
