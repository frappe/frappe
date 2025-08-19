import { markRaw, reactive } from "vue"
import { createDocumentResource } from "frappe-ui"
import Block from "@/utils/block"
import type { StudioComponent } from "@/types/Studio/StudioComponent"
import { getBlockInstance } from "./helpers"
import getBlockTemplate from "./blockTemplate"

export function useStudioComponents() {
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

	async function getComponent(componentName: string) {
		await loadComponent(componentName)
		return componentMap.get(componentName)
	}

	function getComponentDoc(componentName: string) {
		return componentDocMap.get(componentName) as StudioComponent
	}

	async function loadComponent(componentName: string) {
		if (!componentMap.has(componentName) && !fetchingComponent.has(componentName)) {
			fetchingComponent.add(componentName);
			return fetchComponent(componentName)
				.then((componentDoc) => {
					cacheComponent(componentDoc);
				})
				.catch(() => {
					const missingComponentDoc = {
						component_id: componentName,
						component_name: componentName,
						blocks: JSON.stringify(getBlockTemplate("missing-component")),
						creation: "",
						modified: "",
					};
					cacheComponent(missingComponentDoc)
				})
				.finally(() => {
					fetchingComponent.delete(componentName);
				});
		}
	}

	function cacheComponent(componentDoc: StudioComponent) {
		componentDocMap.set(componentDoc.component_id, componentDoc);
		componentMap.set(componentDoc.component_id, markRaw(getBlockInstance(componentDoc.blocks)));
	}

	function removeCachedComponent(componentName: string) {
		componentMap.delete(componentName)
		componentDocMap.delete(componentName)
	}

	return {
		componentMap,
		getComponent,
		cacheComponent,
		removeCachedComponent,
	}
}