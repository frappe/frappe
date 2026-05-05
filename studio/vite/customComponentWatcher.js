import path from "path"
import fs from "fs"

/**
 * Vite plugin that watches for custom Vue component file additions,
 * deletions, and renames in `<app>/studio/` directories across
 * all bench apps.
 *
 * When the file list changes, it sends a custom HMR event
 * (`studio:custom-components-changed`) to the client so the
 * component panel can re-fetch the component list from the API
 * without a full page reload.
 *
 * Content changes to existing components are already handled by
 * Vite's built-in HMR since the files are in its module graph.
 */
function customComponentWatcher(appsDir) {
	let server

	function getStudioFolders() {
		const folders = []
		if (!fs.existsSync(appsDir)) return folders

		for (const appName of fs.readdirSync(appsDir)) {
			// Skip studio itself, already watched
			if (appName === "studio") continue

			const studioDir = path.join(appsDir, appName, "studio")
			if (fs.existsSync(studioDir) && fs.statSync(studioDir).isDirectory()) {
				folders.push(studioDir)
			}
		}
		return folders
	}

	return {
		name: "custom-component-watcher",
		apply: "serve", // dev mode only

		configureServer(_server) {
			server = _server

			const studioFolders = getStudioFolders()
			if (!studioFolders.length) return

			// Watch all studio folders for .vue file changes
			const watcher = server.watcher

			for (const folder of studioFolders) {
				watcher.add(folder)
			}

			function isStudioVueFile(filePath) {
				if (!filePath.endsWith(".vue")) return false
				return studioFolders.some((folder) => filePath.startsWith(folder))
			}

			function notifyClient() {
				server.ws.send({
					type: "custom",
					event: "studio:custom-components-changed",
				})
			}

			watcher.on("add", (filePath) => {
				if (isStudioVueFile(filePath)) {
					console.log(`[studio] New component detected: ${path.basename(filePath)}`)
					notifyClient()
				}
			})

			watcher.on("unlink", (filePath) => {
				if (isStudioVueFile(filePath)) {
					console.log(`[studio] Component removed: ${path.basename(filePath)}`)
					notifyClient()
				}
			})
		},
	}
}

export default customComponentWatcher
