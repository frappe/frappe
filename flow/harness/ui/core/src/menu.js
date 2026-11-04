// a menu hands the focus back to its trigger on a timer as it unmounts: an item that opens a
// dialog or a field runs after that, so what it opens keeps the focus
export function afterMenu(run) {
	return (...args) => setTimeout(() => setTimeout(() => run(...args)))
}

// frappe-ui's Dropdown opens on the press and swallows the click that ends it, matching that click
// to its trigger by `event.target`. Flow runs in a shadow root, where a window listener sees the
// click retargeted to the host, so the click goes through and shuts the menu it just opened. This
// does the same swallow by the click's composed path, which still holds the trigger. Registered
// once, ahead of the Dropdown's own per-press listener, so it runs first.
let opening = null // a closed menu button pressed with the mouse, until its press ends
if (typeof window !== "undefined") {
	window.addEventListener(
		"pointerdown",
		(event) => {
			opening = null
			if (event.pointerType === "touch" || event.button !== 0 || event.ctrlKey) return
			const trigger = event
				.composedPath()
				.find((node) => node instanceof Element && node.getAttribute("aria-haspopup") === "menu")
			if (trigger && trigger.getAttribute("data-state") !== "open") opening = trigger
		},
		true,
	)
	window.addEventListener(
		"click",
		(event) => {
			const trigger = opening
			opening = null
			if (!trigger || event.detail === 0) return
			if (trigger.getAttribute("data-state") === "open" && event.composedPath().includes(trigger))
				event.stopPropagation()
		},
		true,
	)
}
