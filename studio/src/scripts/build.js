import {
	FRAPPE_UI_COMPONENTS,
	FRAPPE_UI_MOLECULES,
	FRAPPE_COMPONENTS,
	STUDIO_COMPONENTS,
	FRAMEWORK_UI_COMPONENTS,
} from "../utils/constants.js"
import { writeFileSync } from "fs"
import fs from "fs"
import { build } from "vite"
import vue from "@vitejs/plugin-vue"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { parseArgs } from "node:util"
import frappeui from "frappe-ui/vite"
import sharedDependencyResolver from "../../vite/sharedDependencyResolver.js"
import studioRootAlias from "../../vite/studioRootAlias.js"
import frameworkUIAlias from "../../vite/frameworkUIAlias.js"

const __dirname = fileURLToPath(new URL(".", import.meta.url))
// bench apps folder (scripts -> src -> frontend -> studio -> apps)
const APPS_DIR = path.resolve(__dirname, "../../../../")

// @framework/ui (apps/frappe/ui) is absent on older frappe. Skip its imports and
// aliases so the exported-app build doesn't try to resolve a missing package.
const frameworkUIAvailable = fs.existsSync(path.resolve(APPS_DIR, "frappe", "ui", "package.json"))

// @framework/ui components are spread across the root barrel and per-widget subpath
// exports, so their imports must be grouped by source module. Components with a
// dedicated subpath export (grouped/heavier widgets) go here.
const FRAMEWORK_UI_IMPORT_SOURCES = {
	Filter: "@framework/ui/Filter",
	SortBy: "@framework/ui/SortBy",
	QuickFilter: "@framework/ui/QuickFilter",
	ColumnSettings: "@framework/ui/ColumnSettings",
	ListViewShell: "@framework/ui/ListView",
	FileUploadDialog: "@framework/ui/FileUpload",
	AttachmentsList: "@framework/ui/FileUpload",
	UploadTray: "@framework/ui/FileUpload",
}

// Components imported as named exports from the root "@framework/ui" barrel. Kept as
// an explicit allowlist (verified against apps/frappe/ui/src/index.ts and its
// Notifications/ActivityTimeline sub-barrels) rather than a silent fallback, so a new
// component can't emit an unresolvable barrel import — getFrameworkUIImports throws if
// a component is in neither map. Every FRAMEWORK_UI_COMPONENTS entry must be in exactly
// one of these two.
const FRAMEWORK_UI_BARREL_COMPONENTS = new Set([
	"FormLayout",
	"Link",
	"Grid",
	"Phone",
	"TableMultiSelect",
	"NotificationPanel",
	"NotificationItem",
	"ActivityTimeline",
	"EmailItem",
	"CommentItem",
	"EmailComposer",
	"CommentComposer",
])

// create a temp directory for app renderers in studio app folder
const TEMP_DIR = path.resolve(__dirname, "../../../.temp-app-renderers")
if (!fs.existsSync(TEMP_DIR)) {
	fs.mkdirSync(TEMP_DIR, { recursive: true })
}

const { values: argv } = parseArgs({
	options: {
		app: { type: "string" },
		components: { type: "string" },
		"out-dir": { type: "string" },
		base: { type: "string" },
		"custom-components": { type: "string" },
		"page-scripts": { type: "string" },
	},
	strict: false,
})

if (!argv.app) {
	console.error("--app is required")
	process.exit(1)
}

await generateAppBuild(
	argv.app,
	argv.components,
	argv["out-dir"],
	argv.base,
	argv["custom-components"],
	argv["page-scripts"],
)

export async function generateAppBuild(
	appName,
	components,
	outDir,
	base,
	customComponentsJson,
	pageScriptsJson,
) {
	if (!appName) return

	const componentList = components ? components.split(",") : []
	const customComponents = customComponentsJson ? JSON.parse(customComponentsJson) : {}
	// pageScripts: [{ page_name, file_path }]
	const pageScripts = pageScriptsJson ? JSON.parse(pageScriptsJson) : []
	const componentSources = findComponentSources(componentList, customComponents)
	const rendererContent = getRendererContent(componentSources, pageScripts)
	const tempRendererPath = writeRendererFile(appName, rendererContent)
	await buildWithVite(appName, tempRendererPath, outDir, base)
	deleteRendererFile(tempRendererPath)
}

function findComponentSources(appComponents, customComponents = {}) {
	const frappeUIComponents = []
	const frappeUIMolecules = []
	const frappeComponents = []
	const frameworkUIComponents = []
	const studioComponents = []
	const missingComponents = []

	appComponents.forEach((component) => {
		if (FRAPPE_UI_COMPONENTS.includes(component)) {
			frappeUIComponents.push(component)
		} else if (FRAPPE_UI_MOLECULES.includes(component)) {
			frappeUIMolecules.push(component)
		} else if (FRAPPE_COMPONENTS.includes(component)) {
			frappeComponents.push(component)
		} else if (FRAMEWORK_UI_COMPONENTS.includes(component)) {
			// Drop @framework/ui components when the package isn't on this bench —
			// a stale app reference must not break the build with an unresolvable import.
			if (frameworkUIAvailable) frameworkUIComponents.push(component)
		} else if (STUDIO_COMPONENTS.includes(component)) {
			studioComponents.push(component)
		} else {
			missingComponents.push(component)
		}
	})

	if (missingComponents.length) {
		throw new Error(
			`Components used by this app are missing from the build lists: ` + `${missingComponents.join(", ")}`,
		)
	}
	return {
		frappeUIComponents,
		frappeUIMolecules,
		frappeComponents,
		frameworkUIComponents,
		studioComponents,
		customComponents,
	}
}

function getRendererContent(componentSources, pageScripts = []) {
	const {
		frappeUIComponents,
		frappeUIMolecules,
		frappeComponents,
		frameworkUIComponents,
		studioComponents,
		customComponents,
	} = componentSources
	const frappeUIImports =
		frappeUIComponents.length > 0 ? `import { ${frappeUIComponents.join(",\n ")} } from "frappe-ui";` : ""
	// Molecules ship from a dedicated subpath
	const frappeUIMoleculeImports =
		frappeUIMolecules.length > 0 ? `import { ${frappeUIMolecules.join(",\n ")} } from "frappe-ui/list";` : ""
	const frappeImports =
		frappeComponents.length > 0 ? `import { ${frappeComponents.join(",\n ")} } from "frappe-ui/frappe";` : ""
	const frameworkUIImports = getFrameworkUIImports(frameworkUIComponents)
	const studioImports = studioComponents
		.map((comp) => `import ${comp} from "@/components/AppLayout/${comp}.vue"`)
		.join("\n")
	const customComponentNames = Object.keys(customComponents)
	const customImports = customComponentNames
		.map((name) => `import ${name} from "${customComponents[name]}"`)
		.join("\n")

	const componentRegistrations = [
		...frappeUIComponents.map((comp) => `app.component("${comp}", ${comp})`),
		...frappeUIMolecules.map((comp) => `app.component("${comp}", ${comp})`),
		...frappeComponents.map((comp) => `app.component("${comp}", ${comp})`),
		...frameworkUIComponents.map((comp) => `app.component("${comp}", ${comp})`),
		...studioComponents.map((comp) => `app.component("${comp}", ${comp})`),
		...customComponentNames.map((comp) => `app.component("${comp}", ${comp})`),
	].join("\n")

	// Per-page setup() modules keyed by page docname (code mode). The import() literals make
	// Rollup chunk each page script (and the modules it imports); codeStore loads them on
	// navigation.
	const pageScriptImport = pageScripts.length
		? `import { setPageScriptImporters } from "@/data/studioPageScripts"`
		: ""
	const pageScriptSetup = pageScripts.length
		? `setPageScriptImporters({
${pageScripts
	.map((p) => `	${JSON.stringify(p.page_name)}: () => import(${JSON.stringify(p.file_path)}),`)
	.join("\n")}
})`
		: ""

	const rendererContent = `import "@/index.css"
import { createApp } from "vue"
import { createPinia } from "pinia"
import "@/setupFrappeUIResource"
import app_router from "@/router/app_router"
import AppRenderer from "@/AppRenderer.vue"
import { resourcesPlugin } from "frappe-ui"
import { spritePlugin } from "frappe-ui/icons"

${frappeUIImports}
${frappeUIMoleculeImports}
${frappeImports}
${frameworkUIImports}
${studioImports}
${customImports}
${pageScriptImport}

const app = createApp(AppRenderer)
const pinia = createPinia()

app.use(app_router)
app.use(pinia)
app.use(resourcesPlugin)
app.use(spritePlugin)

${componentRegistrations}
window.__APP_COMPONENTS__ = app._context.components

${pageScriptSetup}
app.mount("#app")`
	return rendererContent
}

// Build one `import { … } from "<source>"` line per @framework/ui source module,
// since these components come from the root barrel plus several subpath exports.
function getFrameworkUIImports(frameworkUIComponents) {
	const bySource = {}
	for (const comp of frameworkUIComponents) {
		const source =
			FRAMEWORK_UI_IMPORT_SOURCES[comp] || (FRAMEWORK_UI_BARREL_COMPONENTS.has(comp) ? "@framework/ui" : null)
		if (!source) {
			throw new Error(
				`@framework/ui component "${comp}" has no import source. Add it to ` +
					`FRAMEWORK_UI_IMPORT_SOURCES (dedicated subpath) or FRAMEWORK_UI_BARREL_COMPONENTS ` +
					`(and ensure apps/frappe/ui/src/index.ts re-exports it).`,
			)
		}
		bySource[source] ||= []
		bySource[source].push(comp)
	}
	return Object.entries(bySource)
		.map(([source, comps]) => `import { ${comps.join(", ")} } from "${source}";`)
		.join("\n")
}

function writeRendererFile(appName, content) {
	const rendererPath = path.resolve(TEMP_DIR, `renderer-${appName}.js`)

	writeFileSync(rendererPath, content)
	console.log(`Renderer file created at: ${rendererPath}`)
	return rendererPath
}

async function buildWithVite(appName, entryFilePath, outDir, basePath) {
	outDir = outDir || path.resolve(__dirname, `../../../studio/public/app_builds/${appName}`)
	basePath = basePath || `/assets/studio/app_builds/${appName}/`

	console.log(`Building ${appName} with Vite`)
	await build({
		root: path.resolve(__dirname, "../"),
		base: basePath,
		plugins: [
			vue(),
			frappeui({
				frappeProxy: true,
				lucideIcons: true,
				buildConfig: false,
				jinjaBootData: false,
			}),
			studioRootAlias(),
			sharedDependencyResolver(path.resolve(__dirname, "../../")),
		],
		resolve: {
			alias: [
				...(frameworkUIAvailable ? frameworkUIAlias(APPS_DIR) : []),
				{ find: "@", replacement: path.resolve(__dirname, "../") },
			],
			// keep vue/pinia/etc as single instances so studio modules (composables/stores)
			// share the app's runtime — Pinia breaks with duplicate copies
			dedupe: ["vue", "vue-router", "pinia", "frappe-ui"],
		},
		build: {
			manifest: true,
			rolldownOptions: {
				input: {
					studioRenderer: path.resolve(__dirname, entryFilePath),
				},
			},
			outDir: outDir,
			emptyOutDir: true,
			target: "es2015",
			sourcemap: true,
			chunkSizeWarningLimit: 1000,
		},
		optimizeDeps: {
			include: ["frappe-ui > feather-icons", "showdown", "engine.io-client"],
		},
	})

	console.log(`Vite build completed for ${appName}`)
}

function deleteRendererFile(rendererPath) {
	try {
		fs.unlinkSync(rendererPath)
		console.log(`Deleted temporary renderer file: ${rendererPath}`)
	} catch (error) {
		console.warn(`Could not delete temporary renderer file: ${rendererPath} - ${error.message}`)
	}
}
