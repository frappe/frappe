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
					<span v-if="!isCollapsed" class="text-xl font-bold text-gray-800">
						{{ desktopItem?.label }}
					</span>

					<FeatherIcon name="chevron-down" class="ml-auto h-4 w-4 text-gray-600" />
				</button>
			</template>
		</Dropdown>

		<!-- Workspaces -->
		<nav class="mt-4 flex flex-col space-y-0.5" v-if="sidebarItems?.workspaces">
			<ModuleSidebarLink
				v-for="item in sidebarItems?.workspaces"
				:key="item.name"
				:link="item"
				:isCollapsed="isCollapsed"
				:isEditing="isEditing"
				@updateSidebarItem="updateSidebarItem"
			/>
		</nav>

		<!-- Sections, Links, Spacers -->
		<nav class="mt-4 flex flex-col space-y-0.5" v-if="sidebarItems?.sections">
			<template v-for="item in sidebarItems?.sections" :key="item.name">
				<ModuleSidebarLink
					v-if="item.type === 'Link'"
					:link="item"
					:isCollapsed="isCollapsed"
					:isEditing="isEditing"
					@updateSidebarItem="updateSidebarItem"
				/>

				<div v-else-if="item.type === 'Spacer'" class="h-5"></div>

				<div v-else-if="item.type === 'Section Break' && item.links?.length">
					<div v-if="isCollapsed" class="mx-2 my-2 h-1 border-b"></div>
					<div
						v-else
						@click="item.opened = !item.opened"
						class="mt-5 flex cursor-pointer items-center gap-2 px-2"
						:class="item.opened ? 'mb-3' : ''"
					>
						<FeatherIcon
							:name="item.opened ? 'chevron-down' : 'chevron-right'"
							class="h-4 w-4 font-semibold text-gray-600"
						/>
						<div class="flex items-center gap-1 text-sm uppercase text-gray-700">
							{{ item.label }}
						</div>
					</div>

					<nav v-if="item.opened" class="flex flex-col space-y-0.5">
						<ModuleSidebarLink
							v-for="link in item.links"
							:key="link.name"
							:link="link"
							:isCollapsed="isCollapsed"
							:isEditing="isEditing"
							@updateSidebarItem="updateSidebarItem"
						/>
					</nav>
				</div>
			</template>
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
				<Button
					variant="outline"
					class="w-full"
					@click="
						() => {
							draftSidebarItems = []
							isEditing = false
						}
					"
				>
					Discard
				</Button>
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
import { computed, ref } from "vue"
import { Dropdown, FeatherIcon, Dialog, FormControl, createResource } from "frappe-ui"

import Icon from "@/components/Icon.vue"
import ModuleSidebarLink from "@/components/ModuleSidebarLink.vue"

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
	isEditing.value = true
	draftSidebarItems.value = Object.assign({}, sidebar.data)
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
		draftSidebarItems.value.sections.splice(index + 1, 0, { ...item })
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
