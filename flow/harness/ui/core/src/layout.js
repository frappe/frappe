// Tailwind's md: at and above it the sidebar is a docked column, below it a drawer over the chat.
const wide = globalThis.matchMedia?.("(min-width: 768px)")

export const sidebarIsDrawer = () => !!wide && !wide.matches

export const onSidebarLayoutChange = (fn) => wide?.addEventListener("change", fn)

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
