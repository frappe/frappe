<template>
	<Dropdown :options="viewSwitcherOptions">
		<template #default="{ open }">
			<Button :label="configSettings.data.label">
				<template #prefix>
					<FeatherIcon :name="configSettings.data.icon || 'list'" class="h-3.5 text-gray-600" />
				</template>
				<template #suffix>
					<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-3.5 text-gray-600" />
				</template>
			</Button>
		</template>
	</Dropdown>
	<Dialog class="pb-0" v-model="showViewActionsModal" :options="{ size: 'sm' }">
		<template #body>
			<div class="flex flex-col gap-4 p-5">
				<div class="flex items-center justify-between">
					<div class="text-md font-semibold text-gray-900">{{ viewModalMode }}</div>
					<FeatherIcon name="x" class="h-4 cursor-pointer" @click="showViewActionsModal = false" />
				</div>
				<div v-if="viewModalMode == 'Save View As'">
					<div class="flex flex-col gap-4">
						<FormControl
							:type="'text'"
							size="md"
							variant="subtle"
							placeholder="View Name"
							v-model="newViewName"
						/>
						<Button variant="solid" label="Save" @click="createView">
							<template #prefix>
								<FeatherIcon name="save" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>
				<div v-else-if="viewModalMode == 'Save'">
					<div class="flex flex-col gap-4">
						<FormControl
							:type="'text'"
							size="md"
							variant="subtle"
							placeholder="View Name"
							v-model="configSettings.data.label"
						/>
						<Button variant="solid" label="Update" @click="renameView">
							<template #prefix>
								<FeatherIcon name="save" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>
				<div v-else>
					<div class="flex flex-col gap-4">
						<div class="text-base">Are you sure you want to delete this view?</div>
						<Button variant="outline" theme="red" label="Delete" @click="deleteView">
							<template #prefix>
								<FeatherIcon name="trash" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { useRoute, useRouter } from "vue-router"
import { ref, computed } from "vue"
import { call, createResource, FeatherIcon, Dropdown, Dialog } from "frappe-ui"

import {
	configName,
	configSettings,
	isDefaultConfig,
	listConfig,
	oldConfig,
	configUpdated,
	doctypeSavedViews,
} from "@/stores/view"

const props = defineProps({
	queryFilters: {
		type: Object,
		required: true,
	},
})

const viewModalMode = ref("")
const showViewActionsModal = ref(false)
const newViewName = ref("")

const route = useRoute()
const router = useRouter()

const createConfigResource = createResource({
	url: "frappe.client.insert",
	method: "POST",
	makeParams: () => {
		return {
			doc: {
				doctype: "View Config",
				document_type: route.params.doctype,
				label: newViewName.value,
				columns: JSON.stringify(listConfig.value.columns),
				filters: JSON.stringify(props.queryFilters),
				sort_field: listConfig.value.sort[0],
				sort_order: listConfig.value.sort[1],
				custom: 1,
			},
		}
	},
})

const createView = async () => {
	showViewActionsModal.value = false
	let doc = await createConfigResource.submit()
	await router.replace({ query: { view: doc.name } })
}

const deleteView = async () => {
	showViewActionsModal.value = false
	await call("frappe.client.delete", { doctype: "View Config", name: configName.value })
	await router.replace({ query: {} })
}

const renameView = async () => {
	showViewActionsModal.value = false
	await call("frappe.client.set_value", {
		doctype: "View Config",
		name: configName.value,
		fieldname: "label",
		value: configSettings.data.label,
	})
}

const updateView = async () => {
	call("frappe.desk.doctype.view_config.view_config.update_config", {
		config_name: configName.value,
		config: listConfig.value,
		filters: props.queryFilters,
	}).then(() => {
		oldConfig.value = JSON.parse(JSON.stringify(listConfig.value))
	})
}

const viewSwitcherOptions = computed(() => {
	let options = []

	if (isDefaultConfig.value)
		configUpdated.value &&
			options.push({
				group: "View Actions",
				items: [
					{
						label: "Save As",
						icon: "plus",
						onClick: () => {
							viewModalMode.value = "Save View As"
							showViewActionsModal.value = true
						},
					},
				],
			})
	else {
		let actions = []

		configUpdated.value &&
			actions.push({
				label: "Save Changes",
				icon: "save",
				onClick: () => {
					updateView()
				},
			})

		actions.push(
			{
				label: "Rename",
				icon: "edit-3",
				onClick: () => {
					viewModalMode.value = "Save"
					showViewActionsModal.value = true
				},
			},
			{
				label: "Delete",
				icon: "trash",
				onClick: () => {
					viewModalMode.value = "Delete"
					showViewActionsModal.value = true
				},
			}
		)

		actions.length &&
			options.push({
				group: "View Actions",
				items: actions,
			})
	}

	options.push({
		group: "Default Views",
		items: [
			{
				label: "List View",
				icon: "list",
				onClick: async () => {
					await router.replace({ query: {} })
				},
			},
			{
				label: "Report View",
				icon: "table",
			},
			{
				label: "Kanban View",
				icon: "grid",
			},
			{
				label: "Dashboard View",
				icon: "pie-chart",
			},
		],
	})

	let savedViews = doctypeSavedViews.value
		.filter((view) => view.name != configName.value)
		.map((view) => {
			return {
				label: view.label,
				icon: view.icon || "list",
				onClick: async () => {
					await router.replace({ query: { view: view.name } })
				},
			}
		})

	savedViews.length &&
		options.push({
			group: "Saved Views",
			items: savedViews,
		})

	doctypeSavedViews.value.length > 5 &&
		options.push({
			group: "More Views",
			hideLabel: true,
			items: [
				{
					label: "More Views",
					onClick: () => {},
				},
			],
		})
	return options
})
</script>
