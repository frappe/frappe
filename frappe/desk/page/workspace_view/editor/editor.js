// The editor's model: the layout's blocks as stored, and the widgets they point at.

import { SIZES, block_size } from "../grid.js";

// names the default layout to the server, where a role would name a role layout
export const DEFAULT_LAYOUT = "<default>";

// Block type -> the payload's widget table, the stored fields of one widget, and the size and
// values a new one starts with. Onboarding is a block alone, with no widget row.
export const WIDGETS = {
	number_card: { table: "number_cards", fields: ["label", "number_card_name"], size: "M" },
	chart: { table: "charts", fields: ["label", "chart_name"], size: "L" },
	shortcut: {
		table: "shortcuts",
		fields: ["label", "type", "link_to", "url", "doc_view", "color", "format", "stats_filter"],
		size: "M",
		defaults: { type: "DocType" },
	},
	card: {
		table: "cards",
		fields: ["label", "description", "links"],
		size: "M",
		defaults: { links: [] },
	},
	quick_list: {
		table: "quick_lists",
		fields: ["label", "document_type", "quick_list_filter", "order_by"],
		size: "M",
	},
	custom_block: { table: "custom_blocks", fields: ["label", "custom_block_name"], size: "M" },
};

// what `build_links_table_from_card` reads from a stored card's links
const CARD_LINK_KEYS = [
	"label",
	"link_type",
	"link_to",
	"onboard",
	"only_for",
	"dependencies",
	"is_query_report",
];

export const BLOCK_TYPES = [
	"number_card",
	"chart",
	"shortcut",
	"card",
	"quick_list",
	"onboarding",
	"custom_block",
];

// Text is one item with sizes: three heading sizes and Body, which is a paragraph.
export const TEXT_SIZES = { Large: 3, Medium: 4, Small: 5, Body: null };

export const name_key = (type) => `${type}_name`;

export function sizes_of(type) {
	return Object.keys(SIZES[type] || {});
}

// A preset is stored as `col`, plus `row` when the preset has a fixed height. A Tall block
// stays Tall at its new width.
export function set_size(block, preset) {
	const tall = height_of(block) === "Tall";
	const [col, row] = SIZES[block.type][preset];
	block.data.col = col;
	if (row) block.data.row = tall ? row * TALL : row;
	else delete block.data.row;
}

// A list or chart can be Tall, half again its preset's height, to show more of itself.
const TALL = 1.5;
export const HEIGHTS = ["Short", "Tall"];

export function has_heights(block) {
	return (preset_rows(block) || 0) >= 4;
}

export function height_of(block) {
	const rows = preset_rows(block);
	return rows && Number(block.data.row) > rows ? "Tall" : "Short";
}

export function set_height(block, height) {
	const rows = preset_rows(block);
	if (rows) block.data.row = height === "Tall" ? rows * TALL : rows;
}

function preset_rows(block) {
	const preset = SIZES[block.type]?.[block_size(block).name];
	return preset?.[1];
}

const new_id = () => Math.random().toString(36).slice(2, 12);

export function with_ids(blocks) {
	return blocks.map((block) => ({
		...block,
		id: block.id || new_id(),
		data: { ...block.data },
	}));
}

export function move(blocks, id, target) {
	const from = blocks.findIndex((block) => block.id === id);
	const [block] = blocks.splice(from, 1);
	const at = blocks.findIndex((b) => b.id === (target.id || target.after));
	blocks.splice(target.after ? at + 1 : at, 0, block);
}

// A new block of `type` with its widget, labelled so no other widget of its type shares the label.
export function new_block(type, widgets, title) {
	const block = { id: new_id(), type, data: {} };
	if (type === "onboarding") {
		block.data.onboarding_name = "";
		set_size(block, "Wide");
		return { block };
	}

	const spec = WIDGETS[type];
	let label = title;
	for (let n = 2; widgets[spec.table][label]; n++) label = `${title} ${n}`;
	block.data[name_key(type)] = label;
	set_size(block, spec.size);
	const widget = { label, renamed: true, ...JSON.parse(JSON.stringify(spec.defaults || {})) };
	return { block, widget };
}

export function new_text() {
	return { id: new_id(), type: "header", data: { text: heading_html(4, ""), col: 12 } };
}

export function text_size(block) {
	if (block.type === "paragraph") return "Body";
	const level = Number(/class="h(\d)"/.exec(block.data.text || "")?.[1] || 4);
	return level <= 3 ? "Large" : level >= 5 ? "Small" : "Medium";
}

export function text_of(block) {
	return new DOMParser().parseFromString(block.data.text || "", "text/html").body.textContent;
}

// Writes text and size together, since a size names the stored type: a heading or a paragraph.
export function set_text(block, text, size) {
	const level = TEXT_SIZES[size];
	if (level) {
		block.type = "header";
		block.data = { ...block.data, text: heading_html(level, text), col: 12 };
		delete block.data.row;
	} else {
		block.type = "paragraph";
		block.data = { ...block.data, text: escape_html(text) };
	}
}

function heading_html(level, text) {
	return `<span class="h${level}"><b>${escape_html(text)}</b></span>`;
}

function escape_html(text) {
	const div = document.createElement("div");
	div.textContent = text;
	return div.innerHTML;
}

/**
 * What `save_page` takes: the blocks as EditorJS stores them, and the widgets this session
 * touched in the stored shape. A touched widget's block points at its new label. A Body text
 * with nothing in it is left out.
 */
export function to_save(blocks, widgets, touched) {
	const new_widgets = {};
	const stored = [];
	for (const { id, type, data } of blocks) {
		if (type === "paragraph" && !text_of({ data }).trim()) continue;

		const spec = WIDGETS[type];
		if (!spec || !touched.has(id)) {
			stored.push({ id, type, data });
			continue;
		}

		const item = widgets[spec.table][data[name_key(type)]];
		const row = Object.fromEntries(spec.fields.map((field) => [field, item[field] ?? null]));
		if (type === "card") {
			row.links = JSON.stringify(
				(item.links || []).map((link) =>
					Object.fromEntries(CARD_LINK_KEYS.map((key) => [key, link[key] ?? null]))
				)
			);
		}
		(new_widgets[type] ||= []).push(row);
		// a label shown translated is stored as the block named it, unless the editor renamed it
		row.label = item.renamed ? item.label : data[name_key(type)];
		stored.push({ id, type, data: { ...data, [name_key(type)]: row.label } });
	}
	return { blocks: JSON.stringify(stored), new_widgets };
}
