<template>
	<div class="flex flex-col gap-3">
		<div class="sticky top-[41px] z-50 mt-[-15px] flex w-full flex-col gap-3 bg-white py-3">
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
			<div v-else class="grid grid-cols-3 items-center gap-x-2 gap-y-4">
				<div v-for="component in componentList" :key="component.name">
					<div
						class="flex cursor-grab flex-col items-center justify-center gap-2 text-gray-700"
						draggable="true"
						@dragstart="(ev) => canvasStore.handleDragStart(ev, component.name)"
						@dragend="(_ev) => canvasStore.handleDragEnd()"
					>
						<div
							class="flex flex-col items-center justify-center gap-2 truncate rounded border-[1px] border-gray-300 bg-gray-50 p-4 transition duration-300 ease-in-out"
						>
							<component :is="component.icon" class="h-6 w-6" />
						</div>
						<span class="truncate text-xs">{{ component.title }}</span>
					</div>
				</div>
			</div>
		</template>

		<template v-else>
			<EmptyState v-if="!componentList?.length" message="No components found" />
			<div v-else class="flex flex-col" ref="componentContainer">
				<div
					v-for="component in componentList"
					:key="component.component_id"
					class="group/component flex select-none items-center justify-between rounded px-2 py-1"
					:class="{
						'border border-outline-gray-4': componentEditorStore.selectedComponent === component.component_id,
					}"
				>
					<div
						class="user-component flex items-center gap-2 text-ink-gray-7"
						draggable="true"
						:data-component-name="component.component_id"
					>
						<FeatherIcon name="box" class="h-4 w-4"></FeatherIcon>
						<p class="text-base">
							{{ component.component_name }}
						</p>
					</div>
					<div class="invisible group-hover/component:visible has-[.active-item]:visible">
						<Dropdown :options="getComponentMenu(component)" trigger="click">
							<template v-slot="{ open }">
								<button
									class="flex cursor-pointer items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
									:class="open ? 'active-item' : ''"
								>
									<FeatherIcon name="more-horizontal" class="h-3 w-3" />
								</button>
							</template>
						</Dropdown>
					</div>
				</div>
			</div>
			<Button icon-left="plus" class="mt-3" @click="showNewComponentDialog = true">Create Component</Button>
			<NewComponentDialog
				v-model:showDialog="showNewComponentDialog"
				@created="(component) => componentEditorStore.editComponent(component.component_id)"
			/>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useEventListener } from "@vueuse/core"
import { DropDown, FeatherIcon } from "frappe-ui"
import OptionToggle from "@/components/OptionToggle.vue"
import Input from "@/components/Input.vue"
import EmptyState from "@/components/EmptyState.vue"
import NewComponentDialog from "@/components/NewComponentDialog.vue"

import components from "@/data/components"
import { studioComponents } from "@/data/studioComponents"

import useCanvasStore from "@/stores/canvasStore"
import useStudioStore from "@/stores/studioStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import type { leftPanelComponentTabOptions } from "@/types"
import type { StudioComponent } from "@/types/Studio/StudioComponent"

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

const activeTab = computed(() => store.studioLayout.leftPanelComponentTab)

const showNewComponentDialog = ref(false)

function getComponentMenu(component: StudioComponent) {
	return [
		{
			label: "Edit",
			icon: "edit",
			onClick: () => componentEditorStore.editComponent(component.component_id),
		},
		{
			label: "Delete",
			icon: "trash",
			onClick: () => componentEditorStore.deleteComponent(component),
		},
	]
}

// Drag and drop handling for Studio Components
const componentContainer = ref(null)

useEventListener(componentContainer, "click", (e) => {
	const component = (e.target as HTMLElement)?.closest(".user-component") as HTMLElement
	if (component) {
		const componentName = component.dataset.componentName as string
		componentEditorStore.selectedComponent = componentName
		// if in edit mode, open the component in editor
		if (canvasStore.fragmentData.fragmentId) {
			componentEditorStore.editComponent(componentName)
		}
	}
})

useEventListener(componentContainer, "dragstart", (e) => {
	const component = (e.target as HTMLElement)?.closest(".user-component") as HTMLElement
	if (component) {
		const componentName = component.dataset.componentName as string
		setComponentData(e)
		canvasStore.handleDragStart(e, componentName)
	}
})

useEventListener(componentContainer, "dragend", () => {
	canvasStore.handleDragEnd()
})

useEventListener(componentContainer, "dblclick", (e) => {
	const component = (e.target as HTMLElement)?.closest(".user-component") as HTMLElement
	if (component) {
		componentEditorStore.editComponent(component.dataset.componentName as string)
	}
})

const setComponentData = (ev: DragEvent) => {
	ev?.dataTransfer?.setData("isStudioComponent", "true")
}
</script>
