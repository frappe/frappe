import { defineStore } from "pinia"
import { markRaw, reactive } from "vue"
import { createDocumentResource } from "frappe-ui"
import Block from "@/utils/block"
import type { StudioComponent } from "@/types/Studio/StudioComponent"
import { getBlockInstance } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"

export const useComponentStore = defineStore("componentStore", () => {
	const componentMap = reactive<Map<string, Block>>(new Map())
	const componentDocMap = reactive<Map<string, StudioComponent>>(new Map())
	const fetchingComponent = reactive<Set<string>>(new Set())

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
				cacheComponent(componentDoc)
			} catch {
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

	function cacheComponent(componentDoc: StudioComponent) {
		componentDocMap.set(componentDoc.component_id, componentDoc)
		if (componentDoc.block) {
			componentMap.set(componentDoc.component_id, markRaw(getBlockInstance(componentDoc.block)))
		}
	}

	function removeCachedComponent(componentName: string) {
		componentMap.delete(componentName)
		componentDocMap.delete(componentName)
	}

	return {
		componentMap,
		componentDocMap,
		loadComponent,
		getComponent,
		getComponentDoc,
		getComponentName,
		cacheComponent,
		removeCachedComponent,
	}
})

export default useComponentStore
