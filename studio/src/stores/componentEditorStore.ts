import { defineStore } from "pinia"
import { ref } from "vue"
import { dialog } from "frappe-ui"
import { studioComponents } from "@/data/studioComponents"
import { confirm } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"
import { getBlockObjectCopy, getBlockInstance, getComponentBlock } from "@/utils/serializer"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { toast } from "frappe-ui"
import type { StudioComponent, ComponentInput } from "@/types/Studio/StudioComponent"
import useComponentStore from "@/stores/componentStore"
import useStudioStore from "./studioStore"

const useComponentEditorStore = defineStore("componentEditorStore", () => {
	const selectedComponent = ref<string | null>(null)
	const studioComponentBlock = ref<Block | null>(null)
	const componentInputs = ref<ComponentInput[]>([])
	const componentStore = useComponentStore()

	async function createComponent(componentName: string, block?: Block | null) {
		const component: any = { component_name: componentName }
		if (block) {
			component.block = getBlockObjectCopy(block)
			if (component.block?.parentSlotName) {
				// remove parentSlotName from the top-level block of the component
				delete component.block.parentSlotName
			}
		}

		return studioComponents.insert.submit(component, {
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
		})
	}

	function promptNewComponent(options: {
		block?: Block | null
		onCreated: (component: StudioComponent) => void
	}) {
		dialog.prompt({
			title: "Create Component",
			confirmLabel: "Create",
			fields: [{ name: "componentName", label: "Component Name", required: true }],
			onConfirm: async ({ values }: { values: Record<string, any> }) => {
				const component = await createComponent(values.componentName, options.block)
				if (component) options.onCreated(component)
			},
		})
	}

	function saveComponent(block: Block, componentName: string) {
		const payload: any = {
			name: componentName,
			block: getBlockObjectCopy(block),
		}

		payload.inputs = componentInputs.value.map((input) => ({
			input_name: input.input_name,
			type: input.type,
			description: input.description || "",
			default: input.default || "",
			required: 0,
			options: input.options,
		}))

		studioComponents.setValue.submit(payload, {
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
		})
	}

	async function editComponent(componentId: string) {
		const componentBlock = await componentStore.getComponent(componentId)
		const componentDoc = componentStore.getComponentDoc(componentId)
		const block = componentBlock || getBlockInstance(getBlockTemplate("empty-component"))
		studioComponentBlock.value = getComponentBlock(componentId, true)

		// Load existing inputs from the component doc
		if (componentDoc && componentDoc.inputs) {
			componentInputs.value = componentDoc.inputs.map((input: any) => ({
				input_name: input.input_name,
				type: input.type,
				description: input.description,
				default: input.default,
				options: input.options,
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
		if (isComponentUsed(component.component_id)) {
			toast.error("Component is used in this page. You cannot delete it.")
		} else {
			const confirmed = await confirm(
				`Are you sure you want to delete the component '${component.component_name}'?`,
			)
			if (confirmed) {
				const store = useStudioStore()
				studioComponents.runDocMethod
					.submit({
						method: "delete_component",
						name: component.component_id,
						studio_app: store.activeApp?.name,
					})
					.then(() => {
						toast.success(`Component '${component.component_name}' deleted successfully`)
						studioComponents.reload()
						componentStore.removeCachedComponent(component.component_id)
					})
					.catch(() => {
						toast.error(`Failed to delete component '${component.component_name}'`)
					})
			}
		}
	}

	function isComponentUsed(componentId: string): Boolean {
		const checkComponent = (block: Block) => {
			if (block.isStudioComponent && block.componentName === componentId) {
				return true
			}
			if (block.children) {
				for (const child of block.children) {
					if (checkComponent(child)) {
						return true
					}
				}
			}
			return false
		}
		const canvasStore = useCanvasStore()
		for (const block of canvasStore.activeCanvas?.getRootBlock()?.children || []) {
			if (checkComponent(block)) {
				return true
			}
		}
		return false
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
		promptNewComponent,
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
