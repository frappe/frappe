import fs from "node:fs"
import path from "node:path"
import loadTailwindConfig from "tailwindcss/loadConfig.js"
import { findStudioAppFolders } from "../vite/studioApps.js"

const CONFIG_FILE = "tailwind.config.js"
const SUPPORTED_KEYS = ["content", "safelist"]

/**
 * A studio app can ship `<frappe_app>/studio/<studio_app>/tailwind.config.js` (beside its tsconfig.json)
 * to add `content` globs and `safelist` entries, e.g. for components shared with its desk UI that
 * live outside the studio app folder.
 */
export function mergeStudioAppConfigs(baseConfig, appFolders) {
	const appConfigs = appFolders
		.map((folder) => path.join(folder, CONFIG_FILE))
		.filter((configPath) => fs.existsSync(configPath))
		.map(loadStudioAppConfig)
	return {
		...baseConfig,
		content: [...baseConfig.content, ...appConfigs.flatMap((config) => config.content)],
		safelist: [...(baseConfig.safelist || []), ...appConfigs.flatMap((config) => config.safelist)],
	}
}

export { findStudioAppFolders }

function loadStudioAppConfig(configPath) {
	const config = loadTailwindConfig(configPath)
	warnUnsupportedKeys(configPath, config)
	const globs = (config.content || []).map((entry) => resolveGlob(entry, path.dirname(configPath)))
	return {
		content: [...globs, ...globs.map(excludeNodeModules).filter(Boolean)],
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

// Shared folders often carry their own node_modules, which would slow every editor start
function excludeNodeModules(glob) {
	if (typeof glob !== "string" || glob.startsWith("!")) return null
	const folder = glob.split(/[*?{[]/)[0].replace(/\/[^/]*$/, "")
	return `!${folder}/**/node_modules/**`
}

function warnUnsupportedKeys(configPath, config) {
	const ignored = Object.keys(config).filter((key) => !SUPPORTED_KEYS.includes(key))
	if (ignored.length) {
		console.warn(
			`${configPath}: only ${SUPPORTED_KEYS.join(", ")} are supported, ignoring ${ignored.join(", ")}`,
		)
	}
}
