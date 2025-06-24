import { FRAPPE_UI_COMPONENTS, STUDIO_COMPONENTS } from "../utils/constants.js"

const args = process.argv.slice(2)
const appName = args[0]
const components = args[2]

if (!appName) {
	console.error("App name is required. Use --app_name=<app_name> to specify the app.")
	process.exit(1)
}

await generateAppBuild(appName, components)

export async function generateAppBuild(appName, components) {
	if (!appName) return

	const componentList = components ? components.split(",") : []
	const componentSources = findComponentSources(componentList)
	const rendererContent = getRendererContent(componentSources)
	console.log("Generating app build for:", appName, rendererContent)
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

	const rendererContent = `import "./index.css"
		import { createApp } from "vue"
		import { createPinia } from "pinia"
		import "./setupFrappeUIResource"
		import app_router from "@/router/app_router"
		import AppRenderer from "./AppRenderer.vue"
		import { resourcesPlugin } from "frappe-ui"

		${frappeUIImports}
		${studioImports}

		const app = createApp(AppRenderer)
		const pinia = createPinia()

		app.use(app_router)
		app.use(pinia)
		app.use(resourcesPlugin)
		app.mount("#app")
	`
	return rendererContent
}
