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

	<Dialog class="pb-0" v-model="showDialog" :options="{ size: 'sm' }">
		<template #body>
			<div class="flex flex-col gap-4 p-5">
				<!-- Dialog Title -->
				<div class="flex items-center justify-between">
					<div class="text-md font-semibold text-gray-900">{{ dialogAction }}</div>
					<FeatherIcon name="x" class="h-4 cursor-pointer" @click="showDialog = false" />
				</div>

				<div v-if="dialogAction == 'Save View As'">
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

				<div v-else-if="dialogAction == 'Save'">
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

				<!-- Delete -->
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

const showDialog = ref(false)
const dialogAction = ref("")
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
	showDialog.value = false
	let doc = await createConfigResource.submit()
	await router.replace({ query: { view: doc.name } })
}

const deleteView = async () => {
	showDialog.value = false
	await call("frappe.client.delete", { doctype: "View Config", name: configName.value })
	await router.replace({ query: {} })
}

const renameView = async () => {
	showDialog.value = false
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

const getActions = () => {
	let actions = []
	if (isDefaultConfig.value) {
		configUpdated.value &&
			actions.push({
				label: "Save As",
				icon: "plus",
				onClick: () => {
					dialogAction.value = "Save View As"
					showDialog.value = true
				},
			})
	} else {
		configUpdated.value &&
			actions.push({
				label: "Save Changes",
				icon: "save",
				onClick: () => updateView(),
			})

		actions.push(
			{
				label: "Rename",
				icon: "edit-3",
				onClick: () => {
					dialogAction.value = "Save"
					showDialog.value = true
				},
			},
			{
				label: "Delete",
				icon: "trash",
				onClick: () => {
					dialogAction.value = "Delete"
					showDialog.value = true
				},
			}
		)
	}
	return actions
}

const getDefaultViews = () => {
	return [
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
	]
}

const getSavedViews = () => {
	return doctypeSavedViews.value
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
}

const viewSwitcherOptions = computed(() => {
	const options = []

	const actions = getActions()
	if (actions.length) {
		options.push({
			group: "View Actions",
			items: actions,
		})
	}

	options.push({
		group: "Default Views",
		items: getDefaultViews(),
	})

	const savedViews = getSavedViews()
	if (savedViews.length) {
		options.push({
			group: "Saved Views",
			items: savedViews,
		})

		if (savedViews.length > 5) {
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
		}
	}

	return options
})
</script>
