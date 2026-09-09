// Layout-aware drop geometry shared by the on-canvas reorder engine and the
// panel drop zone. All coordinates are in client (screen) space so callers can
// position fixed overlays directly and mix live getBoundingClientRect values
// with cursor clientX/clientY without worrying about canvas scale/translate.
//
// Everything here is pure geometry: it takes rects + a pointer and returns an
// insertion index / an indicator line. Flex row, flex column, wrapped flex and
// CSS grid all fall out of the same 2D reading-order model.

export type LayoutDirection = "row" | "column"
export type IndicatorOrientation = "vertical" | "horizontal"

export interface ChildRect {
	// position in the measured element list, so callers can map an index in
	// reading order back to the element/block it came from
	index: number
	// main-axis extents (left/right for row, top/bottom for column)
	start: number
	end: number
	mid: number
	// cross-axis extents (used to cluster into lines and to size the line)
	crossStart: number
	crossEnd: number
}

export interface IndicatorGeometry {
	orientation: IndicatorOrientation
	// top-left of the line in client coords + its length
	left: number
	top: number
	length: number
}

export function getLayoutDirection(style: CSSStyleDeclaration): LayoutDirection {
	const display = style.display
	if (display === "flex" || display === "inline-flex") {
		return style.flexDirection.includes("row") ? "row" : "column"
	} else if (display === "grid" || display === "inline-grid") {
		return style.gridAutoFlow.includes("column") ? "column" : "row"
	}
	// block-level and inline children stack vertically
	return "column"
}

// Snapshot the given elements along the given axis. Returned in input order,
// which for every layout studio produces matches visual reading order.
export function collectChildRects(elements: HTMLElement[], direction: LayoutDirection): ChildRect[] {
	return elements.map((el, index) => {
		const rect = el.getBoundingClientRect()
		if (direction === "row") {
			return {
				index,
				start: rect.left,
				end: rect.right,
				mid: rect.left + rect.width / 2,
				crossStart: rect.top,
				crossEnd: rect.bottom,
			}
		}
		return {
			index,
			start: rect.top,
			end: rect.bottom,
			mid: rect.top + rect.height / 2,
			crossStart: rect.left,
			crossEnd: rect.right,
		}
	})
}

// Group children into visual lines (grid rows for a row layout, the single
// stacked column for a column/flex layout) in reading order. A one-line result
// means a plain flex row/column; multiple lines means a wrapped flex or a grid.
// Because input order is reading order, a new line simply starts whenever the
// next child no longer overlaps the current line's cross band.
export function clusterLines(rects: ChildRect[]): ChildRect[][] {
	const lines: ChildRect[][] = []
	let current: ChildRect[] = []
	for (const rect of rects) {
		const onCurrent = current.length > 0 && current.some((c) => sameLine(c, rect))
		if (!onCurrent && current.length) {
			lines.push(current)
			current = []
		}
		current.push(rect)
	}
	if (current.length) lines.push(current)
	for (const line of lines) line.sort((a, b) => a.start - b.start)
	return lines
}

// 2D reading-order insertion index: how many children come before the pointer,
// scanning line-by-line down the cross axis and item-by-item along the main
// axis. Reduces to a midpoint scan for a single flex line and handles wrapped
// flex / grid without special-casing. Monotonic within a line, so there's no
// oscillation at the edges.
export function computeReadingOrderIndex(
	lines: ChildRect[][],
	pointerMain: number,
	pointerCross: number,
): number {
	let index = 0
	for (const line of lines) {
		const band = lineBand(line)
		if (pointerCross > band.end) {
			// the whole line sits before the pointer
			index += line.length
			continue
		}
		if (pointerCross < band.start) {
			// this line (and every later one) is after the pointer
			break
		}
		for (const item of line) {
			if (pointerMain > item.mid) index++
			else break
		}
		return index
	}
	return index
}

// Where to draw the insertion line for a resolved index, using the two children
// bracketing the insertion point:
//   - both present and on the same line → centre the line in the gap between them
//   - only a following child (line start, or the very first slot) → a caret at
//     its leading edge, spanning that cell — reads as "insert before this cell"
//   - only a preceding child (very last slot) → a caret at its trailing edge
//   - no children (empty container) → where the first child will land, honouring
//     justify-content (main axis) and align-items (cross axis), sized to the
//     dragged block when known
export function computeDropIndicator(
	lines: ChildRect[][],
	index: number,
	parentRect: DOMRect,
	style: CSSStyleDeclaration,
	direction: LayoutDirection,
	sourceSize?: { width: number; height: number },
): IndicatorGeometry {
	const orientation: IndicatorOrientation = direction === "row" ? "vertical" : "horizontal"
	const flat = lines.flat()

	const build = (mainPos: number, crossStart: number, crossEnd: number): IndicatorGeometry => {
		const length = Math.max(crossEnd - crossStart, 4)
		return orientation === "vertical"
			? { orientation, left: mainPos, top: crossStart, length }
			: { orientation, left: crossStart, top: mainPos, length }
	}

	if (flat.length === 0) {
		const { mainPos, crossStart, crossEnd } = emptyContainerSlot(parentRect, style, direction, sourceSize)
		return build(mainPos, crossStart, crossEnd)
	}

	const prev = index > 0 ? flat[index - 1] : null
	const next = index < flat.length ? flat[index] : null

	if (prev && next && sameLine(prev, next)) {
		const mid = (prev.end + next.start) / 2
		return build(mid, Math.min(prev.crossStart, next.crossStart), Math.max(prev.crossEnd, next.crossEnd))
	}
	if (next) {
		return build(next.start, next.crossStart, next.crossEnd)
	}
	// prev is guaranteed here (flat.length > 0 and next is null)
	const last = prev as ChildRect
	return build(last.end, last.crossStart, last.crossEnd)
}

// Two rects share a visual line when they overlap on the cross axis by more than
// half of the smaller one — robust to ragged item heights in a grid row.
function sameLine(a: ChildRect, b: ChildRect): boolean {
	const overlap = Math.min(a.crossEnd, b.crossEnd) - Math.max(a.crossStart, b.crossStart)
	const minSize = Math.min(a.crossEnd - a.crossStart, b.crossEnd - b.crossStart) || 1
	return overlap > minSize * 0.5
}

function lineBand(line: ChildRect[]): { start: number; end: number } {
	return {
		start: Math.min(...line.map((r) => r.crossStart)),
		end: Math.max(...line.map((r) => r.crossEnd)),
	}
}

// Content-box slot where an empty container's first child would land.
function emptyContainerSlot(
	parentRect: DOMRect,
	style: CSSStyleDeclaration,
	direction: LayoutDirection,
	sourceSize?: { width: number; height: number },
) {
	const padTop = parseFloat(style.paddingTop) || 0
	const padBottom = parseFloat(style.paddingBottom) || 0
	const padLeft = parseFloat(style.paddingLeft) || 0
	const padRight = parseFloat(style.paddingRight) || 0
	const mainLo = direction === "row" ? parentRect.left + padLeft : parentRect.top + padTop
	const mainHi = direction === "row" ? parentRect.right - padRight : parentRect.bottom - padBottom
	const crossLo = direction === "row" ? parentRect.top + padTop : parentRect.left + padLeft
	const crossHi = direction === "row" ? parentRect.bottom - padBottom : parentRect.right - padRight

	const justify = style.justifyContent
	let mainPos = mainLo
	if (justify === "center" || justify === "space-around" || justify === "space-evenly") {
		mainPos = (mainLo + mainHi) / 2
	} else if (justify === "flex-end" || justify === "end" || justify === "right") {
		mainPos = mainHi
	}

	const align = style.alignItems
	const sourceCross = sourceSize ? (direction === "row" ? sourceSize.height : sourceSize.width) : 0
	let crossStart = crossLo
	let crossEnd = crossHi
	if (sourceCross > 0 && align !== "stretch" && align !== "normal" && align !== "") {
		if (align === "center") {
			const centre = (crossLo + crossHi) / 2
			crossStart = centre - sourceCross / 2
			crossEnd = centre + sourceCross / 2
		} else if (align === "flex-end" || align === "end") {
			crossStart = crossHi - sourceCross
			crossEnd = crossHi
		} else {
			crossStart = crossLo
			crossEnd = crossLo + sourceCross
		}
		crossStart = Math.max(crossStart, crossLo)
		crossEnd = Math.min(crossEnd, crossHi)
	}
	return { mainPos, crossStart, crossEnd }
}
