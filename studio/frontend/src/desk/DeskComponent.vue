<template>
	<FrappeUIProvider>
		<StudioComponentRenderer
			v-if="block"
			:studioComponent="block"
			:evaluationContext="{}"
			:listeners="{}"
		/>
		<p v-else-if="error" class="p-3 text-sm text-ink-gray-5">{{ error }}</p>
	</FrappeUIProvider>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { createResource, FrappeUIProvider } from "frappe-ui"
import StudioComponentRenderer from "@/components/StudioComponentRenderer.vue"
import useComponentStore from "@/stores/componentStore"
import Block from "@/utils/block"
import type { StudioComponent, StudioComponentInput } from "@/types/Studio/StudioComponent"

const props = defineProps<{
	/** The id of a global component. */
	component?: string
	/** The name of a workspace. The island draws the workspace's root component. */
	workspace?: string
	props?: Record<string, any>
}>()
const emit = defineEmits<{
	/** The component is ready to render. A host builds its prop form from `props`. */
	load: [definition: { component_name: string; props: StudioComponentInput[] }]
}>()

const componentStore = useComponentStore()
const componentResource = createResource({ url: "frappe.studio.desk.get_desk_component", method: "GET" })
const workspaceResource = createResource({
	url: "frappe.desk.workspace_component.get_workspace_component",
	method: "GET",
})
// what the host asked for, and the id of the component that it loaded
const source = computed(() => props.workspace || props.component || "")
const loaded = ref<{ source: string; componentId: string } | null>(null)
const error = ref("")

const block = computed(() =>
	loaded.value?.source === source.value
		? new Block({
				componentName: loaded.value.componentId,
				isStudioComponent: true,
				componentProps: props.props || {},
			})
		: null,
)

watch(source, loadComponent, { immediate: true })

/** Each reply holds the component to draw first, and then the components that its blocks use. */
function fetchComponents(): Promise<StudioComponent[]> {
	if (props.workspace) return workspaceResource.fetch({ workspace: props.workspace })
	return componentResource.fetch({ component_id: props.component })
}

async function loadComponent(name: string) {
	error.value = ""
	let components: StudioComponent[]
	try {
		components = await fetchComponents()
		await componentStore.setComponents(components)
	} catch (failure: any) {
		console.error(`${name} did not load`, failure)
		const isMissing = failure?.exc_type === "DoesNotExistError"
		error.value = `Component ${name} ${isMissing ? "was not found" : "did not load"}.`
		return
	}
	const componentId = components[0].component_id
	loaded.value = { source: name, componentId }
	emit("load", {
		component_name: componentStore.getComponentName(componentId),
		props: componentStore.getComponentProps(componentId),
	})
}
</script>
