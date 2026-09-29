import fs from "node:fs"
import path from "node:path"
import loadTailwindConfig from "tailwindcss/loadConfig.js"

const CONFIG_FILE = "tailwind.config.js"
const SUPPORTED_KEYS = ["content", "safelist"]

/**
 * A studio app can ship `<frappe_app>/studio/<studio_app>/tailwind.config.js` (beside its tsconfig.json)
 * to add `content` globs and `safelist` entries, e.g. for components shared with its desk UI that
 * live outside the studio app folder. Pass `studioApp` to merge only that app's config.
 */
export function mergeStudioAppConfigs(baseConfig, appsDir, studioApp) {
	const appConfigs = findConfigPaths(appsDir, studioApp).map(loadStudioAppConfig)
	return {
		...baseConfig,
		content: [...baseConfig.content, ...appConfigs.flatMap((config) => config.content)],
		safelist: [...(baseConfig.safelist || []), ...appConfigs.flatMap((config) => config.safelist)],
	}
}

function findConfigPaths(appsDir, studioApp) {
	return fs.readdirSync(appsDir).flatMap((frappeApp) => {
		const studioDir = path.join(appsDir, frappeApp, "studio")
		const studioAppFolders = studioApp ? [scrub(studioApp)] : listFolder(studioDir)
		return studioAppFolders
			.map((folder) => path.join(studioDir, folder, CONFIG_FILE))
			.filter((configPath) => fs.existsSync(configPath))
	})
}

function loadStudioAppConfig(configPath) {
	const config = loadTailwindConfig(configPath)
	warnUnsupportedKeys(configPath, config)
	const content = Array.isArray(config.content) ? config.content : config.content?.files || []
	return {
		content: content.map((entry) => resolveGlob(entry, path.dirname(configPath))),
		safelist: config.safelist || [],
	}
}

// Tailwind resolves content globs from the cwd, so make them relative to the app's config
function resolveGlob(entry, configDir) {
	if (typeof entry !== "string") return entry
	const negated = entry.startsWith("!")
	const resolved = path.resolve(configDir, negated ? entry.slice(1) : entry)
	return negated ? `!${resolved}` : resolved
}

function warnUnsupportedKeys(configPath, config) {
	const ignored = Object.keys(config).filter((key) => !SUPPORTED_KEYS.includes(key))
	if (ignored.length) {
		console.warn(
			`${configPath}: only ${SUPPORTED_KEYS.join(", ")} are supported, ignoring ${ignored.join(", ")}`,
		)
	}
}

function listFolder(folder) {
	return fs.existsSync(folder) ? fs.readdirSync(folder) : []
}

// Same as frappe.scrub, which names the studio app folder on export
function scrub(name) {
	return name.replaceAll(" ", "_").replaceAll("-", "_").toLowerCase()
}
