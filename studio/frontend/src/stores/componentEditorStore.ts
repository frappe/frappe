import { defineStore } from "pinia"
import { ref } from "vue"
import { dialog } from "frappe-ui"
import { studioComponents } from "@/data/studioComponents"
import useStudioStore from "@/stores/studioStore"
import { confirm } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"
import { getBlockObjectCopy, getBlockInstance, getComponentBlock } from "@/utils/serializer"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { toast } from "frappe-ui"
import type { StudioComponent, StudioComponentInput, ComponentInput } from "@/types/Studio/StudioComponent"
import { setScriptProp } from "@/utils/componentScriptProps"
import useComponentStore from "@/stores/componentStore"

const useComponentEditorStore = defineStore("componentEditorStore", () => {
	const selectedComponent = ref<string | null>(null)
	const studioComponentBlock = ref<Block | null>(null)
	const componentInputs = ref<ComponentInput[]>([])
	// whether the component being edited is available in all apps
	const isGlobal = ref(false)
	const componentStore = useComponentStore()

	async function createComponent(componentName: string, block?: Block | null, isGlobal = false) {
		const component: any = { component_name: componentName }
		if (!isGlobal) component.studio_app = useStudioStore().activeApp?.name
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
				toast.success("Component created")
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
			fields: [
				{ name: "componentName", label: "Component Name", required: true },
				{ name: "isGlobalComponent", label: "Global Component", type: "checkbox" },
			],
			onConfirm: async ({ values }: { values: Record<string, any> }) => {
				const component = await createComponent(values.componentName, options.block, values.isGlobalComponent)
				if (component) options.onCreated(component)
			},
		})
	}

	async function saveComponent(block: Block, componentId: string) {
		const payload = { block: getBlockObjectCopy(block) }

		try {
			// the component's docname changes when it moves between the app and global
			const moved = await moveComponent(componentStore.getComponentDoc(componentId))
			const data = await studioComponents.setValue.submit({ ...payload, name: moved.name })
			// before a message from the server, which shows next and must stay on top
			toast.success("Component saved", {
				description: moved.is_global_kept
					? "Another app uses the global component, so it was kept."
					: undefined,
			})
			await componentStore.cacheComponent(data)
			studioComponents.reload()
			resetStudioComponent()
		} catch (error: any) {
			toast.error("Failed to save component", { description: error?.messages?.join(", ") })
		}
	}

	/** Apply the "Global Component" choice: make the component global, or a component of the open app. */
	async function moveComponent(componentDoc: StudioComponent) {
		if (isGlobal.value === !componentDoc.studio_app) return { name: componentDoc.name }
		const { message } = await studioComponents.runDocMethod.submit({
			name: componentDoc.name,
			method: "set_app",
			studio_app: isGlobal.value ? null : useStudioStore().activeApp?.name,
		})
		return message as { name: string; is_global_kept?: boolean }
	}

	async function editComponent(componentId: string) {
		const componentBlock = await componentStore.getComponent(componentId)
		const componentDoc = componentStore.getComponentDoc(componentId)
		const block = componentBlock || getBlockInstance(getBlockTemplate("empty-component"))
		studioComponentBlock.value = getComponentBlock(componentId, true)

		setComponentInputs(componentId)
		isGlobal.value = !componentDoc.studio_app

		const canvasStore = useCanvasStore()
		canvasStore.editOnCanvas(
			block,
			(editedBlock) => saveComponent(editedBlock, componentId),
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
				studioComponents.delete
					.submit(component.name)
					.then(() => {
						toast.success(`Component '${component.component_name}' deleted`)
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

	/** Load the saved inputs, or the props that the component's script declares. */
	function setComponentInputs(componentId: string) {
		componentInputs.value = componentStore.getComponentInputs(componentId).map((input) => ({
			input_name: input.input_name,
			type: input.type,
			description: input.description,
			default: input.default,
			options: input.options,
			required: input.required,
		}))
	}

	/**
	 * Add, change or remove one prop in the component's script, and save the script.
	 * Pass only `input` to add a prop, and only `previous` to remove one.
	 */
	async function saveComponentProp(
		componentId: string,
		previous: StudioComponentInput | null,
		input: StudioComponentInput | null,
	) {
		const componentDoc = componentStore.getComponentDoc(componentId)
		try {
			const script = setScriptProp(componentDoc.script || "", previous, input)
			const data = await studioComponents.setValue.submit({ name: componentDoc.name, script })
			await componentStore.cacheComponent(data)
			setComponentInputs(componentId)
			return true
		} catch (error: any) {
			toast.error("Failed to save the prop", { description: error?.messages?.join(", ") || error?.message })
			return false
		}
	}

	return {
		selectedComponent,
		studioComponentBlock,
		componentInputs,
		createComponent,
		promptNewComponent,
		editComponent,
		deleteComponent,
		isGlobal,
		setComponentInputs,
		saveComponentProp,
	}
})

export default useComponentEditorStore
