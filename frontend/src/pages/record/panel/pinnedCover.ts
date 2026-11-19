export const LINE_UNDER =
	"after:pointer-events-none after:absolute after:inset-x-0 after:top-full after:h-px after:border-b after:border-outline-gray-1 after:content-['']";

// Whatever follows the bar scrolls under it, a collapsed section's next one too. A sub-pixel
// overlap at rest would draw the line under a bar nothing has passed beneath.
export function rowsUnder(bar: HTMLElement) {
	const rows = bar.nextElementSibling;
	if (!rows) return false;
	return bar.getBoundingClientRect().bottom - rows.getBoundingClientRect().top >= 1;
}
