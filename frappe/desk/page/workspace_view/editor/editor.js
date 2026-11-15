// The editor's model: the layout's blocks as stored, and the widgets they point at.

import { SIZES, block_size } from "../grid.js";

// Old block type -> the payload's widget table and the stored fields of one widget. Onboarding is
// a block alone, with no widget row.
export const WIDGETS = {
	number_card: { table: "number_cards", fields: ["label", "number_card_name"] },
	chart: { table: "charts", fields: ["label", "chart_name"] },
	shortcut: {
		table: "shortcuts",
		fields: [
			"label",
			"type",
			"link_to",
			"url",
			"doc_view",
			"kanban_board",
			"icon",
			"restrict_to_domain",
			"color",
			"format",
			"stats_filter",
		],
	},
	card: { table: "cards", fields: ["label", "icon", "description", "links"] },
	quick_list: {
		table: "quick_lists",
		fields: [
			"label",
			"document_type",
			"quick_list_filter",
			"order_by",
			"hide_filter",
			"hide_refresh",
			"hide_new",
			"hide_view_list",
		],
	},
	custom_block: { table: "custom_blocks", fields: ["label", "custom_block_name"] },
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

// Widget types a page makes itself, which are never added by hand
const GENERATED_TYPES = ["Module Customizations"];

// frappe's own types first, in the order people reach for them
const FIRST_TYPES = [
	"Number Card",
	"Chart",
	"Shortcut",
	"Card",
	"Quick List",
	"Onboarding",
	"Custom Block",
];

// The Widget Types a block can be: those with sizes, so not a container's items.
export function addable_types(widget_types) {
	const rank = (name) =>
		FIRST_TYPES.includes(name) ? FIRST_TYPES.indexOf(name) : FIRST_TYPES.length;
	return Object.keys(widget_types)
		.filter(
			(name) =>
				Object.keys(widget_types[name].sizes).length && !GENERATED_TYPES.includes(name)
		)
		.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

// Text is one item with sizes: three heading sizes and Body, which is a paragraph.
export const TEXT_SIZES = { Large: 3, Medium: 4, Small: 5, Body: null };

export const name_key = (type) => `${type}_name`;

// `presets` are a Widget Type's sizes, for a widget block
export function sizes_of(type, presets = SIZES[type]) {
	return Object.keys(presets || {});
}

// A preset is stored as `col`, plus `row` when the preset has a fixed height. A Tall block
// stays Tall at its new width.
export function set_size(block, preset, presets = SIZES[block.type]) {
	const tall = height_of(block) === "Tall";
	const [col, row] = presets[preset];
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

// A new Widget block of `type`, a draft until the page is saved, with its props' defaults.
export function new_widget(type, widget_type, label) {
	const block = { id: new_id(), type: "widget", data: {} };
	const sizes = Object.keys(widget_type.sizes);
	set_size(block, sizes.includes("M") ? "M" : sizes[0], widget_type.sizes);
	const config = Object.fromEntries(
		widget_type.fields
			.filter((field) => field.default != null)
			.map((field) => [field.fieldname, default_of(field)])
	);
	const items = widget_type.child_type ? [] : undefined;
	return {
		block,
		widget: { name: null, type, label, config, items, data: null, renamed: true },
	};
}

const default_of = (field) =>
	field.fieldtype === "Check" ? Number(field.default) : field.default;

// A container's items as its config holds them: a saved item by name, a new one as a draft.
export function config_of(widget, widget_type) {
	if (!widget_type.child_type || !widget.items) return widget.config;
	const widgets = widget.items
		.filter((item) => item.link_to)
		.map((item) =>
			item.widget
				? { widget: item.widget }
				: {
						draft: {
							type: widget_type.child_type,
							label: item.label || item.link_to,
							config: { link_type: item.link_type, link_to: item.link_to },
						},
				  }
		);
	return { ...widget.config, widgets };
}

export function new_text() {
	return { id: new_id(), type: "header", data: { text: heading_html(4, ""), col: 12 } };
}

export function new_section_break() {
	return { id: new_id(), type: "spacer", data: { col: 12 } };
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
 * What `save_page` takes: the blocks, the old widgets this session touched in their stored shape,
 * and the Widgets it edited. A touched old widget's block points at its new label, a new Widget
 * block carries its draft. A Body text with nothing in it is left out.
 */
export function to_save(blocks, widgets, touched, widget_types) {
	const new_widgets = {};
	const widget_edits = {};
	const stored = [];
	for (const { id, type, data, generated, hidden_by } of blocks) {
		// made by the page, or hidden by a weaker layout: neither is this layout's to save
		if (generated || hidden_by) continue;
		if (type === "paragraph" && !text_of({ data }).trim()) continue;

		const widget = type === "widget" && widgets.widget?.[id];
		if (widget) {
			const config = config_of(widget, widget_types[widget.type]);
			if (!widget.name) {
				const draft = { type: widget.type, label: widget.label, config };
				stored.push({ id, type, data: { ...data, draft } });
				continue;
			}
			if (touched.has(id)) {
				widget_edits[widget.name] = {
					config,
					...(widget.renamed && { label: widget.label }),
				};
			}
			stored.push({ id, type, data });
			continue;
		}

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
	return { blocks: JSON.stringify(stored), new_widgets, widget_edits };
}
