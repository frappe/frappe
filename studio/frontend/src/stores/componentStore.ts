import { defineStore } from "pinia"
import { markRaw, reactive, shallowReactive, type Component } from "vue"
import { createDocumentResource } from "frappe-ui"
import Block from "@/utils/block"
import type { StudioComponent, StudioComponentInput } from "@/types/Studio/StudioComponent"
import { compileComponentScript } from "@/browserRuntime/appRuntime"
import {
	hasBuiltComponentScript,
	loadBuiltComponentScript,
	onComponentScriptHotUpdate,
} from "@/data/studioComponentScripts"
import {
	createComponentHost,
	getInputsFromProps,
	validateComponentScript,
	type ComponentScript,
} from "@/utils/componentScript"
import { isObjectEmpty } from "@/utils/helpers"
import { getBlockInstance, getBlockObjectCopy } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"

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
		if (componentDoc) setComponentScript(componentDoc, () => validateComponentScript(module.default))
	})

	async function fetchComponent(componentName: string) {
		const componentDoc = await createDocumentResource({
			doctype: "Studio Component",
			name: componentName,
			auto: true,
		})
		await componentDoc.get.promise
		return componentDoc.doc as StudioComponent
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
					block: JSON.stringify(getBlockTemplate("missing-component")),
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
	// compiles the `script` field in the browser.
	async function loadComponentScript(componentDoc: StudioComponent) {
		const componentId = componentDoc.component_id
		const load = (latestScriptLoads.get(componentId) ?? 0) + 1
		latestScriptLoads.set(componentId, load)
		let getScript: () => ComponentScript | null
		try {
			const module = await loadScriptModule(componentDoc)
			getScript = () => (module ? validateComponentScript(module.default) : null)
		} catch (error) {
			getScript = () => {
				throw error
			}
		}
		if (latestScriptLoads.get(componentId) === load) setComponentScript(componentDoc, getScript)
	}

	async function loadScriptModule(componentDoc: StudioComponent): Promise<Record<string, any> | null> {
		if (hasBuiltComponentScript(componentDoc.component_id)) {
			return loadBuiltComponentScript(componentDoc.component_id)
		}
		if (!componentDoc.script?.trim()) return null
		return compileComponentScript(componentDoc)
	}

	// A script that fails leaves the component as it was, or with its saved inputs when it is
	// new here, so the page still renders.
	function setComponentScript(componentDoc: StudioComponent, getScript: () => ComponentScript | null) {
		const componentId = componentDoc.component_id
		let script: ComponentScript | null = null
		try {
			script = getScript()
			componentScriptErrors.delete(componentId)
		} catch (error) {
			reportScriptError(componentId, error)
			if (componentHosts.has(componentId)) return
		}
		const source = script ?? (componentDoc.inputs || []).map((input) => input.input_name).join()
		if (componentHosts.get(componentId)?.source === source) return
		const host = createComponentHost(componentDoc, script, (error) => reportScriptError(componentId, error))
		componentHosts.set(componentId, { host, source })
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
	function getComponentInputs(componentName: string): StudioComponentInput[] {
		const script = getComponentScript(componentName)
		if (script) return getInputsFromProps(script.props)
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
		// The component emits the events its script declares. Every other event is a DOM event of its root.
		const emits = getComponentEmits(studioComponent.componentName)
		const componentEvents = Object.fromEntries(
			Object.entries(studioComponent.componentEvents || {}).filter(([name]) => !isEmittedEvent(name, emits)),
		)

		if (!isObjectEmpty(baseStyles)) blockOptions.baseStyles = { ...blockOptions.baseStyles, ...baseStyles }
		if (!isObjectEmpty(mobileStyles))
			blockOptions.mobileStyles = { ...blockOptions.mobileStyles, ...mobileStyles }
		if (!isObjectEmpty(tabletStyles))
			blockOptions.tabletStyles = { ...blockOptions.tabletStyles, ...tabletStyles }
		if (visibilityCondition) blockOptions.visibilityCondition = visibilityCondition
		if (classes?.length) blockOptions.classes = [...(blockOptions.classes || []), ...classes]

		if (!isObjectEmpty(componentEvents)) {
			blockOptions.componentEvents = {...(blockOptions.componentEvents || []), ...componentEvents}
		}

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
		getComponentInputs,
		getComponentEmits,
		loadComponent,
		setComponents,
		reloadComponent,
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
