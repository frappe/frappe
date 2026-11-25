import { defineStore } from "pinia"
import { markRaw, reactive, shallowReactive, type Component } from "vue"
import { call } from "frappe-ui"
import Block from "@/runtime/utils/block"
import type { StudioComponent, StudioComponentInput } from "@/types/Studio/StudioComponent"
import { compileComponentScript } from "@/runtime/browserRuntime/appRuntime"
import {
	hasBuiltComponentScript,
	loadBuiltComponentScript,
	onComponentScriptHotUpdate,
} from "@/runtime/data/studioComponentScripts"
import {
	createComponentHost,
	getEditorProps,
	validateComponentScript,
	type ComponentScript,
} from "@/runtime/utils/componentScript"
import { isObjectEmpty } from "@/runtime/utils/helpers"
import { getBlockInstance, getBlockObjectCopy } from "@/runtime/utils/serializer"
import type { BlockOptions, BlockStyleMap } from "@/types"

const MISSING_COMPONENT_BLOCK: BlockOptions = {
	componentName: "HTML",
	originalElement: "__raw_html__",
	innerHTML: `<div style="color:#E86C13;background:#F8F8F8;display:flex;width:300px;height:150px;align-items:center;font-size:16px;justify-content:center"><p>Component Missing</p></div>`,
	baseStyles: {
		height: "fit-content",
		width: "fit-content",
	} as BlockStyleMap,
}

const useComponentStore = defineStore("componentStore", () => {
	const componentMap = reactive<Map<string, Block>>(new Map())
	const componentDocMap = reactive<Map<string, StudioComponent>>(new Map())
	const fetchingComponent = reactive<Set<string>>(new Set())
	// A new host remounts every instance of its component, so a host stays until its source changes.
	// The source is the script, or the input names of a component without one.
	const componentHosts = shallowReactive<Map<string, { host: Component; source: ComponentScript | string }>>(
		new Map(),
	)
	const componentScriptErrors = reactive<Map<string, string>>(new Map())
	const latestScriptLoads = new Map<string, number>()

	onComponentScriptHotUpdate((componentId, module) => {
		const componentDoc = componentDocMap.get(componentId)
		if (componentDoc) loadComponentScript(componentDoc, async () => module)
	})

	// A block names a component by its id. The app decides which component that id means:
	// its own component, or else the global one.
	let studioApp: string | undefined

	function setStudioApp(appName: string) {
		if (appName === studioApp) return
		studioApp = appName
		for (const componentId of [...componentDocMap.keys()]) removeCachedComponent(componentId)
	}

	function fetchComponent(componentId: string): Promise<StudioComponent> {
		return call("frappe.studio.api.get_studio_component", {
			component_id: componentId,
			studio_app: studioApp ?? window.app_name,
		})
	}

	/** Reload a component that changed on the server, given its docname: `<app>/<id>`, or `<id>`. */
	async function reloadComponentDoc(name: string) {
		const separator = name.lastIndexOf("/")
		const owner = separator === -1 ? null : name.slice(0, separator)
		if (owner && owner !== (studioApp ?? window.app_name)) return
		await reloadComponent(name.slice(separator + 1))
	}

	async function getComponent(componentName: string): Promise<Block | undefined> {
		await loadComponent(componentName)
		return componentMap.get(componentName)
	}

	function getComponentDoc(componentName: string) {
		return componentDocMap.get(componentName) as StudioComponent
	}

	function getComponentName(componentId: string) {
		const componentDoc = getComponentDoc(componentId)
		if (!componentDoc) {
			return componentId
		}
		return componentDoc.component_name
	}

	async function loadComponent(componentName: string) {
		if (!componentMap.has(componentName) && !fetchingComponent.has(componentName)) {
			fetchingComponent.add(componentName);

			try {
				const componentDoc = await fetchComponent(componentName);
				await cacheComponent(componentDoc)
			} catch {
				// the page payload may have cached it while this fetch was failing
				if (componentMap.has(componentName)) return
				const missingComponentDoc = {
					name: componentName,
					component_id: componentName,
					component_name: componentName,
					block: JSON.stringify(MISSING_COMPONENT_BLOCK),
					creation: "",
					modified: "",
				};
				cacheComponent(missingComponentDoc)
			} finally {
				fetchingComponent.delete(componentName)
			}
		}
	}

	/** Cache the components of a page. They are ready to mount when the promise resolves. */
	async function setComponents(componentDocs: StudioComponent[]) {
		// Prevent nested blocks from refetching components in this batch.
		for (const componentDoc of componentDocs) fetchingComponent.add(componentDoc.component_id)
		const cached = componentDocs.map((componentDoc) => cacheComponent(componentDoc))
		for (const componentDoc of componentDocs) fetchingComponent.delete(componentDoc.component_id)
		await Promise.all(cached)
	}

	async function reloadComponent(componentName: string) {
		try {
			await cacheComponent(await fetchComponent(componentName))
		} catch {
			removeCachedComponent(componentName)
		}
	}

	/** Cache the block tree now. The component can mount when its script has loaded. */
	function cacheComponent(componentDoc: StudioComponent): Promise<void> {
		componentDocMap.set(componentDoc.component_id, componentDoc)
		if (componentDoc.block) {
			componentMap.set(componentDoc.component_id, markRaw(getBlockInstance(componentDoc.block)))
		}
		return loadComponentScript(componentDoc)
	}

	function removeCachedComponent(componentName: string) {
		componentMap.delete(componentName)
		componentDocMap.delete(componentName)
		componentHosts.delete(componentName)
		componentScriptErrors.delete(componentName)
	}

	// SCRIPTS
	// An app build and the Vite dev server load the script from its file. A database app
	// compiles the `script` field in the browser. A hot update gives the module itself.
	async function loadComponentScript(
		componentDoc: StudioComponent,
		loadModule: () => Promise<Record<string, any> | null> = () => loadScriptModule(componentDoc),
	) {
		const componentId = componentDoc.component_id
		const load = (latestScriptLoads.get(componentId) ?? 0) + 1
		latestScriptLoads.set(componentId, load)
		let script: ComponentScript | null = null
		let failure: { error: unknown } | null = null
		try {
			const module = await loadModule()
			script = module ? validateComponentScript(module.default) : null
		} catch (error) {
			failure = { error }
		}
		if (latestScriptLoads.get(componentId) !== load) return

		if (failure) {
			reportScriptError(componentId, failure.error)
			// The component stays as it was. One that is new here renders with its saved inputs,
			// so the page still renders.
			if (componentHosts.has(componentId)) return
		} else {
			componentScriptErrors.delete(componentId)
		}
		const source = script ?? (componentDoc.inputs || []).map((input) => input.input_name).join()
		if (componentHosts.get(componentId)?.source === source) return
		const host = createComponentHost(componentDoc, script, (error) => reportScriptError(componentId, error))
		componentHosts.set(componentId, { host, source })
	}

	async function loadScriptModule(componentDoc: StudioComponent): Promise<Record<string, any> | null> {
		if (hasBuiltComponentScript(componentDoc.component_id)) {
			return loadBuiltComponentScript(componentDoc.component_id)
		}
		if (!componentDoc.script?.trim()) return null
		return compileComponentScript(componentDoc)
	}

	function reportScriptError(componentId: string, error: unknown) {
		console.error(`Error in the script of component ${componentId}`, error)
		componentScriptErrors.set(componentId, error instanceof Error ? error.message : String(error))
	}

	/** Load every cached component's script again, after the source the scripts load from changed. */
	async function reloadComponentScripts() {
		await Promise.all([...componentDocMap.values()].map((componentDoc) => loadComponentScript(componentDoc)))
	}

	function getComponentHost(componentName: string): Component | undefined {
		return componentHosts.get(componentName)?.host
	}

	/** Whether the component has a script, also one that failed to load. */
	function hasComponentScript(componentName: string): boolean {
		return (
			hasBuiltComponentScript(componentName) ||
			Boolean(componentDocMap.get(componentName)?.script?.trim()) ||
			Boolean(getComponentScript(componentName))
		)
	}

	function getComponentScript(componentName: string): ComponentScript | null {
		const source = componentHosts.get(componentName)?.source
		return typeof source === "object" ? source : null
	}

	/** The props of a scripted component, or the inputs saved on a component without a script. */
	function getComponentProps(componentName: string): StudioComponentInput[] {
		const script = getComponentScript(componentName)
		if (script) return getEditorProps(script.props)
		return componentDocMap.get(componentName)?.inputs || []
	}

	function getComponentEmits(componentName: string): string[] {
		const emits = getComponentScript(componentName)?.emits || []
		return Array.isArray(emits) ? emits : Object.keys(emits)
	}

	function getNewStudioComponentInstance(studioComponent: Block) {
		const component = componentMap.get(studioComponent.componentName)
		if (!component) {
			return
		}
		const blockOptions = getBlockObjectCopy(component)
		const { baseStyles, mobileStyles, tabletStyles, visibilityCondition, classes } = studioComponent
		if (!isObjectEmpty(baseStyles)) blockOptions.baseStyles = { ...blockOptions.baseStyles, ...baseStyles }
		if (!isObjectEmpty(mobileStyles))
			blockOptions.mobileStyles = { ...blockOptions.mobileStyles, ...mobileStyles }
		if (!isObjectEmpty(tabletStyles))
			blockOptions.tabletStyles = { ...blockOptions.tabletStyles, ...tabletStyles }
		if (visibilityCondition) blockOptions.visibilityCondition = visibilityCondition
		if (classes?.length) blockOptions.classes = [...(blockOptions.classes || []), ...classes]

		return new Block(blockOptions)
	}

	return {
		componentMap,
		componentDocMap,
		componentScriptErrors,
		reloadComponentScripts,
		getComponentHost,
		getComponentScript,
		hasComponentScript,
		getComponentProps,
		getComponentEmits,
		loadComponent,
		setComponents,
		reloadComponent,
		reloadComponentDoc,
		setStudioApp,
		getComponent,
		getComponentDoc,
		getComponentName,
		cacheComponent,
		removeCachedComponent,
		getNewStudioComponentInstance,
	}
})

/** Whether a Studio Component emits this event itself: one its script declares, or a two-way binding. */
export function isEmittedEvent(name: string, emits: string[]): boolean {
	return emits.includes(name) || name.startsWith("update:")
}

export default useComponentStore
