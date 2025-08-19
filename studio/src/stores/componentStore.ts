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
	const selectedComponent = ref<StudioComponent | null>(null)
	const { getComponent, cacheComponent, removeCachedComponent } = useStudioComponents()

	async function createComponent(componentName: string) {
		return studioComponents.insert.submit(
			{
				component_name: componentName,
			},
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

	async function editComponent(component: StudioComponent) {
		const componentBlocks = await getComponent(component.component_id)
		const blocks = componentBlocks || getBlockInstance(getBlockTemplate("empty-component"))
		const canvasStore = useCanvasStore()
		canvasStore.editOnCanvas(
			blocks,
			(editedBlock) => saveComponent(editedBlock, component.component_id),
			"Save Component",
			component.component_name,
			component.component_id,
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

	return {
		selectedComponent,
		createComponent,
		editComponent,
		deleteComponent,
	}
})

export default useComponentStore
