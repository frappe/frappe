import { call } from "frappe-ui"
import components from "@/data/components"

export async function generateAppBuild(appName: string) {
	if (!appName) return
	const components = await call("studio.api.get_app_components", { app_name: appName })

	const componentSources = findComponentSources(components)
	const rendererContent = getRendererContent(componentSources)
}

type ComponentSources = {
	frappeUIComponents: string[]
	studioComponents: string[]
}

function findComponentSources(appComponents: string[]): ComponentSources {
	const frappeUIComponents: string[] = []
	const studioComponents: string[] = []

	appComponents.forEach((component) => {
		if (components.isFrappeUIComponent(component)) {
			frappeUIComponents.push(component)
		} else {
			studioComponents.push(component)
		}
	})
	return {
		frappeUIComponents: frappeUIComponents,
		studioComponents: studioComponents,
	}
}

function getRendererContent(componentSources: ComponentSources) {
	const { frappeUIComponents, studioComponents } = componentSources
	const frappeUIImports = frappeUIComponents.length > 0
		? `import { ${frappeUIComponents.join(",\n ")} } from "frappe-ui";`
		: "";

	const studioImports = studioComponents.map(comp =>
		`import ${comp} from "@/components/AppLayout/${comp}.vue"`
	).join("\n")

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