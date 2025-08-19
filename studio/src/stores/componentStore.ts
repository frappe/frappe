import { defineStore } from "pinia"
import { ref, markRaw } from "vue"
import { studioComponents } from "@/data/studioComponents"
import { getBlockObject, getBlockInstance, confirm } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"
import useCanvasStore from "@/stores/canvasStore"
import { toast } from "vue-sonner"
import type { StudioComponent } from "@/types/Studio/StudioComponent"

const useComponentStore = defineStore("componentStore", () => {
	const selectedComponent = ref<StudioComponent | null>(null)

	async function createComponent(componentName: string) {
		return studioComponents.insert.submit(
			{
				component_name: componentName,
			},
			{
				onSuccess(data: any) {
					toast.success("Component created successfully")
					return data
				},
				onError(error: any) {
					toast.error("Failed to create component", {
						description: error.messages.join(", "),
					})
				},
			},
		)
	}

	function editComponent(component: StudioComponent) {
		const blocks = component.blocks?.length
			? markRaw(getBlockInstance(component.blocks))
			: getBlockInstance(getBlockTemplate("empty-component"))
		const canvasStore = useCanvasStore()
		canvasStore.editOnCanvas(
			blocks,
			(editedBlock) => {
				studioComponents.setValue.submit(
					{
						name: component.component_id,
						blocks: getBlockObject(editedBlock),
					},
					{
						onSuccess() {
							toast.success("Component saved successfully")
						},
						onError(error: any) {
							toast.error("Failed to save component", {
								description: error.messages.join(", "),
							})
						},
					},
				)
			},
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
