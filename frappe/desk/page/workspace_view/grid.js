// How workspace blocks sit on the bento grid.
//
// A block keeps today's EditorJS shape. `col` is the width it was saved with, and `row` is an
// optional height in grid rows that legacy ignores. Both snap to the named sizes of the block's
// type when read, and nothing is written back until an editor saves.

// frappe-ui's NumberCard with a change and a sparkline is 140px tall: 39 tracks, at 18 a row
const NUMBER_CARD_ROWS = 39 / 18;

// [width in 12 columns, height in rows]. A null height fits the content, and a quick list's
// height is the most it grows to.
export const SIZES = {
	shortcut: { S: [3, null], M: [4, null], L: [6, null] },
	number_card: { S: [2, NUMBER_CARD_ROWS], M: [3, NUMBER_CARD_ROWS], L: [6, NUMBER_CARD_ROWS] },
	card: { M: [4, null] },
	quick_list: { M: [4, 4], L: [6, 4], XL: [8, 4] },
	chart: { L: [6, 4], XL: [8, 4], Wide: [12, 4] },
	onboarding: { L: [6, null], Wide: [12, null] },
	custom_block: { M: [4, null], L: [6, null], XL: [8, null], Wide: [12, null] },
	header: { Full: [12, null] },
	paragraph: { M: [4, null], L: [6, null], Full: [12, null] },
};

const SMALL = new Set(["S", "M"]);
const SHRINKS = new Set(["quick_list"]);

export function block_size(block) {
	const presets = Object.entries(SIZES[block.type] || { Full: [12, null] });
	const col = Number(block.data?.col) || 12;

	// nearest width, and the smaller one on a tie
	let [name, [width, height]] = presets[0];
	for (const [preset, size] of presets) {
		if (Math.abs(size[0] - col) < Math.abs(width - col))
			[name, [width, height]] = [preset, size];
	}

	return {
		name,
		span: { 12: width, 6: SMALL.has(name) ? 3 : 6, 2: SMALL.has(name) ? 1 : 2 },
		rows: Number(block.data?.row) || height,
		shrinks: SHRINKS.has(block.type),
	};
}

// A spacer, a heading or a full-width paragraph ends a section. A heading or a full-width
// paragraph draws above the section that follows it, and each section packs on its own.
export function split_sections(blocks) {
	const sections = [];
	let current = null;
	for (const block of blocks) {
		if (block.type === "spacer" || is_full_width_text(block)) {
			current = { heading: block.type === "spacer" ? null : block, blocks: [] };
			sections.push(current);
		} else {
			if (!current) sections.push((current = { heading: null, blocks: [] }));
			current.blocks.push(block);
		}
	}
	return sections.filter((section) => section.heading || section.blocks.length);
}

function is_full_width_text(block) {
	if (block.type === "header") return true;
	return block.type === "paragraph" && block_size(block).name === "Full";
}

// Where each block is on screen, by id, to glide from after the page redraws.
export function block_rects(root) {
	const found = new Map();
	for (const el of root?.querySelectorAll("[data-block]") || []) {
		found.set(el.dataset.block, el.getBoundingClientRect());
	}
	return found;
}

// Every block glides from where it was to where it is now, and a block that was not on the page
// fades in. A resized block's content reflows at once, so with `fade_resized` it fades in over
// the change. The block in `held` is under the pointer and is left where it is.
export function glide(root, before, { duration, easing, fade_resized = false, held = null }) {
	if (!root || !before.size || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
	for (const el of root.querySelectorAll("[data-block]")) {
		if (el.dataset.block === held) continue;
		const from = before.get(el.dataset.block);
		if (!from) {
			el.animate([{ opacity: 0 }, { opacity: 1 }], { duration, easing });
			continue;
		}
		const to = el.getBoundingClientRect();
		const dx = from.left - to.left;
		const dy = from.top - to.top;
		const resized =
			fade_resized &&
			(Math.abs(from.width - to.width) > 1 || Math.abs(from.height - to.height) > 1);
		if (!dx && !dy && !resized) continue;
		el.animate(
			[
				{ transform: `translate(${dx}px, ${dy}px)`, opacity: resized ? 0 : 1 },
				{ transform: "none", opacity: 1 },
			],
			{ duration, easing }
		);
	}
}
