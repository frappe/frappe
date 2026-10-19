import fs from "node:fs"
import path from "node:path"

/**
 * Every `<frappe_app>/studio/` folder on the bench and the exported studio apps inside it.
 *
 * frappe keeps this editor in its `studio/` folder, so its exported apps are only the subfolders
 * `studio_apps.txt` lists; any other app's `studio/` folder holds nothing but exported apps.
 */
export function getStudioRoots(appsDir) {
	return listFolder(appsDir).flatMap((frappeApp) => {
		const root = path.join(appsDir, frappeApp, "studio")
		if (!isDirectory(root)) return []
		const names = frappeApp === "frappe" ? readStudioAppsTxt(root) : listFolder(root)
		const folders = names.map((name) => path.join(root, name)).filter(isDirectory)
		return [{ frappeApp, root, folders }]
	})
}

export function findStudioAppFolders(appsDir) {
	return getStudioRoots(appsDir).flatMap((studioRoot) => studioRoot.folders)
}

function readStudioAppsTxt(root) {
	const file = path.join(root, "studio_apps.txt")
	if (!fs.existsSync(file)) return []
	return fs
		.readFileSync(file, "utf8")
		.split("\n")
		.map((line) => line.trim())
		.filter(Boolean)
}

function listFolder(folder) {
	return fs.existsSync(folder) ? fs.readdirSync(folder) : []
}

function isDirectory(folder) {
	return fs.existsSync(folder) && fs.statSync(folder).isDirectory()
}
