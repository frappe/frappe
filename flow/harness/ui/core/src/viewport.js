// A phone's keyboard shrinks only the visible part of the page, and the browser slides the whole
// page up to keep the caret in sight, header and all. Held to the visible part, the page keeps
// its header in place and the composer rides the keyboard. Times the scale, so a pinch zoom,
// which shrinks the visible part too, leaves the page as it is, and where it was panned to.
export function installViewport(root = document.documentElement) {
	const viewport = globalThis.visualViewport
	if (!viewport) return () => {}
	const fit = () => {
		root.style.height = `${viewport.height * viewport.scale}px`
		if (viewport.scale === 1) window.scrollTo(0, 0)
	}
	viewport.addEventListener("resize", fit)
	return () => {
		viewport.removeEventListener("resize", fit)
		root.style.removeProperty("height")
	}
}
