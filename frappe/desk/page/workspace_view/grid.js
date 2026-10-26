// How workspace blocks sit on the bento grid.
//
// A block keeps today's EditorJS shape. `col` is the width it was saved with, and `row` is an
// optional height in grid rows that legacy ignores. Both snap to the named sizes of the block's
// type when read, and nothing is written back until an editor saves.

// [width in 12 columns, height in rows]. A null height fits the content.
export const SIZES = {
	shortcut: { S: [3, 2], M: [4, 2], L: [6, 2] },
	number_card: { S: [3, 2], M: [4, 2], L: [6, 2] },
	card: { M: [4, null], L: [6, null] },
	quick_list: { M: [4, 4], L: [6, 4] },
	chart: { L: [6, 4], Wide: [12, 4] },
	onboarding: { L: [6, null], Wide: [12, null] },
	custom_block: { M: [4, null], L: [6, null], Wide: [12, null] },
	header: { Full: [12, null] },
	paragraph: { M: [4, null], L: [6, null], Full: [12, null] },
};

const SMALL = new Set(["S", "M"]);

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
	};
}

// A spacer ends a section, and each section packs on its own.
export function split_sections(blocks) {
	const sections = [[]];
	for (const block of blocks) {
		if (block.type === "spacer") sections.push([]);
		else sections.at(-1).push(block);
	}
	return sections.filter((section) => section.length);
}
