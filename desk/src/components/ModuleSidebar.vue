<template>
	<div
		class="relative flex h-full max-h-screen min-h-screen flex-col overflow-auto bg-gray-50 px-2 pt-2"
		:class="isCollapsed ? 'w-15' : 'w-60'"
	>
		<!-- Sidebar Menu -->
		<Dropdown
			v-if="desktopItem"
			:options="[
				{
					label: 'Back to Home',
					icon: 'arrow-left',
					onClick: () => $router.push({ name: 'Home' }),
				},
				{
					label: 'Edit Sidebar',
					icon: 'edit',
					onClick: () => enableEditMode(),
				},
			]"
		>
			<template v-slot="{ open }">
				<button
					class="mb-1 flex w-[14rem] items-center gap-2 rounded p-2"
					:class="open ? 'bg-white shadow-sm' : 'hover:bg-gray-200'"
				>
					<div class="rounded-sm p-1" :style="`background-color: ${desktopItem.color}`">
						<Icon :name="desktopItem?.icon" class="h-5 w-5 text-white" />
					</div>
					<span v-if="!isCollapsed" class="truncate text-xl font-bold text-gray-800">
						{{ desktopItem?.label }}
					</span>

					<FeatherIcon name="chevron-down" class="ml-auto h-4 w-4 text-gray-600" />
				</button>
			</template>
		</Dropdown>

		<!-- Workspaces -->
		<nav class="mt-4 flex flex-col space-y-1" v-if="sidebarItems?.workspaces">
			<ModuleSidebarItem
				v-for="item in sidebarItems?.workspaces"
				type="Link"
				:key="item.name"
				:item="item"
				:isCollapsed="isCollapsed"
				:isEditing="isEditing"
			/>
		</nav>

		<!-- Sections, Links, Spacers -->
		<nav class="mt-4 flex flex-col space-y-1" v-if="sidebarItems?.sections">
			<ModuleSidebarItem
				v-for="item in sidebarItems?.sections"
				:key="item.name"
				:type="item.type"
				:item="item"
				:isCollapsed="isCollapsed"
				:isEditing="isEditing"
			/>
		</nav>

		<button
			v-if="isEditing && !isCollapsed"
			class="ml-2 mt-5 flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-700"
			@click="showItemDialog({ type: 'Link' }, 'add')"
		>
			<FeatherIcon name="plus" class="h-4 w-4" />
			Add Sidebar Item
		</button>

		<div class="sticky bottom-0 my-1 mt-auto flex items-end gap-2 bg-gray-50 py-2">
			<template v-if="isEditing">
				<Button variant="outline" class="w-full" @click="isEditing = false"> Discard </Button>
				<Button
					variant="solid"
					class="w-full"
					:loading="sidebarResource.loading"
					@click="updateSidebar"
				>
					Save
				</Button>
			</template>

			<button
				v-else
				class="flex w-full gap-2 rounded p-2 text-sm uppercase text-gray-700 hover:bg-gray-200"
				:class="isCollapsed ? 'justify-center' : ''"
				@click="isCollapsed = !isCollapsed"
			>
				<FeatherIcon
					:name="isCollapsed ? 'arrow-right' : 'arrow-left'"
					class="h-4 w-4 text-gray-600"
				/>
				<span v-if="!isCollapsed">Collapse</span>
			</button>
		</div>
	</div>

	<Dialog
		:options="{
			title: dialogAction === 'edit' ? 'Edit Link' : 'Add Link',
			actions: [
				{
					label: 'Save',
					variant: 'solid',
					onClick: () => {
						if (dialogAction === 'edit') {
							const index = getItemIndex(dialogItem)
							draftSidebarItems.sections.splice(index, 1, dialogItem)
						} else {
							dialogItem.index !== undefined
								? draftSidebarItems.sections.splice(dialogItem.index + 1, 0, dialogItem)
								: draftSidebarItems.sections.push(dialogItem)
						}
						showDialog = false
					},
				},
			],
		}"
		v-model="showDialog"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					type="select"
					:options="['Link', 'Section Break', 'Spacer']"
					size="sm"
					label="Type"
					v-model="dialogItem.type"
				/>
				<FormControl
					type="select"
					v-if="dialogItem.type === 'Link'"
					:options="['DocType', 'Page', 'Report', 'Dashboard', 'URL']"
					size="sm"
					label="Link Type"
					v-model="dialogItem.link_type"
				/>
				<FormControl
					v-if="dialogItem.type === 'Link'"
					type="Autocomplete"
					size="sm"
					label="Link To"
					v-model="dialogItem.link_to"
					@change="dialogItem.label = dialogItem.link_to"
				/>
				<FormControl
					v-if="dialogItem.link_type === 'URL'"
					type="text"
					size="sm"
					label="URL"
					v-model="dialogItem.url"
				/>
				<div class="flex space-x-2" v-if="dialogItem.type === 'Link'">
					<FormControl
						class="w-full"
						type="Icon"
						size="sm"
						label="Icon"
						v-model="dialogItem.icon"
					/>
					<FormControl
						class="w-full"
						type="text"
						size="sm"
						label="Label"
						v-model="dialogItem.label"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, provide } from "vue"
import { Dropdown, FeatherIcon, Dialog, FormControl, createResource } from "frappe-ui"

import Icon from "@/components/Icon.vue"
import ModuleSidebarItem from "@/components/ModuleSidebarItem.vue"

import { getDesktopItem, sidebar } from "@/data/desktop"

const props = defineProps({
	module: {
		type: String,
		required: true,
	},
})

const desktopItem = ref(null)
const isCollapsed = ref(false)
const isEditing = ref(false)
const draftSidebarItems = ref([])
const showDialog = ref(false)
const dialogItem = ref({})
const dialogAction = ref("")

provide("updateSidebarItem", updateSidebarItem)

const sidebarItems = computed(() => {
	if (isEditing.value) {
		return draftSidebarItems.value
	} else {
		return sidebar.data
	}
})

const sidebarResource = createResource({
	url: "frappe.desk.doctype.module_sidebar.module_sidebar.save_module_sidebar",
})

function enableEditMode() {
	draftSidebarItems.value = JSON.parse(JSON.stringify(sidebar.data))
	isEditing.value = true
}

function updateSidebarItem(item, action) {
	if (action === "addBelow") {
		const index = getItemIndex(item)
		showItemDialog({ type: "Link", index: index }, "add")
	} else if (action === "edit") {
		showItemDialog(item, "edit")
	} else if (action === "delete") {
		const index = getItemIndex(item)
		draftSidebarItems.value.sections.splice(index, 1)
	} else if (action === "duplicate") {
		const index = getItemIndex(item)
		const newItem = {
			...item,
			label: `${item.label} Copy`,
			name: `${item.name}_copy`,
			index: index + 1,
		}
		draftSidebarItems.value.sections.splice(index + 1, 0, newItem)
	}
}

function updateSidebar() {
	sidebarResource
		.submit({
			name: sidebar.data.name,
			sections: draftSidebarItems.value.sections,
			workspaces: draftSidebarItems.value.workspaces,
		})
		.then(async () => {
			draftSidebarItems.value = []
			isEditing.value = false
			await getSidebar(props.module)
		})
}

function getItemIndex(item) {
	return draftSidebarItems.value.sections.findIndex((section) => section.name === item.name)
}

function showItemDialog(item, action) {
	dialogItem.value = { ...item }
	dialogAction.value = action
	showDialog.value = true
}

async function getSidebar(module) {
	desktopItem.value = await getDesktopItem(module)
	sidebar.submit({ module: module })
}
getSidebar(props.module)
</script>
