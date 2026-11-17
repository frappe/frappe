import fs from "node:fs"
import path from "node:path"

/**
 * Every `<frappe_app>/studio/` folder on the bench and the exported studio apps inside it.
 *
 * A subfolder is an exported app only when it holds its app JSON (`my-app/my_app.json`), the same
 * rule the Python side uses; frappe's editor under `studio/frontend/` has none.
 */
export function getStudioRoots(appsDir) {
	return listFolder(appsDir).flatMap((frappeApp) => {
		const root = path.join(appsDir, frappeApp, "studio")
		if (!isDirectory(root)) return []
		const folders = listFolder(root)
			.map((name) => path.join(root, name))
			.filter(isStudioAppFolder)
		return [{ frappeApp, root, folders }]
	})
}

export function findStudioAppFolders(appsDir) {
	return getStudioRoots(appsDir).flatMap((studioRoot) => studioRoot.folders)
}

export function isStudioAppFolder(folder) {
	return isDirectory(folder) && fs.existsSync(path.join(folder, `${scrub(path.basename(folder))}.json`))
}

// frappe.scrub: spaces and hyphens become underscores, lowercase
function scrub(name) {
	return name.replace(/[ -]/g, "_").toLowerCase()
}

function listFolder(folder) {
	return fs.existsSync(folder) ? fs.readdirSync(folder) : []
}

function isDirectory(folder) {
	return fs.existsSync(folder) && fs.statSync(folder).isDirectory()
}
