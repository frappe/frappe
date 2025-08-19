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
			<div v-else class="flex flex-col">
				<div
					v-for="component in componentList"
					:key="component.component_id"
					class="group/component flex items-center justify-between rounded px-2 py-1"
					@dblclick="openComponentEditor(component)"
				>
					<div class="flex items-center gap-2 text-ink-gray-7">
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
			<NewComponentDialog v-model:showDialog="showNewComponentDialog" @created="openComponentEditor" />
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, markRaw } from "vue"
import { DropDown, FeatherIcon } from "frappe-ui"
import OptionToggle from "@/components/OptionToggle.vue"
import Input from "@/components/Input.vue"
import EmptyState from "@/components/EmptyState.vue"
import NewComponentDialog from "@/components/NewComponentDialog.vue"

import components from "@/data/components"
import { studioComponents } from "@/data/studioComponents"

import useCanvasStore from "@/stores/canvasStore"
import useStudioStore from "@/stores/studioStore"
import { getComponentBlock, getBlockObject, getBlockInstance, confirm } from "@/utils/helpers"
import type { leftPanelComponentTabOptions } from "@/types"
import type { StudioComponent } from "@/types/Studio/StudioComponent"

import { toast } from "vue-sonner"

const canvasStore = useCanvasStore()
const store = useStudioStore()

const componentFilter = ref("")
const componentList = computed(() => {
	if (componentFilter.value) {
		if (activeTab.value === "Standard") {
			return components.list.filter((component) =>
				component.name?.toLowerCase().includes(componentFilter.value.toLowerCase()),
			)
		} else {
			return studioComponents.data?.filter((component: StudioComponent) =>
				component.component_name?.toLowerCase().includes(componentFilter.value.toLowerCase()),
			)
		}
	} else {
		return activeTab.value === "Standard" ? components.list : studioComponents.data
	}
})

const activeTab = computed(() => store.studioLayout.leftPanelComponentTab)

const showNewComponentDialog = ref(false)

function openComponentEditor(component: StudioComponent) {
	const blocks = component.blocks?.length
		? markRaw(getBlockInstance(component.blocks))
		: getComponentBlock("container")
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

function getComponentMenu(component: StudioComponent) {
	return [
		{
			label: "Edit",
			icon: "edit",
			onClick: () => openComponentEditor(component),
		},
		{
			label: "Delete",
			icon: "trash",
			onClick: () => deleteComponent(component),
		},
	]
}

function deleteComponent(component: StudioComponent) {
	confirm(`Are you sure you want to delete the component '${component.component_name}'?`).then(
		(confirmed) => {
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
		},
	)
}
</script>
