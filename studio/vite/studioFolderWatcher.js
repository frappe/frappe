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

		// Vite 8 calls hotUpdate for create/update/delete. These external studio files
		// aren't in the editor's module graph, so suppress the reload Vite would otherwise do.
		hotUpdate({ type, file, modules }) {
			if (!isUnderStudioFolder(file)) return
			// A mounted custom component being edited: let Vue HMR update it in place.
			if (type === "update" && modules.length > 0) return
			// create / delete / edit-of-unmounted: nothing here to update — swallow the reload.
			// The watcher below refreshes the component panel for .vue changes.
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

// chokidar/Vite report paths with forward slashes; match that so startsWith comparisons hold.
function normalize(filePath) {
	return filePath.replace(/\\/g, "/")
}

export default studioFolderWatcher
