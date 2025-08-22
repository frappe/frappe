import { defineStore } from "pinia"
import { ref } from "vue"
import { studioComponents } from "@/data/studioComponents"
import { getBlockObject, getBlockInstance, confirm } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { toast } from "vue-sonner"
import type { StudioComponent } from "@/types/Studio/StudioComponent"
import { useStudioComponents } from "@/utils/useStudioComponents"

const useComponentStore = defineStore("componentStore", () => {
	const selectedComponent = ref<string | null>(null)
	const { getComponent, getComponentDoc, cacheComponent, removeCachedComponent } = useStudioComponents()

	async function createComponent(componentName: string, blocks?: Block | null) {
		const component: any = { component_name: componentName }
		if (blocks) {
			component.blocks = getBlockObject(blocks)
		}

		return studioComponents.insert.submit(
			component,
			{
				onSuccess(data: any) {
					cacheComponent(data)
					toast.success("Component created successfully")
					return data
				},
				onError(error: any) {
					toast.error("Failed to create component", {
						description: error?.messages?.join(", "),
					})
				},
			},
		)
	}

	function saveComponent(blocks: Block, componentName: string) {
		studioComponents.setValue.submit(
			{
				name: componentName,
				blocks: getBlockObject(blocks),
			},
			{
				onSuccess(data: StudioComponent) {
					cacheComponent(data)
					toast.success("Component saved successfully")
				},
				onError(error: any) {
					toast.error("Failed to save component", {
						description: error.messages.join(", "),
					})
				},
			},
		)
	}

	async function editComponent(componentId: string) {
		const componentBlocks = await getComponent(componentId)
		const componentDoc = getComponentDoc(componentId)
		const blocks = componentBlocks || getBlockInstance(getBlockTemplate("empty-component"))
		const canvasStore = useCanvasStore()
		canvasStore.editOnCanvas(
			blocks,
			(editedBlock) => saveComponent(editedBlock, componentDoc.component_id),
			"Save Component",
			componentDoc.component_name,
			componentDoc.component_id,
		)
	}

	async function deleteComponent(component: StudioComponent) {
		const confirmed = await confirm(
			`Are you sure you want to delete the component '${component.component_name}'?`,
		)
		if (confirmed) {
			studioComponents.delete
				.submit(component.component_id)
				.then(() => {
					toast.success(`Component '${component.component_name}' deleted successfully`)
					removeCachedComponent(component.component_id)
				})
				.catch(() => {
					toast.error(`Failed to delete component '${component.component_name}'`)
				})
		}
	}

	function getComponentName(componentId: string) {
		const componentDoc = getComponentDoc(componentId)
		if (!componentDoc) {
			return componentId
		}
		return componentDoc.component_name
	}

	return {
		selectedComponent,
		createComponent,
		editComponent,
		deleteComponent,
		getComponentName,
	}
})

export default useComponentStore
