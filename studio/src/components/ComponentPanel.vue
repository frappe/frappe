<template>
	<div class="flex flex-col gap-2" ref="componentContainer">
		<div class="sticky top-[41px] z-50 mt-[-15px] flex w-full flex-col gap-3 bg-surface-base py-3">
			<!-- Component Filter -->
			<Input
				type="text"
				variant="outline"
				placeholder="Search component"
				v-model="componentFilter"
				@input="
					(value: string) => {
						componentFilter = value
					}
				"
			/>
			<OptionToggle
				:options="[{ label: 'Standard' }, { label: 'Custom' }]"
				:modelValue="activeTab"
				@update:modelValue="
					(tab) => (store.studioLayout.leftPanelComponentTab = tab as leftPanelComponentTabOptions)
				"
			/>
		</div>

		<template v-if="activeTab === 'Standard'">
			<EmptyState v-if="!componentList.length" message="No matching components" />
			<div v-else class="grid grid-cols-3 items-start gap-x-2 gap-y-4">
				<div v-for="component in componentList" :key="component.name" class="flex flex-col">
					<div
						class="user-component group flex cursor-grab flex-col items-center justify-center gap-3 text-ink-gray-6 transition-all duration-200 hover:scale-105"
						draggable="true"
						:data-component-name="component.name"
					>
						<div
							class="flex h-16 w-16 flex-col items-center justify-center rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-3 transition-all duration-200 group-hover:border-outline-gray-3 group-hover:bg-surface-gray-2 group-hover:shadow-sm"
						>
							<component :is="component.icon" class="h-6 w-6" />
						</div>
						<span class="wrap-normal w-full text-center text-xs">
							{{ component.title }}
						</span>
					</div>
				</div>
			</div>
		</template>

		<template v-else>
			<CollapsibleSection sectionName="Vue Components" v-if="customVueComponents.length" class="px-2">
				<div class="flex flex-col" ref="vueComponentListRef">
					<div
						v-for="component in customVueComponents"
						:key="component.component_name"
						:data-vue-component-name="component.component_name"
						class="user-component group/vue-component flex cursor-grab select-none items-center justify-between rounded p-1 hover:bg-surface-gray-1"
						:class="{
							'border border-outline-gray-4': store.selectedVueComponent === component.component_name,
						}"
						draggable="true"
						:data-component-name="component.component_name"
						:data-is-custom-vue-component="true"
					>
						<div class="flex items-center gap-2 text-ink-gray-7">
							<div
								class="flex h-6 w-6 items-center justify-center rounded bg-surface-green-1 text-ink-green-6"
							>
								<LucideCode class="h-3 w-3" />
							</div>
							<p class="text-sm">{{ component.component_name }}</p>
						</div>
						<div class="invisible group-hover/vue-component:visible has-[.active-item]:visible">
							<Dropdown :options="getVueComponentMenu(component)" trigger="click">
								<template v-slot="{ open }">
									<button
										class="flex cursor-pointer items-center rounded-sm p-1 text-ink-gray-6 hover:bg-surface-gray-4"
										:class="open ? 'active-item' : ''"
									>
										<FeatherIcon name="more-horizontal" class="h-3 w-3" />
									</button>
								</template>
							</Dropdown>
						</div>
					</div>
				</div>
			</CollapsibleSection>

			<CollapsibleSection sectionName="Studio Components" class="px-2">
				<EmptyState v-if="!componentList?.length" message="No components found" />
				<div v-else class="flex flex-col">
					<div
						v-for="component in componentList"
						:key="component.component_id"
						class="group/component user-component flex cursor-grab select-none items-center justify-between rounded p-1 hover:bg-surface-gray-1"
						:class="{
							'border border-outline-gray-4':
								componentEditorStore.selectedComponent === component.component_id,
						}"
						draggable="true"
						:data-component-name="component.component_id"
						:data-is-studio-component="true"
					>
						<div class="flex items-center gap-2 text-ink-gray-7">
							<div
								class="flex h-6 w-6 items-center justify-center rounded bg-surface-purple-1 text-ink-purple-7"
							>
								<LucideBox class="h-3 w-3" />
							</div>
							<p class="text-sm">
								{{ component.component_name }}
							</p>
						</div>
						<div class="invisible group-hover/component:visible has-[.active-item]:visible">
							<Dropdown :options="getComponentMenu(component)" trigger="click">
								<template v-slot="{ open }">
									<button
										class="flex cursor-pointer items-center rounded-sm p-1 text-ink-gray-6 hover:bg-surface-gray-4"
										:class="open ? 'active-item' : ''"
									>
										<FeatherIcon name="more-horizontal" class="h-3 w-3" />
									</button>
								</template>
							</Dropdown>
						</div>
					</div>
				</div>
				<Button icon-left="plus" class="mt-3" @click="createComponent">Create Component</Button>
			</CollapsibleSection>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from "vue"
import { useEventListener } from "@vueuse/core"
import { Dropdown, FeatherIcon } from "frappe-ui"
import OptionToggle from "@/components/OptionToggle.vue"
import Input from "@/components/Input.vue"
import EmptyState from "@/components/EmptyState.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"

import components from "@/data/components"
import { studioComponents } from "@/data/studioComponents"
import { deleteStudioFile } from "@/data/studioFiles"

import useCanvasStore from "@/stores/canvasStore"
import useStudioStore from "@/stores/studioStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import { confirm } from "@/utils/helpers"
import type { leftPanelComponentTabOptions } from "@/types"
import type { StudioComponent } from "@/types/Studio/StudioComponent"
import type { CustomVueComponentMeta } from "@/types/vue"
import LucideCode from "~icons/lucide/code"
import LucideBox from "~icons/lucide/box"

const canvasStore = useCanvasStore()
const store = useStudioStore()
const componentEditorStore = useComponentEditorStore()

const componentFilter = ref("")
const componentList = computed(() => {
	const isStandard = activeTab.value === "Standard"
	const allComponents = isStandard ? components.list : studioComponents.data

	// Apply search filter
	const filtered = componentFilter.value
		? allComponents?.filter((component: any) =>
				(isStandard ? component.name : component.component_name)
					?.toLowerCase()
					.includes(componentFilter.value.toLowerCase()),
			)
		: allComponents

	// Filter out currently editing component to prevent recursion
	if (!isStandard && componentEditorStore.studioComponentBlock) {
		return filtered?.filter(
			(component: StudioComponent) =>
				component.component_id !== componentEditorStore.studioComponentBlock?.componentName,
		)
	}
	return filtered
})
const customVueComponents = computed(() => {
	if (!componentFilter.value) return store.customVueComponents
	return store.customVueComponents.filter((comp) =>
		comp.component_name.toLowerCase().includes(componentFilter.value.toLowerCase()),
	)
})

const activeTab = computed(() => store.studioLayout.leftPanelComponentTab)

function createComponent() {
	componentEditorStore.promptNewComponent({
		onCreated: (component) => componentEditorStore.editComponent(component.component_id),
	})
}

function getComponentMenu(component: StudioComponent) {
	return [
		{
			label: "Edit",
			icon: "lucide-edit",
			onClick: () => componentEditorStore.editComponent(component.component_id),
		},
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			onClick: () => componentEditorStore.deleteComponent(component),
		},
	]
}

function getVueComponentMenu(component: CustomVueComponentMeta) {
	return [
		{
			label: "Edit Component",
			icon: "lucide-edit",
			onClick: () => store.navigateToCodeFile(component.studio_file_path),
		},
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			onClick: () => deleteVueComponent(component),
		},
	]
}

async function deleteVueComponent(component: CustomVueComponentMeta) {
	if (!(await confirm(`Delete ${component.component_name}.vue?`))) return
	await deleteStudioFile(
		{ frappe_app: store.activeApp?.frappe_app!, studio_app: component.studio_app },
		component.studio_file_path,
	)
	await store.setCustomComponents()
}

const vueComponentListRef = ref<HTMLElement | null>(null)
watch(
	() => store.selectedVueComponent,
	async (name) => {
		if (!name) return
		await nextTick()
		const el = vueComponentListRef.value?.querySelector<HTMLElement>(`[data-vue-component-name="${name}"]`)
		el?.scrollIntoView({ block: "nearest", behavior: "smooth" })
		setTimeout(() => {
			store.selectedVueComponent = null
		}, 1500)
	},
)

// Drag and drop handling
const componentContainer = ref(null)

useEventListener(componentContainer, "click", (e) => {
	const component = (e.target as HTMLElement)?.closest(".user-component") as HTMLElement
	if (component) {
		if (component.dataset.isStudioComponent) {
			const componentName = component.dataset.componentName as string
			componentEditorStore.selectedComponent = componentName
			// if in edit mode, open the component in editor
			if (canvasStore.fragmentData.fragmentId) {
				componentEditorStore.editComponent(componentName)
			}
		} else {
			componentEditorStore.selectedComponent = null
		}
	}
})

useEventListener(componentContainer, "dragstart", (e) => {
	const component = (e.target as HTMLElement)?.closest(".user-component") as HTMLElement
	if (component) {
		const componentName = component.dataset.componentName as string
		const isStudioComponent = component.dataset.isStudioComponent
		const isCustomVueComponent = component.dataset.isCustomVueComponent
		if (isStudioComponent) {
			e.dataTransfer?.setData("isStudioComponent", isStudioComponent)
		} else if (isCustomVueComponent) {
			e.dataTransfer?.setData("isCustomVueComponent", isCustomVueComponent)
		}
		canvasStore.handleDragStart(e, componentName)
	}
})

useEventListener(componentContainer, "dragend", () => {
	canvasStore.handleDragEnd()
})

useEventListener(componentContainer, "dblclick", (e) => {
	const component = (e.target as HTMLElement)?.closest(".user-component") as HTMLElement
	if (component && component.dataset.isStudioComponent) {
		componentEditorStore.editComponent(component.dataset.componentName as string)
	}
})
</script>
