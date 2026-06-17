import path from "path"
import fs from "fs"

/**
 * Vite plugin for editing exported apps' `<app>/studio/` folders from Studio.
 *
 * Two jobs:
 *
 * 1. Detect file changes so the UI can re-fetch over custom HMR events instead of a
 *    full page reload: `studio:files-changed` (add/remove -> file explorer reloads its
 *    tree), `studio:file-changed` (content edited -> file explorer re-reads the open
 *    file) and `studio:custom-components-changed` (.vue add/remove -> component panel
 *    re-fetches its list).
 *
 * 2. Stop Vite from full-reloading the whole editor when files under those folders
 *    are created/deleted/renamed (via the file explorer or directly on disk). These
 *    files aren't part of the editor app's module graph, so Vite's default
 *    "unknown change -> full-reload" fallback would needlessly blow away editor state.
 *    The `hotUpdate` hook swallows those events; genuine edits to a mounted custom
 *    component still hot-update via Vue's HMR.
 */
function studioFolderWatcher(appsDir) {
	let studioFoldersCache = null

	function getStudioFolders() {
		if (studioFoldersCache) return studioFoldersCache
		const folders = []
		if (fs.existsSync(appsDir)) {
			for (const appName of fs.readdirSync(appsDir)) {
				// Skip studio itself, already watched
				if (appName === "studio") continue
				const studioDir = path.join(appsDir, appName, "studio")
				if (fs.existsSync(studioDir) && fs.statSync(studioDir).isDirectory()) {
					folders.push(normalize(studioDir))
				}
			}
		}
		studioFoldersCache = folders
		return folders
	}

	function isUnderStudioFolder(filePath) {
		const file = normalize(filePath)
		return getStudioFolders().some((folder) => file.startsWith(folder + "/"))
	}

	return {
		name: "studio-folder-watcher",
		apply: "serve", // dev mode only

		// Make each exported page script a self-accepting HMR boundary. Page scripts load in the
		// exported app's own module graph (via dynamic import), so editing one — or a composable/util
		// it imports — has no boundary to propagate to and Vite would full-reload. Injecting accept()
		// lets Vite hot-swap the page script in place (with its deps re-fetched fresh) and hand the
		// new module to the editor, which re-runs setup(). The page docname is baked in from the
		// sibling JSON so the editor can match it to the active page. Stores keep their singleton
		// state across this (they refresh code only via their own acceptHMRUpdate).
		transform(code, id) {
			const pageName = pageScriptName(id)
			if (!pageName) return
			return { code: code + pageScriptHmrFooter(pageName), map: null }
		},

		// Page scripts and their imports now reach a boundary, so let Vite's HMR run for in-graph
		// content edits (the page-script accept above, or the vue plugin for mounted .vue files).
		// Swallow only structural changes (create/delete/rename — the file explorer/component panel
		// refresh via the custom studio:* events below) and edits to files that aren't imported
		// anywhere, where Vite would otherwise full-reload the whole editor for nothing.
		hotUpdate({ type, file, modules }) {
			if (!isUnderStudioFolder(file)) return
			if (type !== "update") return []
			if (modules.length > 0) return
			return []
		},

		configureServer(server) {
			const studioFolders = getStudioFolders()
			if (!studioFolders.length) return

			const watcher = server.watcher
			for (const folder of studioFolders) {
				watcher.add(folder)
			}

			function send(event, data) {
				server.ws.send({ type: "custom", event, data })
			}

			// Path relative to the frappe app's studio/ dir, i.e. "<studio_app>/<rest>" — what the
			// client uses to identify a file (its open-file path prefixed with the studio app name).
			function studioRelativePath(filePath) {
				const file = normalize(filePath)
				const folder = getStudioFolders().find((f) => file.startsWith(f + "/"))
				return folder ? file.slice(folder.length + 1) : null
			}

			// A studio file was added/removed/renamed: refresh the file explorer tree, and the
			// component panel too when it's a .vue.
			function onStructureChange(filePath, action) {
				if (!isUnderStudioFolder(filePath)) return
				send("studio:files-changed")
				if (filePath.endsWith(".vue")) {
					console.log(`[studio] Component ${action}: ${path.basename(filePath)}`)
					send("studio:custom-components-changed")
				}
			}

			watcher.on("add", (filePath) => onStructureChange(filePath, "added"))
			watcher.on("unlink", (filePath) => onStructureChange(filePath, "removed"))

			// A studio file's content changed on disk (e.g. edited in another editor): tell the client
			// which file so it can re-read it if it's the one open.
			watcher.on("change", (filePath) => {
				const relativePath = studioRelativePath(filePath)
				if (relativePath) send("studio:file-changed", { path: relativePath })
			})
		},
	}
}

// A page exports to `studio/<studio_app>/studio_page/<stem>/<stem>.ts`; the docname lives in the
// sibling `<stem>.json`. Returns the page docname for a page-script module id, else null.
const PAGE_SCRIPT_RE = /\/studio\/[^/]+\/studio_page\/([^/]+)\/([^/]+)\.ts$/

function pageScriptName(id) {
	let file = normalize(id).split("?")[0]
	if (file.startsWith("/@fs/")) file = file.slice("/@fs".length)
	const match = file.match(PAGE_SCRIPT_RE)
	if (!match || match[1] !== match[2]) return null
	try {
		const json = JSON.parse(fs.readFileSync(file.replace(/\.ts$/, ".json"), "utf8"))
		return json.page_name || null
	} catch {
		return null
	}
}

function pageScriptHmrFooter(pageName) {
	return `
if (import.meta.hot) {
	import.meta.hot.accept((mod) => {
		if (mod && window.__STUDIO_HMR_applyPageScript) window.__STUDIO_HMR_applyPageScript(${JSON.stringify(pageName)}, mod)
	})
}
`
}

// chokidar/Vite report paths with forward slashes; match that so startsWith comparisons hold.
function normalize(filePath) {
	return filePath.replace(/\\/g, "/")
}

export default studioFolderWatcher
