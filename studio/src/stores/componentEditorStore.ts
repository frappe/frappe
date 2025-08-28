import { defineStore } from "pinia"
import { ref } from "vue"
import { studioComponents } from "@/data/studioComponents"
import { getBlockObject, getBlockInstance, confirm, getComponentBlock } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { toast } from "vue-sonner"
import type { StudioComponent, ComponentInput } from "@/types/Studio/StudioComponent"
import { useComponentStore } from "@/stores/componentStore"

const useComponentEditorStore = defineStore("componentEditorStore", () => {
	const selectedComponent = ref<string | null>(null)
	const studioComponentBlock = ref<Block | null>(null)
	const componentInputs = ref<ComponentInput[]>([])
	const componentStore = useComponentStore()

	async function createComponent(componentName: string, blocks?: Block | null) {
		const component: any = { component_name: componentName }
		if (blocks) {
			component.blocks = getBlockObject(blocks)
		}

		return studioComponents.insert.submit(
			component,
			{
				onSuccess(data: any) {
					componentStore.cacheComponent(data)
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
		const payload: any = {
			name: componentName,
			blocks: getBlockObject(blocks),
		}

		payload.inputs = componentInputs.value.map(input => ({
			input_name: input.input_name,
			type: input.type,
			description: input.description || "",
			default: input.default || "",
			required: 0,
			options: input.options,
		}))

		studioComponents.setValue.submit(
			payload,
			{
				onSuccess(data: StudioComponent) {
					componentStore.cacheComponent(data)
					resetStudioComponent()
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
		const componentDoc = componentStore.getComponentDoc(componentId)
		const componentBlock = await componentStore.getComponent(componentId)
		const block = componentBlock || getBlockInstance(getBlockTemplate("empty-component"))
		studioComponentBlock.value = getComponentBlock(componentId, true)

		// Load existing inputs from the component doc
		if (componentDoc && componentDoc.inputs) {
			componentInputs.value = componentDoc.inputs.map((input: any) => ({
				input_name: input.input_name,
				type: input.type,
				description: input.description,
				default: input.default
			}))
		} else {
			componentInputs.value = []
		}

		const canvasStore = useCanvasStore()
		canvasStore.editOnCanvas(
			block,
			(editedBlock) => saveComponent(editedBlock, componentDoc.component_id),
			"Save Component",
			componentDoc.component_name,
			componentDoc.component_id,
			"component",
			() => resetStudioComponent(),
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
					componentStore.removeCachedComponent(component.component_id)
				})
				.catch(() => {
					toast.error(`Failed to delete component '${component.component_name}'`)
				})
		}
	}

	function resetStudioComponent() {
		studioComponentBlock.value = null
	}

	// component inputs
	function addComponentInput(input: ComponentInput) {
		componentInputs.value.push(input)
	}

	function updateComponentInput(index: number, input: ComponentInput) {
		if (index >= 0 && index < componentInputs.value.length) {
			componentInputs.value[index] = input
		}
	}

	function removeComponentInput(index: number) {
		if (index >= 0 && index < componentInputs.value.length) {
			componentInputs.value.splice(index, 1)
		}
	}

	function clearComponentInputs() {
		componentInputs.value = []
	}

	return {
		selectedComponent,
		studioComponentBlock,
		componentInputs,
		createComponent,
		editComponent,
		deleteComponent,
		// inputs
		addComponentInput,
		updateComponentInput,
		removeComponentInput,
		clearComponentInputs,
	}
})

export default useComponentEditorStore