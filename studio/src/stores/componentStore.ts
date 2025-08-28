import { defineStore } from "pinia"
import { markRaw, reactive } from "vue"
import { createDocumentResource } from "frappe-ui"
import Block from "@/utils/block"
import type { StudioComponent } from "@/types/Studio/StudioComponent"
import { getBlockInstance } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"
import type { ComponentProps } from "@/types"

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
		if (!componentMap.has(componentName)) {
			fetchingComponent.add(componentName);

			try {
				const componentDoc = await fetchComponent(componentName);
				cacheComponent(componentDoc)
			} catch {
				const missingComponentDoc = {
					name: componentName,
					component_id: componentName,
					component_name: componentName,
					blocks: JSON.stringify(getBlockTemplate("missing-component")),
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
		if (componentDoc.blocks) {
			componentMap.set(componentDoc.component_id, markRaw(getBlockInstance(componentDoc.blocks)))
		}
	}

	function removeCachedComponent(componentName: string) {
		componentMap.delete(componentName)
		componentDocMap.delete(componentName)
	}

	function getStudioComponentProps(componentName: string): ComponentProps {
		const componentDoc = componentDocMap.get(componentName)
		if (!componentDoc || !componentDoc.inputs) return {}

		const props: ComponentProps = {}
		componentDoc.inputs.forEach(input => {
			props[input.input_name] = {
				type: input.type,
				default: input.default || undefined,
				inputType: input.type,
				required: !!input.required,
				options: input.type === "Select" && Array.isArray(input.default) ? input.default.map((opt: string) => ({ value: opt, label: opt })) : undefined
			}
		})
		return props
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
		getStudioComponentProps,
	}
})

export default useComponentStore
