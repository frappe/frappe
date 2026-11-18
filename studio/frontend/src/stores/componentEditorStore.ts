import { defineStore } from "pinia"
import { computed, ref } from "vue"
import { dialog } from "frappe-ui"
import { studioComponents } from "@/data/studioComponents"
import useStudioStore from "@/stores/studioStore"
import { confirm } from "@/utils/helpers"
import getBlockTemplate from "@/utils/blockTemplate"
import { getBlockObjectCopy, getBlockInstance, getComponentBlock } from "@/utils/serializer"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { toast } from "frappe-ui"
import type { StudioComponent, StudioComponentInput } from "@/types/Studio/StudioComponent"
import { setScriptProp } from "@/utils/componentScriptProps"
import useComponentStore from "@/stores/componentStore"

const useComponentEditorStore = defineStore("componentEditorStore", () => {
	const selectedComponent = ref<string | null>(null)
	const studioComponentBlock = ref<Block | null>(null)
	// The pages and components that use the component being edited. One that the user cannot read is null.
	const componentUsages = ref<(string | null)[]>([])
	const componentStore = useComponentStore()
	/** The props that the script of the open component declares, or its saved inputs. */
	const declaredProps = computed<StudioComponentInput[]>(() =>
		componentStore.getComponentProps(useCanvasStore().fragmentData.fragmentId ?? ""),
	)

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
			const { name } = componentStore.getComponentDoc(componentId)
			const data = await studioComponents.setValue.submit({ ...payload, name })
			// before a message from the server, which shows next and must stay on top
			toast.success("Component saved")
			await componentStore.cacheComponent(data)
			studioComponents.reload()
			resetStudioComponent()
		} catch (error: any) {
			toast.error("Failed to save component", { description: error?.messages?.join(", ") })
			// the editor keeps the component open and its changes unsaved
			throw error
		}
	}

	/** Make the component global, or a component of the open app. Its docname changes, and its id stays. */
	async function setGlobal(componentId: string, isGlobal: boolean) {
		const componentDoc = componentStore.getComponentDoc(componentId)
		try {
			const { message } = await studioComponents.runDocMethod.submit({
				name: componentDoc.name,
				method: "set_app",
				studio_app: isGlobal ? null : useStudioStore().activeApp?.name,
			})
			toast.success(
				isGlobal
					? `${componentDoc.component_name} is now a global component`
					: `${componentDoc.component_name} is now a component of this app`,
				{
					description: message?.is_global_kept
						? "Another app uses the global component, so it was kept."
						: undefined,
				},
			)
			await componentStore.reloadComponent(componentId)
			studioComponents.reload()
		} catch (error: any) {
			toast.error("Failed to change the component", { description: error?.messages?.join(", ") })
		}
	}

	async function renameComponent(componentId: string, componentName: string) {
		const { name } = componentStore.getComponentDoc(componentId)
		try {
			const data = await studioComponents.setValue.submit({ name, component_name: componentName })
			await componentStore.cacheComponent(data)
			studioComponents.reload()
			useCanvasStore().fragmentData.fragmentName = componentName
		} catch (error: any) {
			toast.error("Failed to rename the component", { description: error?.messages?.join(", ") })
		}
	}

	async function loadComponentUsages(componentId: string) {
		componentUsages.value = []
		const { name } = componentStore.getComponentDoc(componentId)
		const { message } = await studioComponents.runDocMethod.submit({ name, method: "get_usages" })
		componentUsages.value = message || []
	}

	/** Open a component on top of what is open, for a component inside it. `isReplacing` closes
	 * what is open first, for a component that the user picks from a list. */
	async function editComponent(componentId: string, isReplacing = false) {
		const canvasStore = useCanvasStore()
		if (isReplacing) {
			if (canvasStore.fragmentData.fragmentId === componentId) return
			await canvasStore.exitAllFragments()
			// the user kept the unsaved changes of what is open
			if (canvasStore.fragmentStack.length) return
		}
		const componentBlock = await componentStore.getComponent(componentId)
		const componentDoc = componentStore.getComponentDoc(componentId)
		const block = componentBlock || getBlockInstance(getBlockTemplate("empty-component"))
		studioComponentBlock.value = getComponentBlock(componentId, true)

		loadComponentUsages(componentId)

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

	/** Whether the component was deleted. */
	async function deleteComponent(component: Pick<StudioComponent, "name" | "component_id" | "component_name">) {
		if (!(await confirm(`Are you sure you want to delete the component '${component.component_name}'?`))) {
			return false
		}
		try {
			await studioComponents.delete.submit(component.name)
			toast.success(`Component '${component.component_name}' deleted`)
			studioComponents.reload()
			componentStore.removeCachedComponent(component.component_id)
			return true
		} catch (error: any) {
			toast.error(`Failed to delete component '${component.component_name}'`, {
				description: error?.messages?.join(", "),
			})
			return false
		}
	}

	function resetStudioComponent() {
		studioComponentBlock.value = null
	}

	/**
	 * Add, change or remove one prop in the component's script, and save the script.
	 * Pass only `prop` to add a prop, and only `previous` to remove one.
	 */
	async function saveComponentProp(
		componentId: string,
		previous: StudioComponentInput | null,
		prop: StudioComponentInput | null,
	) {
		const componentDoc = componentStore.getComponentDoc(componentId)
		try {
			const script = setScriptProp(componentDoc.script || "", previous, prop)
			const data = await studioComponents.setValue.submit({ name: componentDoc.name, script })
			await componentStore.cacheComponent(data)
			toast.success(prop ? "Prop saved" : "Prop removed")
			return true
		} catch (error: any) {
			toast.error("Failed to save the prop", { description: error?.messages?.join(", ") || error?.message })
			return false
		}
	}

	return {
		selectedComponent,
		studioComponentBlock,
		declaredProps,
		createComponent,
		promptNewComponent,
		editComponent,
		deleteComponent,
		setGlobal,
		renameComponent,
		componentUsages,
		saveComponentProp,
	}
})

export default useComponentEditorStore
