import { h } from "vue"

// A frappe-ui menu row that is the current pick: marked, with a tick at its end, as the lists
// that pick a model, a level or a mode show it.
export function checked(option, isCurrent) {
	if (!isCurrent) return option
	return {
		...option,
		selected: true,
		slots: { suffix: () => h("span", { class: "lucide-check ml-auto size-4 flex-none text-ink-gray-7", "aria-hidden": "true" }) },
	}
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
