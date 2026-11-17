// App-wide keyboard shortcuts, installed once by FlowChat. Add entries here.
// Combos compare exact modifiers and the key: the plain character it types, so
// Dvorak's Cmd+X (QWERTY's B) stays cut, else the physical key code (Option+B
// types "∫" in e.key on mac). `mod` is the primary modifier and,
// as in Frappe desk, matches either Cmd or Ctrl on every OS. The listener
// captures on window with preventDefault so combos win over browser bindings
// (Firefox's bookmarks sidebar) and focused inputs.

export const SHORTCUTS = [
	{
		combo: { mod: true, code: "KeyB" },
		description: "Toggle the session sidebar",
		run: (store) => store.setSidebarOpen(!store.state.sidebarOpen),
	},
	{
		combo: { mod: true, alt: true, code: "KeyB" },
		description: "Toggle the workspace panel",
		run: (store) => store.setWorkspaceOpen(!store.state.workspace.open),
	},
	{
		combo: { mod: true, code: "Comma" },
		description: "Open settings",
		run: (store) => store.setSettingsOpen(true),
	},
]

// the character a combo's key types on a QWERTY layout
const QWERTY = { Comma: "," }
const typedBy = (code) => (code.startsWith("Key") ? code.slice(3).toLowerCase() : QWERTY[code])

export function findShortcut(event, shortcuts = SHORTCUTS) {
	const mod = event.metaKey || event.ctrlKey
	const typed = /^[!-~]$/.test(event.key ?? "") ? event.key.toLowerCase() : null
	return (
		shortcuts.find(
			({ combo }) =>
				(typed ? typedBy(combo.code) === typed : combo.code === event.code) &&
				!!combo.mod === mod &&
				!!combo.alt === event.altKey &&
				!!combo.shift === event.shiftKey,
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
