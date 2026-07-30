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
			<template v-else>
				<CollapsibleSection
					v-for="section in sections"
					:key="section.label"
					:sectionName="section.label"
					class="px-2"
				>
					<template #title-suffix v-if="section.label === 'Framework UI'">
						<Tooltip text="Experimental — these components are still under development">
							<LucideFlaskConical class="h-3.5 w-3.5 text-ink-amber-6" />
						</Tooltip>
					</template>
					<!-- A family primary shows a stacked edge + part count; clicking it opens its parts
					     tray at the source tile's row boundary (full width, caret under the tile) so no
					     grid cell is orphaned. While searching, every match (parts included) shows as a
					     plain tile so nothing stays hidden behind a family. -->
					<div v-if="section.tiles.length" class="grid grid-cols-3 items-start gap-x-2 gap-y-4">
						<template v-for="(component, index) in section.tiles" :key="component.name">
							<ComponentTile
								:component="component"
								:stacked="!isSearching && component.isGroup"
								:expanded="!isSearching && expandedFamily === component.name"
								@click="onTileClick(component)"
							/>

							<!-- Parts of the open family. Inserted at the end of the source tile's row and
							     spanning every column, with a caret under the source tile's column. -->
							<div
								v-if="index === section.trayAfter"
								class="relative col-span-full -mt-1 rounded-xl border border-outline-gray-2 bg-surface-base p-3.5"
							>
								<span
									class="absolute -top-1.5 h-3 w-3 -translate-x-1/2 rotate-45 border-l border-t border-outline-gray-2 bg-surface-base"
									:style="{ left: section.caretLeft }"
								/>
								<div class="mb-3 flex items-center justify-between">
									<span class="text-sm font-medium tracking-wide text-ink-gray-5">
										{{ expandedPrimary?.title }} Components
									</span>
									<Button icon="lucide-x" variant="ghost" size="sm" @click="expandedFamily = null" />
								</div>
								<div class="grid grid-cols-3 items-start gap-x-2 gap-y-4">
									<ComponentTile v-for="part in expandedParts" :key="part.name" :component="part" />
								</div>
							</div>
						</template>
					</div>
				</CollapsibleSection>
			</template>
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
import { Dropdown, FeatherIcon, Tooltip, Button } from "frappe-ui"
import LucideFlaskConical from "~icons/lucide/flask-conical"
import LucideX from "~icons/lucide/x"
import OptionToggle from "@/components/OptionToggle.vue"
import Input from "@/components/Input.vue"
import EmptyState from "@/components/EmptyState.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import ComponentTile from "@/components/ComponentTile.vue"

import components from "@/data/components"
import { studioComponents } from "@/data/studioComponents"
import { deleteStudioFile } from "@/data/studioFiles"

import useCanvasStore from "@/stores/canvasStore"
import useStudioStore from "@/stores/studioStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import { confirm } from "@/utils/helpers"
import type { leftPanelComponentTabOptions, FrappeUIComponent } from "@/types"
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

const isSearching = computed(() => Boolean(componentFilter.value))

const standardComponentGroups = computed(() =>
	components.getComponentGroups((componentList.value as any[]) || []),
)

// Grid tiles for a section: while searching, every match (parts included) shows as a plain
// tile; otherwise parts are hidden and reached through their family primary's tray.
function gridTiles(group: { components: FrappeUIComponent[] }) {
	return isSearching.value ? group.components : group.components.filter((c) => !c.group)
}

const expandedFamily = ref<string | null>(null)
function onTileClick(component: FrappeUIComponent) {
	if (isSearching.value || !component.isGroup) return
	expandedFamily.value = expandedFamily.value === component.name ? null : component.name
}

// Panel sections with their tiles and, for the open family, where its parts tray lands.
// The tray is inserted at the END of the source tile's row (design 1b, "row boundary") so the
// row stays full and no cell is orphaned; the caret sits under the source tile's column.
const GRID_COLUMNS = 3
const sections = computed(() =>
	standardComponentGroups.value.map((group) => {
		const tiles = gridTiles(group)
		const sourceIndex =
			isSearching.value || !expandedFamily.value
				? -1
				: tiles.findIndex((c) => c.name === expandedFamily.value)
		const rowEnd =
			sourceIndex === -1
				? -1
				: Math.min(Math.floor(sourceIndex / GRID_COLUMNS) * GRID_COLUMNS + GRID_COLUMNS - 1, tiles.length - 1)
		const column = sourceIndex === -1 ? 0 : sourceIndex % GRID_COLUMNS
		return {
			label: group.label,
			tiles,
			trayAfter: rowEnd,
			caretLeft: `${((column + 0.5) / GRID_COLUMNS) * 100}%`,
		}
	}),
)

const partsFor = (component: FrappeUIComponent) => components.getParts(component.name)
const expandedPrimary = computed(() => (expandedFamily.value ? components.get(expandedFamily.value) : null))
const expandedParts = computed(() => (expandedPrimary.value ? partsFor(expandedPrimary.value) : []))

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
