import { FRAPPE_UI_COMPONENTS, FRAPPE_COMPONENTS, STUDIO_COMPONENTS } from "../utils/constants.js"
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

const __dirname = fileURLToPath(new URL(".", import.meta.url))

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
	const frappeComponents = []
	const studioComponents = []

	appComponents.forEach((component) => {
		if (FRAPPE_UI_COMPONENTS.includes(component)) {
			frappeUIComponents.push(component)
		} else if (FRAPPE_COMPONENTS.includes(component)) {
			frappeComponents.push(component)
		} else if (STUDIO_COMPONENTS.includes(component)) {
			studioComponents.push(component)
		}
	})
	return {
		frappeUIComponents,
		frappeComponents,
		studioComponents,
		customComponents,
	}
}

function getRendererContent(componentSources, pageScripts = []) {
	const { frappeUIComponents, frappeComponents, studioComponents, customComponents } = componentSources
	const frappeUIImports =
		frappeUIComponents.length > 0 ? `import { ${frappeUIComponents.join(",\n ")} } from "frappe-ui";` : ""
	const frappeImports =
		frappeComponents.length > 0 ? `import { ${frappeComponents.join(",\n ")} } from "frappe-ui/frappe";` : ""
	const studioImports = studioComponents
		.map((comp) => `import ${comp} from "@/components/AppLayout/${comp}.vue"`)
		.join("\n")
	const customComponentNames = Object.keys(customComponents)
	const customImports = customComponentNames
		.map((name) => `import ${name} from "${customComponents[name]}"`)
		.join("\n")

	const componentRegistrations = [
		...frappeUIComponents.map((comp) => `app.component("${comp}", ${comp})`),
		...frappeComponents.map((comp) => `app.component("${comp}", ${comp})`),
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
${pageScripts.map((p) => `	${JSON.stringify(p.page_name)}: () => import(${JSON.stringify(p.file_path)}),`).join("\n")}
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
${frappeImports}
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
			alias: {
				"@": path.resolve(__dirname, "../"),
			},
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
