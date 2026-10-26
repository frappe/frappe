// The editor's model: the layout's blocks as stored, and the widgets they point at.

import { SIZES } from "../grid.js";

// names the default layout to the server, where a role would name a role layout
export const DEFAULT_LAYOUT = "<default>";

// block type -> the payload's widget table, and the stored fields of one widget
export const WIDGETS = {
	number_card: { table: "number_cards", fields: ["label", "number_card_name"] },
	chart: { table: "charts", fields: ["label", "chart_name"] },
};

export const name_key = (type) => `${type}_name`;

export function sizes_of(type) {
	return Object.keys(SIZES[type] || {});
}

// A preset is stored as `col`, plus `row` when the preset has a fixed height.
export function set_size(block, preset) {
	const [col, row] = SIZES[block.type][preset];
	block.data.col = col;
	if (row) block.data.row = row;
	else delete block.data.row;
}

export function with_ids(blocks) {
	return blocks.map((block) => ({
		...block,
		id: block.id || Math.random().toString(36).slice(2, 12),
		data: { ...block.data },
	}));
}

export function move(blocks, id, target) {
	const from = blocks.findIndex((block) => block.id === id);
	const [block] = blocks.splice(from, 1);
	const at = blocks.findIndex((b) => b.id === (target.id || target.after));
	blocks.splice(target.after ? at + 1 : at, 0, block);
}

/**
 * What `save_page` takes: the blocks as EditorJS stores them, and the widgets this session
 * changed in the stored shape. A changed widget's block points at its new label.
 */
export function to_save(blocks, widgets, touched) {
	const new_widgets = {};
	const stored = blocks.map(({ id, type, data }) => {
		const spec = WIDGETS[type];
		if (!spec || !touched.has(id)) return { id, type, data };

		const item = widgets[spec.table][data[name_key(type)]];
		(new_widgets[type] ||= []).push(
			Object.fromEntries(spec.fields.map((field) => [field, item[field]]))
		);
		return { id, type, data: { ...data, [name_key(type)]: item.label } };
	});
	return { blocks: JSON.stringify(stored), new_widgets };
}
