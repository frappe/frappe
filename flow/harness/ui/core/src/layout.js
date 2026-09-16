// Tailwind's md: at and above it the sidebar is a docked column, below it a drawer over the chat.
const wide = globalThis.matchMedia?.("(min-width: 768px)")

export const sidebarIsDrawer = () => !!wide && !wide.matches

export const onSidebarLayoutChange = (fn) => wide?.addEventListener("change", fn)
