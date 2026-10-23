// Focus rings show only while Tab moves focus. frappe-ui rings every :focus-visible element,
// and Chrome counts focus a script moves after any key press as visible too (a dialog opened
// by a typed command, a trigger a menu hands focus back to on Escape). Tab marks the root,
// a pointer press clears it, and flow.css hides rings and focus reveals without the mark.
export function installFocusRings(root = document.documentElement) {
	const onKey = (event) => {
		if (event.key === "Tab") root.dataset.flowTabbing = ""
	}
	const onPointer = () => delete root.dataset.flowTabbing
	window.addEventListener("keydown", onKey, true)
	window.addEventListener("pointerdown", onPointer, true)
	return () => {
		window.removeEventListener("keydown", onKey, true)
		window.removeEventListener("pointerdown", onPointer, true)
		delete root.dataset.flowTabbing
	}
}
