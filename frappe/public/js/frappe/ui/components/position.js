// The shared "where does this floating panel go" engine.
//
// Menus (via menu.js), popovers, tooltips and hover cards all face the same
// problem: put a floating panel next to an anchor, flip it when it would run
// off screen, and never let it hang past the viewport edge. This module is
// that one answer, so every floating component lands the same way.
//
// The panel must be position: fixed and appended to <body> — that way no
// overflow: hidden ancestor can clip it, and viewport coordinates are the
// only coordinates that matter.

export const SIDES = ["top", "right", "bottom", "left"];
export const ALIGNS = ["start", "center", "end"];

// breathing room kept between a panel and the edge of the viewport
const VIEWPORT_PAD = 8;

/**
 * Decide where a panel goes, relative to the anchor rect (a trigger button,
 * a submenu row, or the right-click position). The panel must already be in
 * the DOM — we need its real size to make these calls.
 *
 * Writes top/left (and maxHeight when the panel is taller than the screen)
 * onto the panel's inline style, and stamps data-side / data-align with the
 * side it actually ended up on, so CSS can point the transform-origin (and
 * later, an arrow) at the anchor.
 *
 * @param {HTMLElement} panel The floating element (already in the DOM).
 * @param {DOMRect} anchor What to position against.
 * @param {"top"|"right"|"bottom"|"left"} side Which side of the anchor to hang off.
 * @param {"start"|"center"|"end"} align How to line up along that side.
 * @param {number} offset Gap between anchor and panel, in px.
 */
export function place(panel, anchor, side, align, offset) {
	// "start" and "end" follow the reading direction (same as radix): for
	// panels above or below the anchor, start means the RIGHT edge in RTL.
	// The math below stays physical — we just translate up front. Sides
	// stay physical on purpose (callers that care, like submenus, pick
	// their side per direction themselves).
	if ((side === "top" || side === "bottom") && frappe.utils.is_rtl()) {
		if (align === "start") align = "end";
		else if (align === "end") align = "start";
	}

	let rect = panel.getBoundingClientRect();

	// taller than the viewport: cap it and let the panel scroll
	const max_height = window.innerHeight - 2 * VIEWPORT_PAD;
	if (rect.height > max_height) {
		panel.style.maxHeight = `${max_height}px`;
		rect = panel.getBoundingClientRect();
	}

	// how much free space there is on each side of the anchor
	const room = {
		top: anchor.top - VIEWPORT_PAD,
		bottom: window.innerHeight - anchor.bottom - VIEWPORT_PAD,
		left: anchor.left - VIEWPORT_PAD,
		right: window.innerWidth - anchor.right - VIEWPORT_PAD,
	};

	// if the panel doesn't fit on the asked-for side, and the opposite side
	// is roomier, open there instead (a menu near the bottom of the screen
	// opens upward)
	const opposite = { top: "bottom", bottom: "top", left: "right", right: "left" };
	const needed = side === "top" || side === "bottom" ? rect.height : rect.width;
	if (room[side] < needed + offset && room[opposite[side]] > room[side]) {
		side = opposite[side];
	}

	// side picks which edge of the anchor the panel hangs off; align slides
	// it along that edge (start = the two left/top edges line up, end = the
	// right/bottom edges, center = midpoints)
	let top, left;
	if (side === "top" || side === "bottom") {
		top = side === "bottom" ? anchor.bottom + offset : anchor.top - offset - rect.height;
		if (align === "start") left = anchor.left;
		else if (align === "end") left = anchor.right - rect.width;
		else left = anchor.left + anchor.width / 2 - rect.width / 2;
	} else {
		left = side === "right" ? anchor.right + offset : anchor.left - offset - rect.width;
		if (align === "start") top = anchor.top;
		else if (align === "end") top = anchor.bottom - rect.height;
		else top = anchor.top + anchor.height / 2 - rect.height / 2;
	}

	// whatever side/align said, never hang past the edge of the screen
	left = Math.min(Math.max(left, VIEWPORT_PAD), window.innerWidth - rect.width - VIEWPORT_PAD);
	top = Math.min(Math.max(top, VIEWPORT_PAD), window.innerHeight - rect.height - VIEWPORT_PAD);

	panel.style.top = `${Math.round(top)}px`;
	panel.style.left = `${Math.round(left)}px`;
	panel.setAttribute("data-side", side);
	panel.setAttribute("data-align", align);
}
