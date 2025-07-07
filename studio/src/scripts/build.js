import { FRAPPE_UI_COMPONENTS, STUDIO_COMPONENTS } from "../utils/constants.js"
import { writeFileSync } from "fs"
import fs from "fs"
import { build } from "vite"
import vue from "@vitejs/plugin-vue"
import path from "node:path"
import { fileURLToPath } from "node:url"
import frappeui from "frappe-ui/vite/index.js"

const __dirname = fileURLToPath(new URL(".", import.meta.url))

// create a temp directory for app renderers in studio app folder
const TEMP_DIR = path.resolve(__dirname, "../../../.temp-app-renderers")
if (!fs.existsSync(TEMP_DIR)) {
	fs.mkdirSync(TEMP_DIR, { recursive: true })
}

const args = process.argv.slice(2)
const appName = args[0]
const components = args[2]

if (!appName) {
	console.error("App name is required")
	process.exit(1)
}

await generateAppBuild(appName, components)

export async function generateAppBuild(appName, components) {
	if (!appName) return

	const componentList = components ? components.split(",") : []
	const componentSources = findComponentSources(componentList)
	const rendererContent = getRendererContent(componentSources)
	const tempRendererPath = writeRendererFile(appName, rendererContent)
	await buildWithVite(appName, tempRendererPath)
	deleteRendererFile(tempRendererPath)
}

function findComponentSources(appComponents) {
	const frappeUIComponents = []
	const studioComponents = []

	appComponents.forEach((component) => {
		if (FRAPPE_UI_COMPONENTS.includes(component)) {
			frappeUIComponents.push(component)
		} else if (STUDIO_COMPONENTS.includes(component)) {
			studioComponents.push(component)
		}
	})
	return {
		frappeUIComponents: frappeUIComponents,
		studioComponents: studioComponents,
	}
}

function getRendererContent(componentSources) {
	const { frappeUIComponents, studioComponents } = componentSources
	const frappeUIImports =
		frappeUIComponents.length > 0 ? `import { ${frappeUIComponents.join(",\n ")} } from "frappe-ui";` : ""

	const studioImports = studioComponents
		.map((comp) => `import ${comp} from "@/components/AppLayout/${comp}.vue"`)
		.join("\n")

	const componentRegistrations = [
		...frappeUIComponents.map((comp) => `app.component("${comp}", ${comp})`),
		...studioComponents.map((comp) => `app.component("${comp}", ${comp})`),
	].join("\n")

	const rendererContent = `import "@/index.css"
import { createApp } from "vue"
import { createPinia } from "pinia"
import "@/setupFrappeUIResource"
import app_router from "@/router/app_router"
import AppRenderer from "@/AppRenderer.vue"
import { resourcesPlugin } from "frappe-ui"

${frappeUIImports}
${studioImports}

const app = createApp(AppRenderer)
const pinia = createPinia()

app.use(app_router)
app.use(pinia)
app.use(resourcesPlugin)

${componentRegistrations}
window.__APP_COMPONENTS__ = app._context.components

app.mount("#app")`
	return rendererContent
}

function writeRendererFile(appName, content) {
	const rendererPath = path.resolve(TEMP_DIR, `renderer-${appName}.js`)

	writeFileSync(rendererPath, content)
	console.log(`Renderer file created at: ${rendererPath}`)
	return rendererPath
}

async function buildWithVite(appName, entryFilePath) {
	console.log(`Building ${appName} with Vite`)
	await build({
		root: path.resolve(__dirname, "../"),
		base: "/assets/studio/app_builds/",
		server: {
			// explicitly set origin of generated assets (images, fonts, etc) during development.
			// Required for the app renderer running on webserver port
			// https://vite.dev/guide/backend-integration
			origin: "http://127.0.0.1:8080",
			allowedHosts: true,
		},
		plugins: [
			vue(),
			frappeui({
				frappeProxy: true,
				lucideIcons: true,
			}),
		],
		resolve: {
			alias: {
				vue: "vue/dist/vue.esm-bundler.js",
				"@": path.resolve(__dirname, "../"),
			},
		},
		build: {
			manifest: true,
			rollupOptions: {
				input: {
					studioRenderer: path.resolve(__dirname, entryFilePath),
				},
			},
			outDir: path.resolve(__dirname, `../../../studio/public/app_builds/${appName}`),
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
