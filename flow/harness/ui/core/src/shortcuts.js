// App-wide keyboard shortcuts, installed once by FlowChat. Add entries here.
// Combos compare exact modifiers and the physical key code (layout-safe:
// Option+B types "∫" in e.key on mac). The listener captures on window with
// preventDefault so combos win over browser bindings (Firefox's bookmarks
// sidebar) and focused inputs.

export const SHORTCUTS = [
	{
		combo: { meta: true, code: "KeyB" },
		description: "Toggle the session sidebar",
		run: (store) => store.setSidebarOpen(store.state.prefs.sidebarOpen === false),
	},
	{
		combo: { meta: true, alt: true, code: "KeyB" },
		description: "Toggle the workspace panel",
		run: (store) => store.setWorkspaceOpen(!store.state.workspace.open),
	},
]

export function findShortcut(event, shortcuts = SHORTCUTS) {
	return (
		shortcuts.find(
			({ combo }) =>
				combo.code === event.code &&
				!!combo.meta === event.metaKey &&
				!!combo.alt === event.altKey &&
				!!combo.shift === event.shiftKey &&
				!!combo.ctrl === event.ctrlKey,
		) ?? null
	)
}

export function installShortcuts(store) {
	const onKey = (event) => {
		const shortcut = findShortcut(event)
		if (!shortcut) return
		event.preventDefault()
		event.stopPropagation()
		shortcut.run(store)
	}
	window.addEventListener("keydown", onKey, true)
	return () => window.removeEventListener("keydown", onKey, true)
}
