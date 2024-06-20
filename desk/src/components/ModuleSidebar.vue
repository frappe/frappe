<template>
	<div
		class="relative flex h-full max-h-screen min-h-screen flex-col overflow-auto bg-gray-50 px-2 pt-2"
		:class="isCollapsed ? 'w-15' : 'w-60'"
	>
		<!-- Sidebar Menu -->
		<Dropdown
			v-if="desktopItem && Object.keys(desktopItem).length > 0"
			class="w-56"
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
					class="mb-1 flex items-center gap-2 rounded p-2"
					:class="[open ? 'bg-white shadow-sm' : 'hover:bg-gray-200', isCollapsed ? '' : 'w-56']"
				>
					<div class="rounded-sm p-1" :style="`background-color: ${desktopItem.color}`">
						<Icon :name="desktopItem.icon" class="h-5 w-5 text-white" />
					</div>
					<span v-if="!isCollapsed" class="truncate text-xl font-bold text-gray-800">
						{{ desktopItem?.label }}
					</span>

					<FeatherIcon
						v-if="!isCollapsed"
						name="chevron-down"
						class="ml-auto h-4 w-4 text-gray-600"
					/>
				</button>
			</template>
		</Dropdown>

		<!-- Workspaces -->
		<nav class="mt-4 flex flex-col space-y-1" v-if="sidebarItems?.workspaces">
			<Draggable
				class="w-full"
				v-model="sidebarItems.workspaces"
				group="workspaces"
				item-key="name"
				:disable="!isEditing"
			>
				<template #item="{ element: item }">
					<ModuleSidebarItem
						type="Link"
						:item="item"
						:isCollapsed="isCollapsed"
						:isEditing="isEditing"
					/>
				</template>
			</Draggable>
		</nav>

		<!-- Sections, Links, Spacers -->
		<nav class="mt-4 flex flex-col space-y-1" v-if="sidebarItems?.sections">
			<Draggable
				class="w-full"
				v-model="sidebarItems.sections"
				group="items"
				item-key="name"
				:disable="!isEditing"
			>
				<template #item="{ element: item }">
					<ModuleSidebarItem
						:type="item.type"
						:item="item"
						:isCollapsed="isCollapsed"
						:isEditing="isEditing"
					/>
				</template>
			</Draggable>
		</nav>

		<button
			v-if="isEditing && !isCollapsed"
			class="ml-2 mt-5 flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-700"
			@click="showItemDialog({ type: 'Link', link_type: 'DocType' }, 'add')"
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
			title: dialogAction === 'edit' ? 'Edit Sidebar Item' : 'Add Sidebar Item',
			size: '2xl',
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
		@after-leave="dialogItem = emptySidebarLink"
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

				<template v-if="dialogItem.type === 'Section Break'">
					<FormControl type="text" size="sm" label="Label" v-model="dialogItem.label" />
					<Grid
						label="Links"
						:fields="[
							{
								label: 'Link Type',
								fieldname: 'link_type',
								fieldtype: 'select',
								options: ['DocType', 'Page', 'Report', 'Dashboard', 'URL'],
								onChange: (_value: string, index: number) => {
									if (dialogItem?.links) {
										dialogItem.links[index].link_to = ''
										dialogItem.links[index].label = ''
									}
								},
								width: 1.5,
							},
							{
								label: 'Link To',
								fieldname: 'link_to',
								fieldtype: 'Link',
								onChange: (value: string, index: number) => {
									if (dialogItem?.links)
										dialogItem.links[index].label = value
								},
								width: 2.25,
							},
							{
								label: 'Icon',
								fieldname: 'icon',
								fieldtype: 'Icon',
								width: 1.5,
							},
							{
								label: 'Label',
								fieldname: 'label',
								fieldtype: 'Text',
								width: 2,
							},
						]"
						v-model:rows="dialogItem.links"
					/>
				</template>

				<template v-else-if="dialogItem.type === 'Link'">
					<FormControl
						type="select"
						:options="['DocType', 'Page', 'Report', 'Dashboard', 'URL']"
						size="sm"
						label="Link Type"
						v-model="dialogItem.link_type"
						@change="
							() => {
								dialogItem.link_to = ''
								dialogItem.label = ''
							}
						"
					/>
					<FormControl
						v-if="dialogItem.link_type === 'URL'"
						type="text"
						size="sm"
						label="URL"
						v-model="dialogItem.url"
					/>
					<Link
						v-else
						:doctype="dialogItem.link_type"
						v-model="dialogItem.link_to"
						label="Link To"
						@update:modelValue="() => (dialogItem.label = dialogItem.link_to)"
					/>
					<div class="flex space-x-2">
						<IconPicker size="sm" label="Icon" v-model="dialogItem.icon" />
						<FormControl
							class="w-full"
							type="text"
							size="sm"
							label="Label"
							v-model="dialogItem.label"
						/>
					</div>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, provide } from "vue"
import { Dropdown, FeatherIcon, Dialog, FormControl, createResource } from "frappe-ui"
import Draggable from "vuedraggable"

import Icon from "@/components/Icon.vue"
import ModuleSidebarItem from "@/components/ModuleSidebarItem.vue"
import Link from "@/components/FormControls/Link.vue"
import Grid from "@/components/FormControls/Grid.vue"
import IconPicker from "@/components/FormControls/IconPicker.vue"

import { getDesktopItem, sidebar } from "@/data/desktop"
import { DesktopItem, ModuleSidebar, ModuleSidebarLink, UpdateSidebarItemAction } from "@/types"
import { updateSidebarItemFnKey } from "@/types/injectionKeys"

const props = defineProps({
	module: {
		type: String,
		required: true,
	},
})

const emptySidebarItems = {
	name: "",
	module: "",
	workspaces: [],
	sections: [],
}

const emptySidebarLink: ModuleSidebarLink = {
	type: "Link",
	link_type: "DocType",
	link_to: "",
	name: "",
	icon: "",
	label: "",
	links: [],
}

const desktopItem = ref<DesktopItem | null>(null)
const isCollapsed = ref(false)
const isEditing = ref(false)
const draftSidebarItems = ref<ModuleSidebar>(emptySidebarItems)
const showDialog = ref(false)
const dialogItem = ref<ModuleSidebarLink>({ ...emptySidebarLink })
const dialogAction = ref("")

provide(updateSidebarItemFnKey, updateSidebarItem)

const sidebarItems = computed({
	get: () => {
		if (isEditing.value) {
			return draftSidebarItems.value
		} else {
			return sidebar.data
		}
	},
	set: (value) => {
		draftSidebarItems.value = value
	},
})

const sidebarResource = createResource({
	url: "frappe.desk.doctype.module_sidebar.module_sidebar.save_module_sidebar",
})

function enableEditMode() {
	draftSidebarItems.value = JSON.parse(JSON.stringify(sidebar.data))
	isEditing.value = true
}

function updateSidebarItem(item: ModuleSidebarLink, action: UpdateSidebarItemAction): void {
	if (action === "addBelow") {
		const index = getItemIndex(item)
		showItemDialog({ type: "Link", link_type: "DocType", index: index }, "add")
	} else if (action === "edit") {
		showItemDialog(item, "edit")
	} else if (action === "delete") {
		const index = getItemIndex(item)
		draftSidebarItems.value.sections.splice(index, 1)
	} else if (action === "duplicate") {
		const index = getItemIndex(item)
		const newItem = {
			...item,
			name: `${item.name}_copy`,
			index: index + 1,
		}
		if (newItem.type !== "Spacer") {
			newItem.label = `${newItem.label} Copy`
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
			draftSidebarItems.value = { ...emptySidebarItems }
			await getSidebar(props.module)
			isEditing.value = false
		})
}

function getItemIndex(item: ModuleSidebarLink) {
	return draftSidebarItems.value.sections.findIndex((section) => section.name === item.name)
}

function showItemDialog(item: Partial<ModuleSidebarLink>, action: "add" | "edit") {
	Object.assign(dialogItem.value, JSON.parse(JSON.stringify(item)))
	dialogAction.value = action
	showDialog.value = true
}

async function getSidebar(module: string) {
	desktopItem.value = await getDesktopItem(module)
	sidebar.submit({ module: module })
}
getSidebar(props.module)
</script>
