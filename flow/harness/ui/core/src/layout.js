import { reactive } from "vue"

// Under Tailwind's md the frame is narrow: a phone, or a Desk panel's iframe. It shows one pane at
// a time, so the sidebar slides over the chat and settings open as pages. A narrow frame worked by
// a finger is a phone, which drops hover-only buttons and takes swipes and bigger rows.
const wide = globalThis.matchMedia?.("(min-width: 768px)")
const finger = globalThis.matchMedia?.("(pointer: coarse)")

export const layout = reactive({ narrow: false, phone: false })

function measure() {
	layout.narrow = !!wide && !wide.matches
	layout.phone = layout.narrow && !!finger?.matches
}
measure()
wide?.addEventListener("change", measure)
finger?.addEventListener("change", measure)

// the chat's text size in px (Settings › Appearance); the thread's step rows sit 1px under it
export const CHAT_FONT_SIZE = { min: 12, max: 22, default: 15 }
// the chat's text weight; markdown headings are 600, so the choices stop under it
export const CHAT_FONT_WEIGHT = {
	default: 400,
	options: [
		{ label: "Light", value: 300 },
		{ label: "Regular", value: 400 },
		{ label: "Medium", value: 500 },
	],
}
