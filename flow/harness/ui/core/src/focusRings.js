// Focus rings show only while Tab moves focus. frappe-ui rings every :focus-visible element,
// and Chrome counts focus a script moves after any key press as visible too (a dialog opened
// by a typed command, a trigger a menu hands focus back to on Escape). Tab marks the root,
// a pointer press clears it, and flow.css hides rings and focus reveals without the mark. An
// island marks its shadow host as well, which its overlays, beside the root, sit under.
export function installFocusRings(...roots) {
	if (!roots.length) roots = [document.documentElement]
	const onKey = (event) => {
		if (event.key === "Tab") for (const root of roots) root.dataset.flowTabbing = ""
	}
	const onPointer = () => roots.forEach((root) => delete root.dataset.flowTabbing)
	window.addEventListener("keydown", onKey, true)
	window.addEventListener("pointerdown", onPointer, true)
	return () => {
		window.removeEventListener("keydown", onKey, true)
		window.removeEventListener("pointerdown", onPointer, true)
		onPointer()
	}
}
