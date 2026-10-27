// The index grid's geometry: 112px tiles with 56px logos, 16px apart, at most six to a row.

const MOST_COLUMNS = 6;
const FEWEST_BOX_COLUMNS = 3;
// The arrange strip's hint, Reset and Done fit on one line from four columns.
const FEWEST_ARRANGE_COLUMNS = 4;

// Literal classes, so Tailwind finds them. One per column count.
const GRID_COLUMNS = [
	"grid-cols-[repeat(1,112px)]",
	"grid-cols-[repeat(2,112px)]",
	"grid-cols-[repeat(3,112px)]",
	"grid-cols-[repeat(4,112px)]",
	"grid-cols-[repeat(5,112px)]",
	"grid-cols-[repeat(6,112px)]",
];

// From the first logo's left edge to the last logo's right edge: n tiles and n-1 gaps, less 56px.
const BOX_WIDTHS: Record<number, string> = {
	3: "max-w-[312px]",
	4: "max-w-[440px]",
	5: "max-w-[568px]",
	6: "max-w-[696px]",
};

/** How many columns a grid of this many tiles draws: one per tile, up to six. */
export function columnsFor(tiles: number): number {
	return Math.min(Math.max(tiles, 1), MOST_COLUMNS);
}

export function gridClass(tiles: number): string {
	return GRID_COLUMNS[columnsFor(tiles) - 1];
}

/** The filter box spans the first row's logos, never fewer than three columns. */
export function boxWidthClass(tiles: number): string {
	return BOX_WIDTHS[Math.max(columnsFor(tiles), FEWEST_BOX_COLUMNS)];
}

/** While arranging, the box and the strip span the drag grid of every app, never fewer than four columns. */
export function arrangeBoxWidthClass(tiles: number): string {
	return BOX_WIDTHS[Math.max(columnsFor(tiles), FEWEST_ARRANGE_COLUMNS)];
}

/** The page's centred column: the box sits at 18vh from the top. */
export const PAGE_COLUMN = "mx-auto flex max-w-4xl flex-col items-center px-6 pb-24 pt-[18vh]";
