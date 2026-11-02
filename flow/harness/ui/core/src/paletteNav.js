// One wrapping index policy for compact popovers, full palettes, and slash
// commands. Home/End remain available for normal cursor movement in searches.
export function nextNavigationIndex(current, count, key) {
	if (!count) return null
	if (key === "ArrowDown") return current < 0 ? 0 : (current + 1) % count
	if (key === "ArrowUp") return current < 0 ? count - 1 : (current - 1 + count) % count
	return null
}
