import { clone_plain, freshen_field } from "../utils";

export function useLayoutMutations(layout, selection) {
	const { selected_field, selected_fields, selected_section } = selection;

	function find_field_column(df) {
		const lv = layout.value;
		const zones = [lv?.header, lv?.footer, ...(lv?.sections || [])].filter(Boolean);
		for (const section of zones) {
			for (const column of section.columns || []) {
				if (column.fields?.includes(df)) return column;
			}
		}
		return null;
	}
	function duplicate_field(df) {
		if (!df || !layout.value) return;
		const col = find_field_column(df);
		if (!col) return;
		const clone = freshen_field(clone_plain(df));
		col.fields.splice(col.fields.indexOf(df) + 1, 0, clone);
		selected_section.value = null;
		selected_field.value = clone;
	}
	function duplicate_section(section) {
		if (!section || !layout.value) return;
		const sections = layout.value.sections;
		const idx = sections.indexOf(section);
		if (idx === -1) return;
		const clone = clone_plain(section);
		delete clone.remove;
		(clone.columns || []).forEach((c) => (c.fields || []).forEach(freshen_field));
		sections.splice(idx + 1, 0, clone);
		selected_field.value = null;
		selected_section.value = clone;
	}
	function duplicate_selection() {
		if (selected_fields.value.length > 1) {
			const clones = [];
			selected_fields.value.slice().forEach((df) => {
				selected_field.value = null;
				duplicate_field(df);
				if (selected_field.value) clones.push(selected_field.value);
			});
			selected_fields.value = clones;
			selected_field.value = clones[clones.length - 1] || null;
		} else if (selected_field.value) {
			duplicate_field(selected_field.value);
		} else if (selected_section.value) {
			duplicate_section(selected_section.value);
		}
	}
	function move_in_array(arr, item, dir) {
		const i = arr.indexOf(item);
		const j = i + dir;
		if (i === -1 || j < 0 || j >= arr.length) return;
		arr.splice(i, 1);
		arr.splice(j, 0, item);
	}
	function move_fields_in_column(col, fields, dir) {
		const selected = new Set(fields);
		const ordered = fields
			.slice()
			.sort((a, b) => col.fields.indexOf(a) - col.fields.indexOf(b));
		const seq = dir > 0 ? ordered.reverse() : ordered;
		for (const df of seq) {
			const i = col.fields.indexOf(df);
			const j = i + dir;
			if (j < 0 || j >= col.fields.length) continue;
			if (selected.has(col.fields[j])) continue;
			move_in_array(col.fields, df, dir);
		}
	}
	function move_selection(dir) {
		if (selected_fields.value.length > 1) {
			const groups = new Map();
			selected_fields.value.forEach((df) => {
				const col = find_field_column(df);
				if (!col) return;
				if (!groups.has(col)) groups.set(col, []);
				groups.get(col).push(df);
			});
			groups.forEach((fields, col) => move_fields_in_column(col, fields, dir));
		} else if (selected_field.value) {
			const col = find_field_column(selected_field.value);
			if (col) move_in_array(col.fields, selected_field.value, dir);
		} else if (selected_section.value) {
			move_in_array(layout.value?.sections || [], selected_section.value, dir);
		}
	}
	// After a bulk drag drops `dragged` (Sortable moved only that one field),
	// pull the rest of the selected group over so they sit contiguously around
	// it, keeping their original document order. `group` is the whole selection
	// in document order, including `dragged`.
	function reflow_dragged_group(dragged, group) {
		if (!dragged || !group || group.length < 2 || !layout.value) return;
		group
			.filter((f) => f !== dragged)
			.forEach((f) => {
				const col = find_field_column(f);
				if (col) col.fields.splice(col.fields.indexOf(f), 1);
			});
		const col = find_field_column(dragged);
		if (!col) return;
		const di = group.indexOf(dragged);
		const before = group.slice(0, di);
		const after = group.slice(di + 1);
		let at = col.fields.indexOf(dragged);
		before.forEach((f, k) => col.fields.splice(at + k, 0, f));
		at = col.fields.indexOf(dragged) + 1;
		after.forEach((f, k) => col.fields.splice(at + k, 0, f));
	}
	function insert_section(data) {
		if (!data || !layout.value) return;
		const clone = clone_plain(data);
		delete clone.remove;
		(clone.columns || []).forEach((c) => (c.fields || []).forEach(freshen_field));
		const sections = layout.value.sections;
		const idx = selected_section.value ? sections.indexOf(selected_section.value) : -1;
		if (idx !== -1) sections.splice(idx + 1, 0, clone);
		else sections.push(clone);
		selected_field.value = null;
		selected_section.value = clone;
	}
	function insert_field(data) {
		if (!data || !layout.value) return;
		const clone = freshen_field(clone_plain(data));
		const col = selected_field.value && find_field_column(selected_field.value);
		if (col) {
			col.fields.splice(col.fields.indexOf(selected_field.value) + 1, 0, clone);
		} else {
			const sections = layout.value.sections || [];
			const target = selected_section.value || sections[sections.length - 1];
			const first_col = target?.columns?.[0];
			if (!first_col) return;
			first_col.fields.push(clone);
		}
		selected_section.value = null;
		selected_field.value = clone;
	}
	function remove_section(section) {
		const idx = layout.value.sections.indexOf(section);
		if (idx === -1) return;
		layout.value.sections.splice(idx, 1);
		if (selected_section.value === section) {
			selected_section.value = null;
		}
		if (
			selected_field.value &&
			section.columns.some((c) => c.fields.includes(selected_field.value))
		) {
			selected_field.value = null;
		}
	}

	return {
		duplicate_field,
		duplicate_section,
		duplicate_selection,
		move_selection,
		reflow_dragged_group,
		insert_section,
		insert_field,
		remove_section,
	};
}
