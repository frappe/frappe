// Dev-only helper to suppress a Vite full page reload.
//
// Vite watches the whole project, so adding/removing a file under studio/<app>/ (which the file
// explorer does) makes the dev server send a `full-reload` — even though an empty new file or a
// removed unused file changes nothing in the running app. That reload throws away the Studio editor
// state (the open file, scroll position, etc.). Content edits don't reload (Vite emits a plain
// `change` the editor app doesn't import), so only create/delete need this.
//
// Trick: throwing inside the `vite:beforeFullReload` listener aborts Vite's reload handler before it
// calls location.reload(). We only throw inside a short window opened by a deliberate file op.

let suppressReloadUntil = 0

/** Swallow the next Vite full reload that lands within `windowMs` (call right before a create/delete). */
export function suppressNextViteReload(windowMs = 2000) {
	suppressReloadUntil = Date.now() + windowMs
}

if (import.meta.hot) {
	import.meta.hot.on("vite:beforeFullReload", () => {
		if (Date.now() < suppressReloadUntil) {
			throw new Error("[studio] suppressed full reload after a file-explorer change")
		}
	})
}
